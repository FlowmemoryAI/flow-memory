[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$EnvFile = '.env.compute-market.live',

    [Parameter()]
    [string]$PublicApiUrl = '',

    [Parameter()]
    [switch]$RunLiveIntegrationTests,

    [Parameter()]
    [ValidateSet('auto', 'validate-only')]
    [string]$Mode = 'auto'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }
$composePath = Join-Path $repoRoot 'docker-compose.compute-market.yml'
$smokeScript = Join-Path $PSScriptRoot 'smoke_compute_market_public.ps1'
$renderBlueprintPath = Join-Path $repoRoot 'render.yaml'
$renderHelper = Join-Path $PSScriptRoot 'deploy_compute_market_render_level1.py'

function Write-Status {
    param([string]$Status, [hashtable]$Fields)
    $ordered = [ordered]@{ status = $Status }
    foreach ($key in ($Fields.Keys | Sort-Object)) {
        $ordered[$key] = $Fields[$key]
    }
    $ordered | ConvertTo-Json -Depth 8
}

function Read-EnvFile {
    param([Parameter(Mandatory = $true)] [string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Environment file not found: $Path"
    }

    $values = [ordered]@{}
    foreach ($rawLine in [System.IO.File]::ReadLines($Path)) {
        $line = $rawLine.Trim()
        if ($line.Length -eq 0 -or $line.StartsWith('#') -or -not $line.Contains('=')) { continue }
        $parts = $line.Split('=', 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$key] = $value
    }
    return $values
}

function Set-EnvForProcess {
    param([hashtable]$Values)
    foreach ($key in $Values.Keys) {
        [Environment]::SetEnvironmentVariable([string]$key, [string]$Values[$key], 'Process')
    }
}

function Test-CommandAvailable {
    param([Parameter(Mandatory = $true)] [string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}
function Get-PublicUrlBlockReason {
    param([Parameter(Mandatory = $true)] [string]$Url)

    try {
        $uri = [System.Uri]$Url
    }
    catch {
        return 'public_url_invalid'
    }

    $hostName = $uri.Host.Trim('[', ']').TrimEnd('.').ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($hostName)) {
        return 'public_url_missing_host'
    }
    if ($hostName -in @('localhost', 'ip6-localhost', 'ip6-loopback') -or $hostName.EndsWith('.local')) {
        return 'public_url_must_not_use_localhost'
    }
    if ($hostName -match '(^|\.)(yourdomain\.com|example\.com|example\.test|example\.invalid|test|invalid)$' -or $hostName -match '<your-domain>|changeme') {
        return 'public_url_placeholder_not_allowed'
    }

    $address = $null
    if (-not [System.Net.IPAddress]::TryParse($hostName, [ref]$address)) {
        return ''
    }
    if ([System.Net.IPAddress]::IsLoopback($address)) {
        return 'public_url_must_use_global_host'
    }

    $bytes = $address.GetAddressBytes()
    if ($address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) {
        if ($bytes[0] -eq 10) { return 'public_url_must_use_global_host' }
        if ($bytes[0] -eq 127) { return 'public_url_must_use_global_host' }
        if ($bytes[0] -eq 169 -and $bytes[1] -eq 254) { return 'public_url_must_use_global_host' }
        if ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) { return 'public_url_must_use_global_host' }
        if ($bytes[0] -eq 192 -and $bytes[1] -eq 168) { return 'public_url_must_use_global_host' }
        if ($bytes[0] -eq 0) { return 'public_url_must_use_global_host' }
    }
    elseif ($address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetworkV6) {
        if ($address.IsIPv6LinkLocal -or $address.IsIPv6SiteLocal -or $address.IsIPv6Multicast) {
            return 'public_url_must_use_global_host'
        }
        if ($bytes[0] -eq 0 -and $bytes[15] -le 1) { return 'public_url_must_use_global_host' }
        if (($bytes[0] -band 254) -eq 252) { return 'public_url_must_use_global_host' }
    }

    return ''
}
function Get-EnvValueOrDefault {
    param(
        [Parameter(Mandatory = $true)] $Values,
        [Parameter(Mandatory = $true)] [string]$Key,
        [Parameter()] [string]$Default = ''
    )
    if ($Values.Contains($Key)) {
        return [string]$Values[$Key]
    }
    return $Default
}



function ConvertTo-ProcessArgument {
    param([Parameter(Mandatory = $true)] [AllowEmptyString()] [string]$Argument)

    if ($Argument.Length -eq 0) { return '""' }
    if ($Argument -notmatch '[\s"]') { return $Argument }

    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($char in $Argument.ToCharArray()) {
        if ($char -eq '\') {
            $backslashes += 1
            continue
        }
        if ($char -eq '"') {
            if ($backslashes -gt 0) { [void]$builder.Append(('\' * ($backslashes * 2))) }
            [void]$builder.Append('\"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append(('\' * $backslashes))
            $backslashes = 0
        }
        [void]$builder.Append($char)
    }
    if ($backslashes -gt 0) { [void]$builder.Append(('\' * ($backslashes * 2))) }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function ConvertTo-ProcessArguments {
    param([Parameter(Mandatory = $true)] [string[]]$ArgumentList)

    return (($ArgumentList | ForEach-Object { ConvertTo-ProcessArgument -Argument ([string]$_) }) -join ' ')
}

function Invoke-ExternalQuiet {
    param(
        [Parameter(Mandatory = $true)] [string]$FilePath,
        [Parameter(Mandatory = $true)] [string[]]$ArgumentList,
        [Parameter()] [string]$WorkingDirectory = $repoRoot
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = ConvertTo-ProcessArguments -ArgumentList $ArgumentList
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    return @{ ExitCode = $process.ExitCode; Stdout = $stdout; Stderr = $stderr }
}

$requiredKeys = @(
    'FLOW_MEMORY_API_KEY',
    'FLOW_MEMORY_API_KEY_SCOPES',
    'FLOW_MEMORY_COMPUTE_DATABASE_URL',
    'FLOW_MEMORY_COMPUTE_REDIS_URL',
    'FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI',
    'FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION'
    'FLOW_MEMORY_COMPUTE_POSTGRES_BACKUP_POLICY_URI',
    'FLOW_MEMORY_COMPUTE_POSTGRES_RESTORE_DRILL_URI',
    'FLOW_MEMORY_COMPUTE_POSTGRES_BLUE_GREEN_REHEARSAL_URI'
    'FLOW_MEMORY_COMPUTE_REDIS_LIMITER_TEST_URI',
    'FLOW_MEMORY_COMPUTE_REDIS_CIRCUIT_BREAKER_TEST_URI',
    'FLOW_MEMORY_COMPUTE_REDIS_MULTI_INSTANCE_TEST_URI',
    'FLOW_MEMORY_COMPUTE_REDIS_DASHBOARD_URI'
)

$placeholderPattern = 'CHANGEME|<[^>]*>|<required>|<your-domain>|yourdomain\.com|api\.yourdomain\.com|<managed_postgres_url>|<managed_redis_url>|<audit_export_uri>|managed-postgres-host|managed-redis-host|high-entropy-api-key'
$weakApiKeys = @('api-key', 'dev-key', 'prod-key', 'test', 'secret', 'password')
$envValues = Read-EnvFile -Path $envPath
$renderApiKey = [Environment]::GetEnvironmentVariable('RENDER_API_KEY', 'Process')
if ([string]::IsNullOrWhiteSpace($renderApiKey)) {
    foreach ($scope in @('User', 'Machine')) {
        $candidate = [Environment]::GetEnvironmentVariable('RENDER_API_KEY', $scope)
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            $renderApiKey = $candidate
            [Environment]::SetEnvironmentVariable('RENDER_API_KEY', $candidate, 'Process')
            break
        }
    }
}
if (-not [string]::IsNullOrWhiteSpace($renderApiKey) -and $renderApiKey -match $placeholderPattern) {
    Write-Status -Status 'blocked_missing_render_auth' -Fields @{
        public_url = ''
        missing_values = @('RENDER_API_KEY')
    }
    exit 20
}

$renderOwnerId = [Environment]::GetEnvironmentVariable('RENDER_OWNER_ID', 'Process')
if (
    $Mode -eq 'auto' -and
    (Test-Path -LiteralPath $renderBlueprintPath) -and
    (Test-Path -LiteralPath $renderHelper)
) {
    $render = Invoke-ExternalQuiet -FilePath 'python' -ArgumentList @($renderHelper, '--env-file', $envPath)
    if (-not [string]::IsNullOrWhiteSpace($render.Stdout)) {
        [Console]::Out.Write($render.Stdout)
    }
    exit $render.ExitCode
}
$missing = New-Object System.Collections.Generic.List[string]
$placeholders = New-Object System.Collections.Generic.List[string]
foreach ($key in $requiredKeys) {
    if (-not $envValues.Contains($key) -or [string]::IsNullOrWhiteSpace([string]$envValues[$key])) {
        $missing.Add($key)
        continue
    }
    if ([string]$envValues[$key] -match $placeholderPattern) {
        $placeholders.Add($key)
    }
}
if (
    $envValues.Contains('FLOW_MEMORY_API_KEY') -and
    $weakApiKeys -contains ([string]$envValues['FLOW_MEMORY_API_KEY']).Trim().ToLowerInvariant() -and
    -not $placeholders.Contains('FLOW_MEMORY_API_KEY')
) {
    $placeholders.Add('FLOW_MEMORY_API_KEY')
}
if ($envValues.Contains('RENDER_KEYVALUE_IP_ALLOWLIST') -and [string]$envValues['RENDER_KEYVALUE_IP_ALLOWLIST'] -match $placeholderPattern) {
    $placeholders.Add('RENDER_KEYVALUE_IP_ALLOWLIST')
}
if ([string]::IsNullOrWhiteSpace($PublicApiUrl) -and $envValues.Contains('FLOW_MEMORY_PUBLIC_API_URL')) {
    $PublicApiUrl = [string]$envValues['FLOW_MEMORY_PUBLIC_API_URL']
}
if (-not [string]::IsNullOrWhiteSpace($PublicApiUrl)) {
    if ($PublicApiUrl -match $placeholderPattern) {
        $placeholders.Add('FLOW_MEMORY_PUBLIC_API_URL')
    }
    elseif (-not $PublicApiUrl.StartsWith('https://')) {
        Write-Status -Status 'blocked_invalid_public_url' -Fields @{
            public_url = $PublicApiUrl
            required_action = 'FLOW_MEMORY_PUBLIC_API_URL/ PublicApiUrl must be an https:// URL.'
        }
        exit 14
    }
    else {
        $publicUrlBlockReason = Get-PublicUrlBlockReason -Url $PublicApiUrl
        if (-not [string]::IsNullOrWhiteSpace($publicUrlBlockReason)) {
            Write-Status -Status 'blocked_invalid_public_url' -Fields @{
                public_url = $PublicApiUrl
                reason = $publicUrlBlockReason
                required_action = 'FLOW_MEMORY_PUBLIC_API_URL/ PublicApiUrl must be a real public HTTPS endpoint.'
            }
            exit 14
        }
    }
}


$renderManagedPrerequisites = New-Object System.Collections.Generic.List[string]
$renderManagedPrerequisites.Add('RENDER_API_KEY')
if ($placeholders -contains 'FLOW_MEMORY_COMPUTE_REDIS_URL') {
    $renderManagedPrerequisites.Add('RENDER_KEYVALUE_IP_ALLOWLIST')
}

if ($missing.Count -gt 0 -or $placeholders.Count -gt 0) {
    $renderManagedPlaceholders = @(
        $placeholders | Where-Object {
            $_ -eq 'FLOW_MEMORY_COMPUTE_DATABASE_URL' -or $_ -eq 'FLOW_MEMORY_COMPUTE_REDIS_URL'
        }
    )
    $onlyRenderManagedPlaceholders = (
        (Test-Path -LiteralPath $renderBlueprintPath) -and
        $missing.Count -eq 0 -and
        $placeholders.Count -eq $renderManagedPlaceholders.Count
    )
    if ($onlyRenderManagedPlaceholders) {
        Write-Status -Status 'blocked_missing_deployment_target' -Fields @{
            public_url = ''
            deployment_target = 'render'
            missing_values = @($renderManagedPrerequisites)
            placeholder_values = @($placeholders)
        }
        exit 13
    }
    Write-Status -Status 'blocked_missing_values' -Fields @{
        public_url = ''
        missing_values = @($missing)
        placeholder_values = @($placeholders)
    }
    exit 2
}

$auditExportUri = [string]$envValues['FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI']
if (-not $auditExportUri.StartsWith('s3://')) {
    Write-Status -Status 'blocked_missing_audit_object_storage' -Fields @{
        public_url = ''
        audit_export_uri = $auditExportUri
        required_action = 'FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI must be an s3:// Object Lock bucket/prefix.'
    }
    exit 14
}

$postgresOperationalEvidenceKeys = @(
    'FLOW_MEMORY_COMPUTE_POSTGRES_BACKUP_POLICY_URI',
    'FLOW_MEMORY_COMPUTE_POSTGRES_RESTORE_DRILL_URI',
    'FLOW_MEMORY_COMPUTE_POSTGRES_BLUE_GREEN_REHEARSAL_URI'
)
$invalidPostgresEvidenceUris = New-Object System.Collections.Generic.List[hashtable]
foreach ($key in $postgresOperationalEvidenceKeys) {
    $value = [string]$envValues[$key]
    if (-not ($value.StartsWith('https://') -or $value.StartsWith('s3://'))) {
        $scheme = ''
        if ($value.Contains('://')) {
            $scheme = $value.Split('://', 2)[0]
        }
        $invalidPostgresEvidenceUris.Add(@{
            key = $key
            actual = $scheme
            expected = 'https_or_s3'
        })
    }
}
if ($invalidPostgresEvidenceUris.Count -gt 0) {
    Write-Status -Status 'blocked_invalid_postgres_operational_evidence' -Fields @{
        public_url = ''
        invalid_values = @($invalidPostgresEvidenceUris)
        required_action = 'Managed Postgres backup/PITR policy, restore drill, and blue/green migration rehearsal evidence must be stored at https:// or s3:// URIs.'
    }
    exit 17
}

$redisOperationalEvidenceKeys = @(
    'FLOW_MEMORY_COMPUTE_REDIS_LIMITER_TEST_URI',
    'FLOW_MEMORY_COMPUTE_REDIS_CIRCUIT_BREAKER_TEST_URI',
    'FLOW_MEMORY_COMPUTE_REDIS_MULTI_INSTANCE_TEST_URI',
    'FLOW_MEMORY_COMPUTE_REDIS_DASHBOARD_URI'
)
$invalidRedisEvidenceUris = New-Object System.Collections.Generic.List[hashtable]
foreach ($key in $redisOperationalEvidenceKeys) {
    $value = [string]$envValues[$key]
    if (-not ($value.StartsWith('https://') -or $value.StartsWith('s3://'))) {
        $scheme = ''
        if ($value.Contains('://')) {
            $scheme = $value.Split('://', 2)[0]
        }
        $invalidRedisEvidenceUris.Add(@{
            key = $key
            actual = $scheme
            expected = 'https_or_s3'
        })
    }
}
if ($invalidRedisEvidenceUris.Count -gt 0) {
    Write-Status -Status 'blocked_invalid_redis_operational_evidence' -Fields @{
        public_url = ''
        invalid_values = @($invalidRedisEvidenceUris)
        required_action = 'Managed Redis limiter, circuit-breaker, multi-instance shared-state, and dashboard evidence must be stored at https:// or s3:// URIs.'
    }
    exit 17
}

$redisUri = [string]$envValues['FLOW_MEMORY_COMPUTE_REDIS_URL']
if (-not $redisUri.StartsWith('rediss://')) {
    $redisScheme = ''
    if ($redisUri.Contains('://')) {
        $redisScheme = $redisUri.Split('://', 2)[0]
    }
    Write-Status -Status 'blocked_insecure_redis' -Fields @{
        public_url = ''
        redis_url_scheme = $redisScheme
        required_action = 'FLOW_MEMORY_COMPUTE_REDIS_URL must be a TLS rediss:// managed Redis URL.'
    }
    exit 15
}
$jwtSecret = (Get-EnvValueOrDefault -Values $envValues -Key 'FLOW_MEMORY_API_JWT_HS256_SECRET').Trim()
$jwtIssuer = (Get-EnvValueOrDefault -Values $envValues -Key 'FLOW_MEMORY_API_JWT_ISSUER').Trim()
$jwtAudience = (Get-EnvValueOrDefault -Values $envValues -Key 'FLOW_MEMORY_API_JWT_AUDIENCE').Trim()
$jwtLeewaySeconds = (Get-EnvValueOrDefault -Values $envValues -Key 'FLOW_MEMORY_API_JWT_LEEWAY_SECONDS' -Default '60').Trim()
if ([string]::IsNullOrWhiteSpace($jwtLeewaySeconds)) {
    $jwtLeewaySeconds = '60'
}
$gatewayJwtConfigured = (
    -not [string]::IsNullOrWhiteSpace($jwtSecret) -or
    -not [string]::IsNullOrWhiteSpace($jwtIssuer) -or
    -not [string]::IsNullOrWhiteSpace($jwtAudience)
)
if ($gatewayJwtConfigured) {
    $gatewayPlaceholderPattern = "$placeholderPattern|high-entropy"
    $jwtMissing = New-Object System.Collections.Generic.List[string]
    if ([string]::IsNullOrWhiteSpace($jwtSecret) -or $jwtSecret -match $gatewayPlaceholderPattern) {
        $jwtMissing.Add('FLOW_MEMORY_API_JWT_HS256_SECRET')
    }
    if ([string]::IsNullOrWhiteSpace($jwtIssuer) -or $jwtIssuer -match $gatewayPlaceholderPattern) {
        $jwtMissing.Add('FLOW_MEMORY_API_JWT_ISSUER')
    }
    if ([string]::IsNullOrWhiteSpace($jwtAudience) -or $jwtAudience -match $gatewayPlaceholderPattern) {
        $jwtMissing.Add('FLOW_MEMORY_API_JWT_AUDIENCE')
    }
    if ($jwtMissing.Count -gt 0) {
        Write-Status -Status 'blocked_incomplete_gateway_jwt' -Fields @{
            public_url = ''
            missing_values = @($jwtMissing)
            required_action = 'Configure FLOW_MEMORY_API_JWT_HS256_SECRET, FLOW_MEMORY_API_JWT_ISSUER, and FLOW_MEMORY_API_JWT_AUDIENCE together for public gateway JWT auth.'
        }
        exit 16
    }
    if ($jwtSecret.Length -lt 32) {
        Write-Status -Status 'blocked_weak_gateway_jwt_secret' -Fields @{
            public_url = ''
            invalid_value = 'FLOW_MEMORY_API_JWT_HS256_SECRET'
            required_action = 'Use a high-entropy gateway JWT HS256 secret with at least 32 characters.'
        }
        exit 16
    }
    if (-not $jwtIssuer.StartsWith('https://')) {
        Write-Status -Status 'blocked_insecure_gateway_jwt_issuer' -Fields @{
            public_url = ''
            invalid_value = 'FLOW_MEMORY_API_JWT_ISSUER'
            required_scheme = 'https'
            required_action = 'Use an https:// issuer URL for public gateway JWT auth.'
        }
        exit 16
    }
    $jwtLeeway = 0
    if (-not [int]::TryParse($jwtLeewaySeconds, [ref]$jwtLeeway) -or $jwtLeeway -lt 0) {
        Write-Status -Status 'blocked_invalid_gateway_jwt_leeway' -Fields @{
            public_url = ''
            invalid_value = 'FLOW_MEMORY_API_JWT_LEEWAY_SECONDS'
            required_action = 'Set FLOW_MEMORY_API_JWT_LEEWAY_SECONDS to a non-negative integer.'
        }
        exit 16
    }
}

$safetyExpectations = @{
    FLOW_MEMORY_API_REQUIRE_SCOPES = 'true'
    FLOW_MEMORY_API_JWT_REQUIRE_TENANT = 'true'
    FLOW_MEMORY_API_ENABLE_NONCE_CHECK = 'true'
    FLOW_MEMORY_API_NONCE_REPLAY_BACKEND = 'redis'
    FLOW_MEMORY_API_NONCE_FAIL_CLOSED = 'true'
    FLOW_MEMORY_API_NONCE_REQUIRE_TLS = 'true'
    FLOW_MEMORY_COMPUTE_MARKET_ENABLED = 'true'
    FLOW_MEMORY_COMPUTE_MARKET_MODE = 'production_planning'
    FLOW_MEMORY_COMPUTE_STORAGE_BACKEND = 'postgres'
    FLOW_MEMORY_COMPUTE_POSTGRES_SSL_MODE = 'require'
    FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION = 'true'
    FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION = 'true'
    FLOW_MEMORY_COMPUTE_MIGRATIONS_ENABLED = 'true'
    FLOW_MEMORY_COMPUTE_MIGRATIONS_AUTO_RUN = 'true'
    FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND = 'redis'
    FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND = 'redis'
    FLOW_MEMORY_COMPUTE_RATE_LIMIT_FAIL_CLOSED = 'true'
    FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_FAIL_CLOSED = 'true'
    FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED = 'true'
    FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED = 'false'
    FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED = 'false'
    FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED = 'false'
    FLOW_MEMORY_COMPUTE_AUDIT_REQUIRED = 'true'
    FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED = 'true'
    FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED = 'true'
    FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED = 'true'
    FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED = 'true'
    FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED = 'true'
    FLOW_MEMORY_COMPUTE_METRICS_ENABLED = 'true'
    FLOW_MEMORY_COMPUTE_TRACING_ENABLED = 'true'
    FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED = 'false'
    FLOW_MEMORY_COMPUTE_EXTERNAL_EXECUTION_ENABLED = 'false'
    FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED = 'false'
}

$forbiddenLevel1ConfiguredKeys = @(
    'FLOW_MEMORY_BILLING_STRIPE_SECRET_KEY',
    'FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_SECRET',
    'FLOW_MEMORY_BILLING_STRIPE_SUCCESS_URL',
    'FLOW_MEMORY_BILLING_STRIPE_CANCEL_URL',
    'FLOW_MEMORY_COMPUTE_SETTLEMENT_ENVIRONMENT',
    'FLOW_MEMORY_COMPUTE_SETTLEMENT_SECURITY_REVIEW_ID'
)

$badSafety = New-Object System.Collections.Generic.List[string]
foreach ($key in $safetyExpectations.Keys) {
    if (-not $envValues.Contains($key) -or ([string]$envValues[$key]).ToLowerInvariant() -ne $safetyExpectations[$key]) {
        $badSafety.Add($key)
    }
}
if ($badSafety.Count -gt 0) {
    Write-Status -Status 'blocked_invalid_safety_config' -Fields @{
        public_url = ''
        invalid_keys = @($badSafety)
    }
    exit 3
}

$forbiddenConfigured = New-Object System.Collections.Generic.List[string]
foreach ($key in $forbiddenLevel1ConfiguredKeys) {
    if ($envValues.Contains($key) -and -not [string]::IsNullOrWhiteSpace([string]$envValues[$key])) {
        $forbiddenConfigured.Add($key)
    }
}
if ($forbiddenConfigured.Count -gt 0) {
    Write-Status -Status 'blocked_forbidden_level1_config' -Fields @{
        public_url = ''
        forbidden_keys = @($forbiddenConfigured)
        expected = 'empty_for_level1'
    }
    exit 3
}

$observabilitySinkKeys = @(
    'FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL',
    'FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL',
    'FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL'
)
$missingObservabilitySinks = New-Object System.Collections.Generic.List[string]
foreach ($key in $observabilitySinkKeys) {
    if (-not $envValues.Contains($key) -or [string]::IsNullOrWhiteSpace([string]$envValues[$key])) {
        $missingObservabilitySinks.Add($key)
    }
    elseif (-not ([string]$envValues[$key]).StartsWith('https://')) {
        Write-Status -Status 'blocked_insecure_observability_sink' -Fields @{
            public_url = ''
            invalid_value = $key
            required_scheme = 'https'
        }
        exit 17
    }
}
if ($missingObservabilitySinks.Count -gt 0) {
    Write-Status -Status 'blocked_missing_observability_sink' -Fields @{
        public_url = ''
        missing_values = @($missingObservabilitySinks)
        required_action = 'Configure HTTPS alert webhook, error tracking webhook, and OTLP collector sinks before public Level 1 deployment.'
    }
    exit 17
}

Set-EnvForProcess -Values $envValues

$compose = Invoke-ExternalQuiet -FilePath 'docker' -ArgumentList @('compose', '--env-file', $envPath, '-f', $composePath, 'config')
if ($compose.ExitCode -ne 0) {
    Write-Status -Status 'failed_compose_config' -Fields @{
        public_url = ''
        exit_code = $compose.ExitCode
    }
    exit 4
}

$composeText = [string]$compose.Stdout
$composeChecks = @{
    storage_backend_postgres = 'FLOW_MEMORY_COMPUTE_STORAGE_BACKEND:\s+postgres'
    rate_limit_backend_redis = 'FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND:\s+redis'
    circuit_breaker_backend_redis = 'FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND:\s+redis'
    require_managed_redis = 'FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION:\s+"?true"?'
    dry_run_required_true = 'FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED:\s+"?true"?'
    live_settlement_false = 'FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED:\s+"?false"?'
    broadcast_false = 'FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED:\s+"?false"?'
    private_key_inputs_false = 'FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED:\s+"?false"?'
    external_provider_quotes_false = 'FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED:\s+"?false"?'
    external_provider_execution_false = 'FLOW_MEMORY_COMPUTE_EXTERNAL_EXECUTION_ENABLED:\s+"?false"?'
    redis_limiter_evidence_bound = 'FLOW_MEMORY_COMPUTE_REDIS_LIMITER_TEST_URI:\s+\S+'
    redis_circuit_evidence_bound = 'FLOW_MEMORY_COMPUTE_REDIS_CIRCUIT_BREAKER_TEST_URI:\s+\S+'
    redis_multi_instance_evidence_bound = 'FLOW_MEMORY_COMPUTE_REDIS_MULTI_INSTANCE_TEST_URI:\s+\S+'
    redis_dashboard_evidence_bound = 'FLOW_MEMORY_COMPUTE_REDIS_DASHBOARD_URI:\s+\S+'
}
$failedComposeChecks = New-Object System.Collections.Generic.List[string]
foreach ($name in $composeChecks.Keys) {
    if ($composeText -notmatch $composeChecks[$name]) { $failedComposeChecks.Add($name) }
}
if ($failedComposeChecks.Count -gt 0) {
    Write-Status -Status 'failed_compose_config_safety_checks' -Fields @{
        public_url = ''
        failed_checks = @($failedComposeChecks)
    }
    exit 5
}

if ($RunLiveIntegrationTests) {
    [Environment]::SetEnvironmentVariable('FLOW_MEMORY_TEST_POSTGRES_URL', [string]$envValues['FLOW_MEMORY_COMPUTE_DATABASE_URL'], 'Process')
    [Environment]::SetEnvironmentVariable('FLOW_MEMORY_TEST_REDIS_URL', [string]$envValues['FLOW_MEMORY_COMPUTE_REDIS_URL'], 'Process')
    $liveInfra = Invoke-ExternalQuiet -FilePath 'python' -ArgumentList @('scripts/validate_compute_market_live_infra.py')
    if ($liveInfra.ExitCode -ne 0) {
        Write-Status -Status 'failed_live_infra_validation' -Fields @{
            public_url = ''
            exit_code = $liveInfra.ExitCode
        }
        exit 6
    }
    $pytest = Invoke-ExternalQuiet -FilePath 'python' -ArgumentList @('-m', 'pytest', 'tests/test_compute_market_live_integration.py', '-q')
    if ($pytest.ExitCode -ne 0) {
        Write-Status -Status 'failed_live_integration_tests' -Fields @{
            public_url = ''
            exit_code = $pytest.ExitCode
        }
        exit 7
    }
}

if ($Mode -eq 'validate-only') {
    Write-Status -Status 'validated_not_deployed' -Fields @{
        public_url = $PublicApiUrl
        docker_compose_config = 'passed'
    }
    exit 0
}

$configuredTarget = ''
if (Test-Path -LiteralPath (Join-Path $repoRoot 'fly.toml')) { $configuredTarget = 'fly' }
elseif (Test-Path -LiteralPath (Join-Path $repoRoot 'railway.json')) { $configuredTarget = 'railway' }
elseif (Test-Path -LiteralPath (Join-Path $repoRoot 'render.yaml')) { $configuredTarget = 'render' }

if ($configuredTarget -eq 'fly' -and (Test-CommandAvailable 'flyctl')) {
    $secretArgs = New-Object System.Collections.Generic.List[string]
    $secretArgs.Add('secrets')
    $secretArgs.Add('set')
    foreach ($key in $requiredKeys + $safetyExpectations.Keys) {
        if ($envValues.Contains($key)) { $secretArgs.Add("$key=$($envValues[$key])") }
    }
    $secrets = Invoke-ExternalQuiet -FilePath 'flyctl' -ArgumentList $secretArgs.ToArray()
    if ($secrets.ExitCode -ne 0) {
        Write-Status -Status 'failed_fly_secrets' -Fields @{ public_url = ''; exit_code = $secrets.ExitCode }
        exit 7
    }
    $deploy = Invoke-ExternalQuiet -FilePath 'flyctl' -ArgumentList @('deploy', '--ha=false')
    if ($deploy.ExitCode -ne 0) {
        Write-Status -Status 'failed_fly_deploy' -Fields @{ public_url = ''; exit_code = $deploy.ExitCode }
        exit 8
    }
}
elseif ($configuredTarget -eq 'railway' -and (Test-CommandAvailable 'railway')) {
    $status = Invoke-ExternalQuiet -FilePath 'railway' -ArgumentList @('status')
    if ($status.ExitCode -ne 0) {
        Write-Status -Status 'blocked_railway_not_linked' -Fields @{ public_url = ''; deployment_target = 'railway' }
        exit 9
    }
    foreach ($key in $requiredKeys + $safetyExpectations.Keys) {
        if ($envValues.Contains($key)) {
            $varSet = Invoke-ExternalQuiet -FilePath 'railway' -ArgumentList @('variables', '--set', "$key=$($envValues[$key])")
            if ($varSet.ExitCode -ne 0) {
                Write-Status -Status 'failed_railway_variables' -Fields @{ public_url = ''; key = $key }
                exit 10
            }
        }
    }
    $deploy = Invoke-ExternalQuiet -FilePath 'railway' -ArgumentList @('up', '--detach')
    if ($deploy.ExitCode -ne 0) {
        Write-Status -Status 'failed_railway_deploy' -Fields @{ public_url = ''; exit_code = $deploy.ExitCode }
        exit 11
    }
}
elseif ($configuredTarget -eq 'render' -and (Test-CommandAvailable 'render')) {
    Write-Status -Status 'blocked_render_manual_service_creation_required' -Fields @{ public_url = ''; deployment_target = 'render' }
    exit 12
}
else {
    Write-Status -Status 'blocked_missing_deployment_target' -Fields @{
        public_url = ''
        configured_target = $configuredTarget
        docker_compose_config = 'passed'
    }
    exit 13
}

if ([string]::IsNullOrWhiteSpace($PublicApiUrl) -and $envValues.Contains('FLOW_MEMORY_PUBLIC_API_URL')) {
    $PublicApiUrl = [string]$envValues['FLOW_MEMORY_PUBLIC_API_URL']
}
if ([string]::IsNullOrWhiteSpace($PublicApiUrl)) {
    Write-Status -Status 'deployed_public_url_missing' -Fields @{ public_url = '' }
    exit 14
}

$smoke = Invoke-ExternalQuiet -FilePath 'powershell' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $smokeScript, '-ApiUrl', $PublicApiUrl, '-ApiKey', [string]$envValues['FLOW_MEMORY_API_KEY'], '-RequireImmutableAudit')
if ($smoke.ExitCode -ne 0) {
    Write-Status -Status 'failed_public_smoke_tests' -Fields @{ public_url = $PublicApiUrl; exit_code = $smoke.ExitCode }
    exit 15
}

Write-Status -Status 'public_level_1_live' -Fields @{
    public_url = $PublicApiUrl
    smoke = 'passed'
    docker_compose_config = 'passed'
}
