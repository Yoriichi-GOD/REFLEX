[CmdletBinding()]
param(
    [string]$Profile = "reflex-aws",
    [string]$Region = "ap-southeast-2",
    [string]$StackName = "reflex-foundation",
    [string]$ExistingImageTag = "",
    [string]$ExistingBuildId = "",
    [string]$ExpectedSourceSha256 = "",
    [switch]$UpdateService
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$template = Join-Path $PSScriptRoot "foundation.yaml"
$serviceTemplate = Join-Path $PSScriptRoot "service.yaml"
$python = Join-Path $root ".venv\Scripts\python.exe"
$runTag = [DateTime]::UtcNow.ToString("yyyyMMdd'T'HHmmss'Z'").ToLowerInvariant()

if ($Region -ne "ap-southeast-2") { throw "REFLEX regional resources must use ap-southeast-2 (Sydney)." }
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

Write-Host "Checking the authorized AWS profile and validating the Sydney infrastructure template..."
$null = Invoke-AwsRaw -AwsArgs @("sts", "get-caller-identity", "--query", "UserId", "--output", "text")
$null = Invoke-AwsJson -AwsArgs @("cloudformation", "validate-template", "--template-body", "file://$template")
$null = Invoke-AwsJson -AwsArgs @("cloudformation", "validate-template", "--template-body", "file://$serviceTemplate")

$existing = & aws cloudformation describe-stacks --stack-name $StackName --profile $Profile --region $Region --query "Stacks[0].StackStatus" --output text --no-cli-pager 2>&1
$foundationExists = $LASTEXITCODE -eq 0
if ($foundationExists -and (($existing | Out-String).Trim() -notin @("CREATE_COMPLETE", "UPDATE_COMPLETE"))) { throw "Foundation stack '$StackName' exists in status $(($existing | Out-String).Trim()); inspect it before resuming." }
if (-not $foundationExists -and (($existing | Out-String) -notmatch "does not exist")) { throw "Could not safely determine whether stack '$StackName' already exists: $(($existing | Out-String).Trim())" }
$serviceStackName = "reflex-service"
$existingService = & aws cloudformation describe-stacks --stack-name $serviceStackName --profile $Profile --region $Region --query "Stacks[0].StackStatus" --output text --no-cli-pager 2>&1
$serviceExists = $LASTEXITCODE -eq 0
if ($serviceExists -and -not $UpdateService) { throw "Stack '$serviceStackName' already exists. Pass -UpdateService to deploy a new tested image to the existing stack." }
if ($serviceExists -and (($existingService | Out-String).Trim() -notin @("CREATE_COMPLETE", "UPDATE_COMPLETE"))) { throw "Service stack '$serviceStackName' is in status $(($existingService | Out-String).Trim()); inspect it before updating." }
if (-not $serviceExists -and $UpdateService) { throw "-UpdateService was supplied but stack '$serviceStackName' does not exist." }
if (-not $serviceExists -and (($existingService | Out-String) -notmatch "does not exist")) { throw "Could not safely determine whether stack '$serviceStackName' already exists: $(($existingService | Out-String).Trim())" }

$sourceZip = Join-Path ([IO.Path]::GetTempPath()) "reflex-source-$runTag.zip"
$requestJson = Join-Path ([IO.Path]::GetTempPath()) "reflex-service-$runTag.json"
try {
    & $python (Join-Path $root "backend\scripts\package_aws_source.py") --output $sourceZip
    if ($LASTEXITCODE -ne 0) { throw "Could not create the allowlisted AWS source archive." }
    $sourceBundleHash = (Get-FileHash -LiteralPath $sourceZip -Algorithm SHA256).Hash.ToLowerInvariant()

    if ($foundationExists) {
        Write-Host "Reusing the already-verified foundation stack '$StackName'."
    } else {
        Write-Host "Creating the single-region build/network foundation in $Region..."
        $null = Invoke-AwsJson -AwsArgs @("cloudformation", "create-stack", "--stack-name", $StackName, "--template-body", "file://$template", "--capabilities", "CAPABILITY_NAMED_IAM", "--on-failure", "ROLLBACK")
        $foundationStatus = "CREATE_IN_PROGRESS"
        for ($attempt = 0; $attempt -lt 90; $attempt++) {
            Start-Sleep -Seconds 10
            $foundationStatus = Invoke-AwsRaw -AwsArgs @("cloudformation", "describe-stacks", "--stack-name", $StackName, "--query", "Stacks[0].StackStatus", "--output", "text")
            if ($foundationStatus -eq "CREATE_COMPLETE") { break }
            if ($foundationStatus -match "ROLLBACK|FAILED|DELETE_COMPLETE") { throw "AWS foundation stack ended in $foundationStatus. Inspect its CloudFormation events before retrying." }
        }
        if ($foundationStatus -ne "CREATE_COMPLETE") { throw "Timed out waiting for the foundation stack; last status was $foundationStatus." }
    }

    $stack = Invoke-AwsJson -AwsArgs @("cloudformation", "describe-stacks", "--stack-name", $StackName)
    $outputs = @{}
    foreach ($item in $stack.Stacks[0].Outputs) { $outputs[$item.OutputKey] = $item.OutputValue }
    $buildTag = "reflex-$runTag"
    if ($ExistingImageTag) {
        if ($ExistingImageTag -notmatch '^reflex-[0-9tz]+$' -or -not $ExistingBuildId -or $ExpectedSourceSha256 -notmatch '^[0-9a-f]{64}$') { throw "Reusing an image requires a valid ExistingImageTag, ExistingBuildId, and ExpectedSourceSha256." }
        if ($sourceBundleHash -ne $ExpectedSourceSha256) { throw "Current allowlisted source hash does not match the already-tested build. Refusing to reuse the image." }
        $verifiedBuild = Invoke-AwsJson -AwsArgs @("codebuild", "batch-get-builds", "--ids", $ExistingBuildId)
        if ($verifiedBuild.builds.Count -ne 1 -or $verifiedBuild.builds[0].buildStatus -ne "SUCCEEDED" -or $verifiedBuild.builds[0].projectName -ne $outputs.ImageBuildProject) { throw "The specified CodeBuild run is not a successful build of this project's image builder." }
        $buildId = $ExistingBuildId
        $buildTag = $ExistingImageTag
        Write-Host "Reusing the verified CodeBuild image $buildTag (source sha256 $sourceBundleHash)."
    } else {
        $null = Invoke-AwsRaw -AwsArgs @("s3", "cp", $sourceZip, "s3://$($outputs.SourceBucketName)/build/source.zip", "--only-show-errors")
        Write-Host "Private source bundle uploaded; the S3 lifecycle expires it after one day. Starting the remote image build..."
        $build = Invoke-AwsJson -AwsArgs @("codebuild", "start-build", "--project-name", $outputs.ImageBuildProject, "--environment-variables-override", "name=IMAGE_TAG,value=$buildTag,type=PLAINTEXT")
        $buildId = $build.build.id
        $buildStatus = "IN_PROGRESS"
        for ($attempt = 0; $attempt -lt 140; $attempt++) {
            Start-Sleep -Seconds 15
            $statusResponse = Invoke-AwsJson -AwsArgs @("codebuild", "batch-get-builds", "--ids", $buildId)
            $buildStatus = $statusResponse.builds[0].buildStatus
            if ($buildStatus -eq "SUCCEEDED") { break }
            if ($buildStatus -in @("FAILED", "FAULT", "STOPPED", "TIMED_OUT")) { throw "Remote image build ended in $buildStatus. Inspect the CodeBuild log group before retrying." }
        }
        if ($buildStatus -ne "SUCCEEDED") { throw "Timed out waiting for the CodeBuild image build; last status was $buildStatus." }
    }
    $imageDigest = Invoke-AwsRaw -AwsArgs @("ecr", "describe-images", "--repository-name", "reflex/inspection", "--image-ids", "imageTag=$buildTag", "--query", "imageDetails[0].imageDigest", "--output", "text")
    if (-not $imageDigest.StartsWith("sha256:")) { throw "CodeBuild succeeded but the expected immutable ECR image digest was not found." }

    $serviceParameters = @(
        @{ ParameterKey = "ImageUri"; ParameterValue = "$($outputs.ImageRepositoryUri):$buildTag" },
        @{ ParameterKey = "BuildTag"; ParameterValue = $buildTag },
        @{ ParameterKey = "ClusterName"; ParameterValue = $outputs.ClusterName },
        @{ ParameterKey = "ExecutionRoleArn"; ParameterValue = $outputs.ExecutionRoleArn },
        @{ ParameterKey = "ExpressInfrastructureRoleArn"; ParameterValue = $outputs.ExpressInfrastructureRoleArn },
        @{ ParameterKey = "AppLogGroupName"; ParameterValue = $outputs.AppLogGroupName },
        @{ ParameterKey = "PublicSubnets"; ParameterValue = $outputs.PublicSubnets }
    )
    $serializedParameters = ConvertTo-Json -InputObject $serviceParameters -Depth 6
    [IO.File]::WriteAllText($requestJson, $serializedParameters, [Text.UTF8Encoding]::new($false))

    if ($UpdateService) {
        Write-Host "Updating the existing bounded ECS Express service to the newly tested image..."
        $null = Invoke-AwsJson -AwsArgs @("cloudformation", "update-stack", "--stack-name", $serviceStackName, "--template-body", "file://$serviceTemplate", "--parameters", "file://$requestJson")
        $serviceStackStatus = "UPDATE_IN_PROGRESS"
        $completedServiceStatus = "UPDATE_COMPLETE"
    } else {
        Write-Host "Creating one bounded ECS Express service (one task maximum) with HTTPS ingress..."
        $null = Invoke-AwsJson -AwsArgs @("cloudformation", "create-stack", "--stack-name", $serviceStackName, "--template-body", "file://$serviceTemplate", "--parameters", "file://$requestJson", "--on-failure", "ROLLBACK")
        $serviceStackStatus = "CREATE_IN_PROGRESS"
        $completedServiceStatus = "CREATE_COMPLETE"
    }
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        Start-Sleep -Seconds 10
        $serviceStackStatus = Invoke-AwsRaw -AwsArgs @("cloudformation", "describe-stacks", "--stack-name", $serviceStackName, "--query", "Stacks[0].StackStatus", "--output", "text")
        if ($serviceStackStatus -eq $completedServiceStatus) { break }
        if ($serviceStackStatus -match "ROLLBACK|FAILED|DELETE_COMPLETE") { throw "ECS Express service stack ended in $serviceStackStatus. Inspect its CloudFormation events before retrying." }
    }
    if ($serviceStackStatus -ne $completedServiceStatus) { throw "Timed out waiting for the ECS Express service; last status was $serviceStackStatus." }
    $serviceStack = Invoke-AwsJson -AwsArgs @("cloudformation", "describe-stacks", "--stack-name", $serviceStackName)
    $serviceOutputs = @{}
    foreach ($item in $serviceStack.Stacks[0].Outputs) { $serviceOutputs[$item.OutputKey] = $item.OutputValue }
    $serviceArn = $serviceOutputs.ServiceArn
    $endpoint = [string]$serviceOutputs.Endpoint
    if (-not $endpoint.StartsWith("https://")) { $endpoint = "https://$endpoint" }
    if (-not $serviceArn -or -not $endpoint.StartsWith("https://")) { throw "Service stack completed without a valid endpoint and ARN output." }

    $proofPath = Join-Path $root "results\aws-smoke-$runTag.json"
    & $python (Join-Path $root "backend\scripts\smoke.py") --api-base $endpoint --expect-aws --proof-file $proofPath
    if ($LASTEXITCODE -ne 0) { throw "The remote OpenCV smoke test failed. The foundation and service remain for diagnosis; use destroy.ps1 after review if needed." }
    $proof = Get-Content -LiteralPath $proofPath -Raw | ConvertFrom-Json

    $cloudEvent = $null
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $logs = Invoke-AwsJson -AwsArgs @("logs", "filter-log-events", "--log-group-name", $outputs.AppLogGroupName, "--filter-pattern", $proof.request_id)
        foreach ($entry in $logs.events) {
            try {
                $logMessage = [string]$entry.message
                $jsonStart = $logMessage.IndexOf("{")
                if ($jsonStart -ge 0) { $candidate = $logMessage.Substring($jsonStart) | ConvertFrom-Json } else { continue }
                if ($candidate.event -eq "inspection_completed") { $cloudEvent = $candidate; break }
            } catch { }
        }
        if ($cloudEvent) { break }
        Start-Sleep -Seconds 5
    }
    if (-not $cloudEvent) { throw "The synthetic request succeeded, but its correlated CloudWatch event did not appear." }
    if ($proof.build_revision -ne $buildTag -or $cloudEvent.request_id -ne $proof.request_id -or $cloudEvent.inspection_id -ne $proof.inspection_id -or $cloudEvent.opencv_version -notlike "5.*" -or $cloudEvent.agent_tools -notcontains "inspect_crop" -or $cloudEvent.decision -ne $proof.decision) {
        throw "The CloudWatch event did not match the same OpenCV 5 request and crop action; do not claim cloud proof."
    }
    $evidence = @{ smoke = $proof; cloudwatch = $cloudEvent; source_bundle_sha256 = $sourceBundleHash; image_tag = $buildTag; image_digest = $imageDigest; codebuild_id = $buildId; service_status = $serviceStackStatus; region = $Region; task_count_limit = 1; inspection_retention_days = 1; foundation_stack = $StackName; service_stack = $serviceStackName }
    $evidencePath = Join-Path $root "results\aws-evidence-$runTag.json"
    $evidence | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $evidencePath -Encoding utf8
    Write-Host "Verified endpoint: $endpoint"
    Write-Host "Verified CloudWatch event for the same request ID and inspection ID. Evidence: $evidencePath"
    Write-Host "The public demo accepts images; its page warns users to submit synthetic images only. Do not upload private or production imagery."
    Write-Host "This service uses billable Fargate and load-balancer resources. Review billing and run infra/aws/destroy.ps1 when the public demo is no longer needed."
}
finally {
    if (Test-Path -LiteralPath $sourceZip -PathType Leaf) { Remove-Item -LiteralPath $sourceZip -Force }
    if (Test-Path -LiteralPath $requestJson -PathType Leaf) { Remove-Item -LiteralPath $requestJson -Force }
}
