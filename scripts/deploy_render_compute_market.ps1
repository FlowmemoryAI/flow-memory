[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$EnvFile = '.env.compute-market.live',

    [Parameter()]
    [string]$RenderApiKey = '',

    [Parameter()]
    [string]$RenderOwnerId = '',

    [Parameter()]
    [switch]$AllowFreePlans
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }
$renderHelper = Join-Path $PSScriptRoot 'deploy_compute_market_render_level1.py'

function Write-Status {
    param([string]$Status, [hashtable]$Fields)
    $ordered = [ordered]@{ status = $Status }
    foreach ($key in $Fields.Keys) { $ordered[$key] = $Fields[$key] }
    $ordered | ConvertTo-Json -Depth 8
}

if (-not (Test-Path -LiteralPath $renderHelper)) {
    Write-Status -Status 'failed_deployment' -Fields @{
        reason = 'render_helper_missing'
        missing_values = @('scripts/deploy_compute_market_render_level1.py')
    }
    exit 10
}

if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Status -Status 'failed_deployment' -Fields @{
        reason = 'env_file_missing'
        missing_values = @($envPath)
    }
    exit 11
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    Write-Status -Status 'failed_deployment' -Fields @{
        reason = 'python_missing'
        missing_values = @('python')
    }
    exit 12
}
$pythonPath = $pythonCommand.Source



if (-not [string]::IsNullOrWhiteSpace($RenderApiKey)) {
    [Environment]::SetEnvironmentVariable('RENDER_API_KEY', $RenderApiKey, 'Process')
}
if (-not [string]::IsNullOrWhiteSpace($RenderOwnerId)) {
    [Environment]::SetEnvironmentVariable('RENDER_OWNER_ID', $RenderOwnerId, 'Process')
}
if ($AllowFreePlans) {
    [Environment]::SetEnvironmentVariable('RENDER_ALLOW_FREE_PLANS', 'true', 'Process')
}

& $pythonPath $renderHelper --env-file $envPath
exit $LASTEXITCODE
