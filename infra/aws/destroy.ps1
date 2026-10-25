[CmdletBinding()]
param(
    [string]$Profile = "reflex-aws",
    [string]$Region = "ap-southeast-2",
    [string]$ConfirmStackNames
)

$ErrorActionPreference = "Stop"
$expected = "reflex-service,reflex-foundation"
if ($Region -ne "ap-southeast-2") { throw "REFLEX AWS resources are constrained to ap-southeast-2 (Sydney)." }
if ($ConfirmStackNames -cne $expected) { throw "Deletion requires -ConfirmStackNames '$expected'. No resources were changed." }

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

$null = Invoke-AwsRaw -AwsArgs @("sts", "get-caller-identity", "--query", "UserId", "--output", "text")
foreach ($stackName in @("reflex-service", "reflex-foundation")) {
    $status = & aws cloudformation describe-stacks --stack-name $stackName --profile $Profile --region $Region --query "Stacks[0].StackStatus" --output text --no-cli-pager 2>&1
    if ($LASTEXITCODE -ne 0) {
        if (($status | Out-String) -match "does not exist") { Write-Host "Stack '$stackName' is already absent."; continue }
        throw "Could not safely inspect '$stackName': $(($status | Out-String).Trim())"
    }
    if ($stackName -eq "reflex-foundation") {
        $bucket = & aws cloudformation describe-stacks --stack-name $stackName --profile $Profile --region $Region --query "Stacks[0].Outputs[?OutputKey=='SourceBucketName'].OutputValue | [0]" --output text --no-cli-pager 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Could not inspect the foundation stack's source bucket before deletion." }
        $bucket = ($bucket | Out-String).Trim()
        if ($bucket -and $bucket -ne "None") {
            $null = Invoke-AwsRaw -AwsArgs @("s3", "rm", "s3://$bucket/build/", "--recursive", "--only-show-errors")
        }
    }
    Write-Host "Deleting '$stackName' (current status $status)..."
    $null = Invoke-AwsRaw -AwsArgs @("cloudformation", "delete-stack", "--stack-name", $stackName)
    $complete = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        Start-Sleep -Seconds 10
        $latest = & aws cloudformation describe-stacks --stack-name $stackName --profile $Profile --region $Region --query "Stacks[0].StackStatus" --output text --no-cli-pager 2>&1
        if ($LASTEXITCODE -ne 0 -and (($latest | Out-String) -match "does not exist")) { $complete = $true; break }
        if ($LASTEXITCODE -eq 0 -and (($latest | Out-String).Trim() -match "DELETE_FAILED")) { throw "Deletion of '$stackName' failed. Inspect its CloudFormation events." }
    }
    if (-not $complete) { throw "Timed out waiting for '$stackName' deletion." }
}
Write-Host "Both REFLEX stacks are absent. The stack-managed log groups and contents are removed, and the ECR image/source bundle are deleted."
