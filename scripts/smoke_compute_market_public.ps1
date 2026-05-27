[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApiUrl,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApiKey
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$baseUrl = $ApiUrl.TrimEnd('/')
if (-not ($baseUrl -match '^https://')) {
    throw 'ApiUrl must be an https:// public URL for Level 1 smoke tests.'
}
function Add-NonceHeaders {
    param(
        [Parameter(Mandatory = $true)] [hashtable]$Headers,
        [Parameter(Mandatory = $true)] [string]$Label
    )

    $Headers['x-flow-memory-timestamp'] = [string][DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $Headers['x-flow-memory-nonce'] = "$Label-$([Guid]::NewGuid().ToString('N'))"
    return $Headers
}


function Read-HttpErrorBody {
    param([Parameter(Mandatory = $true)] $ErrorRecord)

    $response = $null
    if ($null -ne $ErrorRecord.Exception -and ($ErrorRecord.Exception.PSObject.Properties.Name -contains 'Response')) {
        $response = $ErrorRecord.Exception.Response
    }
    if ($null -eq $response) {
        $message = if ($null -ne $ErrorRecord.Exception) { $ErrorRecord.Exception.Message } else { [string]$ErrorRecord }
        return @{ StatusCode = 0; Body = $message }
    }

    if ($response.GetType().FullName -eq 'System.Net.Http.HttpResponseMessage') {
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        return @{ StatusCode = [int]$response.StatusCode; Body = $body }
    }

    $stream = $response.GetResponseStream()
    if ($null -eq $stream) {
        return @{ StatusCode = [int]$response.StatusCode; Body = '' }
    }

    $reader = New-Object System.IO.StreamReader($stream)
    try {
        return @{ StatusCode = [int]$response.StatusCode; Body = $reader.ReadToEnd() }
    }
    finally {
        $reader.Dispose()
    }
}

function Invoke-ComputeMarketRequest {
    param(
        [Parameter(Mandatory = $true)] [ValidateSet('GET', 'POST')] [string]$Method,
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [string]$Scopes,
        [Parameter()] [object]$Body,
        [Parameter()] [bool]$IncludeApiKey = $true
    )

    $headers = @{ 'x-flow-memory-scopes' = $Scopes }
    if ($IncludeApiKey) {
        $headers['x-flow-memory-api-key'] = $ApiKey
    }
    $headers = Add-NonceHeaders -Headers $headers -Label "$Method-$Path"

    $request = @{
        Uri = "$baseUrl$Path"
        Method = $Method
        Headers = $headers
        TimeoutSec = 90
    }

    if ($PSBoundParameters.ContainsKey('Body')) {
        $request['ContentType'] = 'application/json'
        $request['Body'] = ($Body | ConvertTo-Json -Depth 20 -Compress)
    }

    try {
        $response = Invoke-WebRequest @request
        $content = [string]$response.Content
        $json = $null
        if ($content.Trim().Length -gt 0) {
            $json = $content | ConvertFrom-Json
        }
        return @{ StatusCode = [int]$response.StatusCode; Json = $json; Body = $content }
    }
    catch {
        $errorResult = Read-HttpErrorBody -ErrorRecord $_
        $json = $null
        if ([string]$errorResult.Body -and ([string]$errorResult.Body).Trim().Length -gt 0) {
            try { $json = ([string]$errorResult.Body | ConvertFrom-Json) } catch { $json = $null }
        }
        return @{ StatusCode = [int]$errorResult.StatusCode; Json = $json; Body = [string]$errorResult.Body }
    }
}

function Assert-Status {
    param([hashtable]$Response, [int]$Expected, [string]$Name)
    if ([int]$Response.StatusCode -ne $Expected) {
        throw "$Name returned HTTP $($Response.StatusCode), expected $Expected."
    }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Get-DataField {
    param([object]$Json, [string]$Name)
    if ($null -eq $Json -or $null -eq $Json.data) { return $null }
    return $Json.data.$Name
}
$root = Invoke-WebRequest -Uri "$baseUrl/" -Method GET -TimeoutSec 90
$rootJson = $root.Content | ConvertFrom-Json
Assert-True ([int]$root.StatusCode -eq 200) 'root did not return HTTP 200.'
Assert-True ($rootJson.ok -eq $true) 'root did not return ok=true.'
Assert-True ($rootJson.data.service -eq 'Flow Memory Compute Market') 'root did not identify Flow Memory Compute Market.'

$health = Invoke-ComputeMarketRequest -Method GET -Path '/compute/health' -Scopes 'compute:read'
Assert-Status -Response $health -Expected 200 -Name 'health'
Assert-True (($health.Json.ok -eq $true) -or ((Get-DataField -Json $health.Json -Name 'ok') -eq $true)) 'health did not return ok=true.'

$readiness = Invoke-ComputeMarketRequest -Method GET -Path '/compute/readiness' -Scopes 'compute:read'
Assert-Status -Response $readiness -Expected 200 -Name 'readiness'
Assert-True (($readiness.Json.ok -eq $true) -or ((Get-DataField -Json $readiness.Json -Name 'ok') -eq $true)) 'readiness did not return ok=true.'
Assert-True ((Get-DataField -Json $readiness.Json -Name 'ready') -eq $true) 'readiness did not return ready=true.'

$readinessData = $readiness.Json.data
$storageBackend = $null
if ($null -ne $readinessData.storage) { $storageBackend = $readinessData.storage.backend }
if (-not $storageBackend -and $null -ne $readinessData.production_safety_defaults) { $storageBackend = $readinessData.production_safety_defaults.storage_backend }
$rateLimitBackend = $null
if ($null -ne $readinessData.production_safety_defaults) { $rateLimitBackend = $readinessData.production_safety_defaults.rate_limit_backend }
if (-not $rateLimitBackend -and $null -ne $readinessData.rate_limiter_status) { $rateLimitBackend = $readinessData.rate_limiter_status.backend }
$circuitBreakerBackend = $null
if ($null -ne $readinessData.production_safety_defaults) { $circuitBreakerBackend = $readinessData.production_safety_defaults.circuit_breaker_backend }
if (-not $circuitBreakerBackend -and $null -ne $readinessData.circuit_breaker_status) { $circuitBreakerBackend = $readinessData.circuit_breaker_status.backend }

Assert-True (($storageBackend -eq 'postgres') -or ($storageBackend -eq 'postgresql')) "readiness storage backend was '$storageBackend', expected postgres/postgresql."
Assert-True ($rateLimitBackend -eq 'redis') "readiness rate limit backend was '$rateLimitBackend', expected redis."
Assert-True ($circuitBreakerBackend -eq 'redis') "readiness circuit breaker backend was '$circuitBreakerBackend', expected redis."
Assert-True ($readinessData.production_safety_defaults.require_managed_redis_in_production -eq $true) 'readiness did not require managed Redis in production.'
$redisUrlScheme = $readinessData.production_safety_defaults.redis_url_scheme
$allowInternalRedis = $readinessData.production_safety_defaults.allow_internal_redis_in_production
$redisSchemeAllowed = ($redisUrlScheme -eq 'rediss') -or (($redisUrlScheme -eq 'redis') -and ($allowInternalRedis -eq $true))
Assert-True $redisSchemeAllowed "readiness Redis URL scheme was '$redisUrlScheme', expected rediss or explicitly allowed Render internal redis."

$planBody = @{
    task = 'public live Level 1 Flow Memory Compute Market smoke test'
    dry_run = $true
}
$plan = Invoke-ComputeMarketRequest -Method POST -Path '/compute/plan' -Scopes 'compute:plan' -Body $planBody
Assert-Status -Response $plan -Expected 200 -Name 'plan'
Assert-True (($plan.Json.ok -eq $true) -or ($plan.Json.data.compute_plan.ok -eq $true)) 'plan did not return ok=true.'
$computePlan = $plan.Json.data.compute_plan
Assert-True ($computePlan.dry_run_only -eq $true) 'plan did not return dry_run_only=true.'
Assert-True ($computePlan.funds_moved -eq $false) 'plan did not return funds_moved=false.'
Assert-True ($computePlan.broadcast_allowed -eq $false) 'plan did not return broadcast_allowed=false.'
Assert-True ($computePlan.private_key_required -eq $false) 'plan did not return private_key_required=false.'

$metricsHeaders = Add-NonceHeaders -Headers @{
    'x-flow-memory-api-key' = $ApiKey
    'x-flow-memory-scopes' = 'compute:read'
} -Label 'GET-/metrics'
$metrics = Invoke-WebRequest -Uri "$baseUrl/metrics" -Method GET -Headers $metricsHeaders -TimeoutSec 90
Assert-True ([int]$metrics.StatusCode -eq 200) 'Prometheus metrics did not return HTTP 200.'
Assert-True ([string]$metrics.Content -match 'compute_plan_requests_total') 'Prometheus metrics did not expose compute_plan_requests_total.'

$alerts = Invoke-ComputeMarketRequest -Method GET -Path '/compute/alerts' -Scopes 'compute:read'
Assert-Status -Response $alerts -Expected 200 -Name 'alerts'
Assert-True ($alerts.Json.ok -eq $true) 'alerts endpoint did not return ok=true.'

$telemetry = Invoke-ComputeMarketRequest -Method GET -Path '/compute/telemetry' -Scopes 'compute:read'
Assert-Status -Response $telemetry -Expected 200 -Name 'telemetry'
Assert-True ($telemetry.Json.ok -eq $true) 'telemetry endpoint did not return ok=true.'

$auditVerify = Invoke-ComputeMarketRequest -Method GET -Path '/compute/audit/verify' -Scopes 'compute:audit'
Assert-Status -Response $auditVerify -Expected 200 -Name 'audit verify'
Assert-True (($auditVerify.Json.ok -eq $true) -and ($auditVerify.Json.data.ok -eq $true)) 'audit verify did not return ok=true.'

$auditExport = Invoke-ComputeMarketRequest -Method GET -Path '/admin/audit/export' -Scopes 'compute:admin'
Assert-Status -Response $auditExport -Expected 200 -Name 'admin audit export'
$auditExporter = $auditExport.Json.data.audit_exporter_status
$auditExportConfigured = ($auditExport.Json.data.immutable -eq $true) -or ($auditExporter.exporter -eq 'local_file')
Assert-True $auditExportConfigured 'admin audit export did not report configured immutable Object Lock or Render disk local-file storage.'

$auditExportWrite = Invoke-ComputeMarketRequest -Method POST -Path '/compute/audit/export' -Scopes 'compute:audit' -Body @{ chain_id = 'all' }
Assert-Status -Response $auditExportWrite -Expected 200 -Name 'audit export write'
$auditExportWriteData = $auditExportWrite.Json.data
Assert-True (($auditExportWrite.Json.ok -eq $true) -and ($auditExportWriteData.ok -eq $true)) 'audit export write did not return ok=true.'
Assert-True (-not [string]::IsNullOrWhiteSpace([string]$auditExportWriteData.manifest_hash)) 'audit export write did not return a manifest_hash.'
Assert-True ([int]$auditExportWriteData.event_count -ge 1) 'audit export write did not export any audit events.'

$storageDiagnostics = Invoke-ComputeMarketRequest -Method GET -Path '/admin/storage/diagnostics' -Scopes 'compute:admin'
Assert-Status -Response $storageDiagnostics -Expected 200 -Name 'admin storage diagnostics'
Assert-True ($storageDiagnostics.Json.data.ok -eq $true) 'admin storage diagnostics did not return ok=true.'
$schemaVerification = $storageDiagnostics.Json.data.schema_verification
Assert-True ($schemaVerification.ok -eq $true) 'Postgres schema verification did not return ok=true.'
Assert-True (($null -eq $schemaVerification.missing_tables) -or ($schemaVerification.missing_tables.Count -eq 0)) 'Postgres schema verification reported missing tables.'
Assert-True (($null -eq $schemaVerification.missing_indexes) -or ($schemaVerification.missing_indexes.Count -eq 0)) 'Postgres schema verification reported missing indexes.'
Assert-True ($schemaVerification.advisory_lock_probe.acquired -eq $true) 'Postgres advisory migration lock probe did not acquire.'

$redisDiagnostics = Invoke-ComputeMarketRequest -Method GET -Path '/admin/redis/diagnostics' -Scopes 'compute:admin'
Assert-Status -Response $redisDiagnostics -Expected 200 -Name 'admin redis diagnostics'
Assert-True ($redisDiagnostics.Json.data.ok -eq $true) 'admin redis diagnostics did not return ok=true.'
Assert-True ($redisDiagnostics.Json.data.rate_limit_probe.ok -eq $true) 'Redis rate-limit probe did not return ok=true.'
Assert-True ($redisDiagnostics.Json.data.circuit_breaker_probe.ok -eq $true) 'Redis circuit-breaker probe did not return ok=true.'
Assert-True ($redisDiagnostics.Json.data.rate_limit_fail_closed -eq $true) 'Redis rate limiter is not fail-closed.'
Assert-True ($redisDiagnostics.Json.data.circuit_breaker_fail_closed -eq $true) 'Redis circuit breaker is not fail-closed.'

$missingKey = Invoke-ComputeMarketRequest -Method GET -Path '/compute/health' -Scopes 'compute:read' -IncludeApiKey $false
Assert-Status -Response $missingKey -Expected 401 -Name 'missing-key health'

$wrongScope = Invoke-ComputeMarketRequest -Method POST -Path '/compute/plan' -Scopes 'compute:read' -Body $planBody
Assert-Status -Response $wrongScope -Expected 403 -Name 'wrong-scope plan'

$result = [ordered]@{
    status = 'passed'
    public_url = $baseUrl
    root = [int]$root.StatusCode
    health = $health.StatusCode
    readiness = $readiness.StatusCode
    storage_backend = $storageBackend
    rate_limit_backend = $rateLimitBackend
    circuit_breaker_backend = $circuitBreakerBackend
    redis_url_scheme = $redisUrlScheme
    allow_internal_redis_in_production = [bool]$allowInternalRedis
    plan = $plan.StatusCode
    audit_verify = $auditVerify.StatusCode
    metrics = [int]$metrics.StatusCode
    alerts = $alerts.StatusCode
    audit_export = $auditExport.StatusCode
    audit_export_write = $auditExportWrite.StatusCode
    audit_export_write_manifest_hash_present = -not [string]::IsNullOrWhiteSpace([string]$auditExportWriteData.manifest_hash)
    admin_storage_diagnostics = $storageDiagnostics.StatusCode
    admin_redis_diagnostics = $redisDiagnostics.StatusCode
    audit_export_immutable = [bool]$auditExport.Json.data.immutable
    missing_key = $missingKey.StatusCode
    wrong_scope = $wrongScope.StatusCode
    dry_run_only = [bool]$computePlan.dry_run_only
    funds_moved = [bool]$computePlan.funds_moved
    broadcast_allowed = [bool]$computePlan.broadcast_allowed
    private_key_required = [bool]$computePlan.private_key_required
}

$result | ConvertTo-Json -Depth 8
