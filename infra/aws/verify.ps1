[CmdletBinding()]
param(
    [string]$Profile = "reflex-aws",
    [string]$Region = "ap-southeast-2",
    [string]$ExpectedSourceSha256 = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$runTag = [DateTime]::UtcNow.ToString("yyyyMMdd'T'HHmmss'Z'").ToLowerInvariant()
$sourceZip = Join-Path ([IO.Path]::GetTempPath()) "reflex-verify-$runTag.zip"

if ($Region -ne "ap-southeast-2") { throw "REFLEX resources must use ap-southeast-2 (Sydney)." }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "The project Python environment is missing: $python" }

function Invoke-AwsRaw {
    param([Parameter(Mandatory)][string[]]$AwsArgs)
    $output = & aws @AwsArgs --profile $Profile --region $Region --no-cli-pager 2>&1
    $exit = $LASTEXITCODE
    if ($exit -ne 0) {
        $message = ($output | Out-String).Trim() -replace '[\r\n]+', ' '
        throw "AWS CLI failed ($($AwsArgs[0..([Math]::Min(2, $AwsArgs.Length - 1))] -join ' ')): $message"
    }
    return ($output | Out-String).Trim()
}

function Invoke-AwsJson {
    param([Parameter(Mandatory)][string[]]$AwsArgs)
    $text = Invoke-AwsRaw -AwsArgs $AwsArgs
    if (-not $text) { return $null }
    return $text | ConvertFrom-Json
}

try {
    $null = Invoke-AwsRaw -AwsArgs @("sts", "get-caller-identity", "--query", "UserId", "--output", "text")
    $foundation = Invoke-AwsJson -AwsArgs @("cloudformation", "describe-stacks", "--stack-name", "reflex-foundation")
    $service = Invoke-AwsJson -AwsArgs @("cloudformation", "describe-stacks", "--stack-name", "reflex-service")
    if ($foundation.Stacks[0].StackStatus -notin @("CREATE_COMPLETE", "UPDATE_COMPLETE")) { throw "Foundation stack is not stable: $($foundation.Stacks[0].StackStatus)." }
    if ($service.Stacks[0].StackStatus -notin @("CREATE_COMPLETE", "UPDATE_COMPLETE")) { throw "Service stack is not stable: $($service.Stacks[0].StackStatus)." }

    $foundationOutputs = @{}
    foreach ($item in $foundation.Stacks[0].Outputs) { $foundationOutputs[$item.OutputKey] = $item.OutputValue }
    $serviceOutputs = @{}
    foreach ($item in $service.Stacks[0].Outputs) { $serviceOutputs[$item.OutputKey] = $item.OutputValue }
    $endpoint = [string]$serviceOutputs.Endpoint
    if (-not $endpoint.StartsWith("https://")) { $endpoint = "https://$endpoint" }
    if (-not $endpoint.StartsWith("https://")) { throw "Service stack has no valid HTTPS endpoint." }

    $proofPath = Join-Path $root "results\aws-smoke-$runTag.json"
    Write-Host "Running a fresh synthetic smoke request against $endpoint ..."
    & $python (Join-Path $root "backend\scripts\smoke.py") --api-base $endpoint --expect-aws --proof-file $proofPath
    if ($LASTEXITCODE -ne 0) { throw "The live AWS smoke request failed; no cloud proof was recorded." }
    $proof = Get-Content -LiteralPath $proofPath -Raw | ConvertFrom-Json
    if ($proof.endpoint.TrimEnd('/') -ne $endpoint.TrimEnd('/') -or $proof.runtime -ne "aws" -or $proof.opencv_version -notlike "5.*" -or -not $proof.synthetic_fixture -or $proof.tool_trace -notcontains "inspect_crop") {
        throw "The smoke proof does not match the current AWS endpoint, OpenCV 5, and synthetic crop trace."
    }

    $sourceResult = & $python (Join-Path $root "backend\scripts\package_aws_source.py") --output $sourceZip
    if ($LASTEXITCODE -ne 0) { throw "Could not fingerprint the allowlisted AWS source package." }
    $sourceBundleHash = (Get-FileHash -LiteralPath $sourceZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ExpectedSourceSha256 -and $sourceBundleHash -ne $ExpectedSourceSha256.ToLowerInvariant()) { throw "Current source archive hash differs from the expected built source hash." }

    $projectName = $foundationOutputs.ImageBuildProject
    $recentBuildIds = @(Invoke-AwsJson -AwsArgs @("codebuild", "list-builds-for-project", "--project-name", $projectName, "--sort-order", "DESCENDING", "--query", "ids[0:20]"))
    if ($recentBuildIds.Count -eq 0) { throw "No CodeBuild runs were found for the image builder." }
    $buildArgs = @("codebuild", "batch-get-builds", "--ids") + $recentBuildIds
    $buildResponse = Invoke-AwsJson -AwsArgs $buildArgs
    $matchingBuild = $null
    foreach ($build in $buildResponse.builds) {
        $tagVariable = $build.environment.environmentVariables | Where-Object { $_.name -eq "IMAGE_TAG" } | Select-Object -First 1
        if ($tagVariable -and $tagVariable.value -eq $proof.build_revision) { $matchingBuild = $build; break }
    }
    if (-not $matchingBuild -or $matchingBuild.buildStatus -ne "SUCCEEDED") { throw "No successful CodeBuild image run matches build $($proof.build_revision)." }
    $testPhase = $matchingBuild.phases | Where-Object { $_.phaseType -eq "BUILD" } | Select-Object -First 1
    if (-not $testPhase -or $testPhase.phaseStatus -ne "SUCCEEDED") { throw "The matching CodeBuild build phase did not succeed." }

    $imageDigest = Invoke-AwsRaw -AwsArgs @("ecr", "describe-images", "--repository-name", "reflex/inspection", "--image-ids", "imageTag=$($proof.build_revision)", "--query", "imageDetails[0].imageDigest", "--output", "text")
    if (-not $imageDigest.StartsWith("sha256:")) { throw "The build image digest could not be verified in ECR." }

    $inspectionEvent = $null
    $requestEvent = $null
    for ($attempt = 0; $attempt -lt 12; $attempt++) {
        $logs = Invoke-AwsJson -AwsArgs @("logs", "filter-log-events", "--log-group-name", $foundationOutputs.AppLogGroupName, "--filter-pattern", $proof.request_id)
        foreach ($entry in $logs.events) {
            try {
                $message = [string]$entry.message
                $jsonStart = $message.IndexOf("{")
                if ($jsonStart -lt 0) { continue }
                $candidate = $message.Substring($jsonStart) | ConvertFrom-Json
                if ($candidate.request_id -ne $proof.request_id) { continue }
                if ($candidate.event -eq "inspection_completed") { $inspectionEvent = $candidate }
                if ($candidate.event -eq "request_completed") { $requestEvent = $candidate }
            } catch { }
        }
        if ($inspectionEvent -and $requestEvent) { break }
        Start-Sleep -Seconds 5
    }
    if (-not $inspectionEvent -or -not $requestEvent) { throw "CloudWatch did not return both structured events for request $($proof.request_id)." }
    if ($inspectionEvent.inspection_id -ne $proof.inspection_id -or $inspectionEvent.opencv_version -notlike "5.*" -or $inspectionEvent.agent_tools -notcontains "inspect_crop" -or $inspectionEvent.decision -ne $proof.decision -or -not $inspectionEvent.synthetic) {
        throw "The CloudWatch inspection event does not match the synthetic smoke output."
    }
    if ($requestEvent.route -ne "/api/inspections" -or $requestEvent.status_code -ne 200) { throw "The CloudWatch request event does not confirm a successful inspection POST." }

    $evidence = @{
        smoke = $proof
        cloudwatch = @{ inspection = $inspectionEvent; request = $requestEvent }
        source_bundle_sha256 = $sourceBundleHash
        image_tag = $proof.build_revision
        image_digest = $imageDigest
        codebuild_id = $matchingBuild.id
        codebuild_status = $matchingBuild.buildStatus
        codebuild_build_phase = $testPhase.phaseStatus
        service_status = $service.Stacks[0].StackStatus
        region = $Region
        task_count_limit = 1
        inspection_retention_days = 1
        foundation_stack = "reflex-foundation"
        service_stack = "reflex-service"
    }
    $evidencePath = Join-Path $root "results\aws-evidence-$runTag.json"
    $evidence | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $evidencePath -Encoding utf8
    Write-Host "Verified endpoint: $endpoint"
    Write-Host "Verified same-request CloudWatch inspection and request events, OpenCV 5, crop trace, and successful CodeBuild."
    Write-Host "Evidence: $evidencePath"
    Write-Host "The public demo accepts synthetic images only. AWS Fargate, load-balancer, public IPv4, log, and image resources are billable."
} finally {
    if (Test-Path -LiteralPath $sourceZip -PathType Leaf) { Remove-Item -LiteralPath $sourceZip -Force }
}
