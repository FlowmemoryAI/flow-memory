[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApiUrl,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApiKey,

    [Parameter()]
    [switch]$RequireImmutableAudit,
    [Parameter()]
    [switch]$IncludeMarketAlpha,


    [Parameter()]
    [string]$GatewayJwtHs256Secret = $env:FLOW_MEMORY_API_JWT_HS256_SECRET,

    [Parameter()]
    [string]$GatewayJwtIssuer = $env:FLOW_MEMORY_API_JWT_ISSUER,

    [Parameter()]
    [string]$GatewayJwtAudience = $env:FLOW_MEMORY_API_JWT_AUDIENCE,

    [Parameter()]
    [ValidateRange(30, 3600)]
    [int]$GatewayJwtTtlSeconds = 300

)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$MinimumPostgresSchemaTableCount = 110
$MinimumPostgresSchemaIndexCount = 1311


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
function Get-ApiKeyBlockReason {
    param([Parameter(Mandatory = $true)] [string]$Value)

    if ($Value -match 'CHANGEME|<[^>]*>|high-entropy-api-key') {
        return 'api_key_placeholder_not_allowed'
    }
    if ($Value.Trim().ToLowerInvariant() -in @('api-key', 'dev-key', 'prod-key', 'test', 'secret', 'password')) {
        return 'api_key_weak_value_not_allowed'
    }
    return ''
}


$baseUrl = $ApiUrl.TrimEnd('/')
if (-not ($baseUrl -match '^https://')) {
    throw 'ApiUrl must be an https:// public URL for Level 1 smoke tests.'
}
$publicUrlBlockReason = Get-PublicUrlBlockReason -Url $baseUrl
if (-not [string]::IsNullOrWhiteSpace($publicUrlBlockReason)) {
    throw "ApiUrl must be a real public endpoint for Level 1 smoke tests: $publicUrlBlockReason."
}
$apiKeyBlockReason = Get-ApiKeyBlockReason -Value $ApiKey
if (-not [string]::IsNullOrWhiteSpace($apiKeyBlockReason)) {
    throw "ApiKey must be a real production secret for Level 1 smoke tests: $apiKeyBlockReason."
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

function ConvertTo-Base64Url {
    param([Parameter(Mandatory = $true)] [byte[]]$Bytes)

    return [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}


function New-GatewayJwt {
    param(
        [Parameter(Mandatory = $true)] [string]$Secret,
        [Parameter(Mandatory = $true)] [string]$Issuer,
        [Parameter(Mandatory = $true)] [string]$Audience,
        [Parameter(Mandatory = $true)] [string]$Scopes,
        [Parameter(Mandatory = $true)] [int]$TtlSeconds,
        [string]$Roles = ''
    )

    if ($Secret.Length -lt 32) {
        throw 'Gateway JWT secret must be at least 32 characters when configured.'
    }
    if ([string]::IsNullOrWhiteSpace($Issuer) -or -not $Issuer.StartsWith('https://')) {
        throw 'Gateway JWT issuer must be a non-empty https:// URL when JWT smoke is configured.'
    }
    if ([string]::IsNullOrWhiteSpace($Audience)) {
        throw 'Gateway JWT audience must be non-empty when JWT smoke is configured.'
    }

    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $header = [ordered]@{ alg = 'HS256'; typ = 'JWT' }
    $claims = [ordered]@{
        iss = $Issuer
        aud = $Audience
        sub = 'flow-memory-public-smoke'
        scope = $Scopes
        iat = $now
        nbf = $now
        exp = $now + $TtlSeconds
    }
    if (-not [string]::IsNullOrWhiteSpace($Roles)) {
        $claims['flow_memory_roles'] = @($Roles -split '\s+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    }

    $encoding = [System.Text.Encoding]::UTF8
    $headerSegment = ConvertTo-Base64Url -Bytes $encoding.GetBytes(($header | ConvertTo-Json -Compress))
    $payloadSegment = ConvertTo-Base64Url -Bytes $encoding.GetBytes(($claims | ConvertTo-Json -Compress))
    $signingInput = "$headerSegment.$payloadSegment"
    $hmac = [System.Security.Cryptography.HMACSHA256]::new($encoding.GetBytes($Secret))
    try {
        $signature = $hmac.ComputeHash($encoding.GetBytes($signingInput))
    }
    finally {
        $hmac.Dispose()
    }

    return "$signingInput.$(ConvertTo-Base64Url -Bytes $signature)"
}


function Invoke-GatewayJwtRequest {
    param(
        [Parameter(Mandatory = $true)] [string]$Token,
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [string]$Scopes,
        [Parameter(Mandatory = $true)] [string]$Label
    )

    $headers = Add-NonceHeaders -Headers @{
        authorization = "Bearer $Token"
        'x-flow-memory-scopes' = $Scopes
    } -Label $Label

    try {
        $response = Invoke-WebRequest -Uri "$baseUrl$Path" -Method GET -Headers $headers -TimeoutSec 90
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
function Assert-DataFlag {
    param([hashtable]$Response, [string]$Field, [object]$Expected, [string]$Name)
    $actual = Get-DataField -Json $Response.Json -Name $Field
    Assert-True ($actual -eq $Expected) "$Name expected $Field=$Expected but received '$actual'."
}

$gatewayJwtConfigured = (
    -not [string]::IsNullOrWhiteSpace($GatewayJwtHs256Secret) -or
    -not [string]::IsNullOrWhiteSpace($GatewayJwtIssuer) -or
    -not [string]::IsNullOrWhiteSpace($GatewayJwtAudience)
)
if ($gatewayJwtConfigured) {
    if (-not [string]::IsNullOrWhiteSpace($GatewayJwtHs256Secret) -and $GatewayJwtHs256Secret -match 'CHANGEME|<[^>]*>|high-entropy') {
        throw 'Gateway JWT secret must be a real high-entropy secret when JWT smoke is configured.'
    }
    $missingGatewayJwtSettings = New-Object System.Collections.Generic.List[string]
    if ([string]::IsNullOrWhiteSpace($GatewayJwtHs256Secret)) {
        $missingGatewayJwtSettings.Add('FLOW_MEMORY_API_JWT_HS256_SECRET')
    }
    if ([string]::IsNullOrWhiteSpace($GatewayJwtIssuer)) {
        $missingGatewayJwtSettings.Add('FLOW_MEMORY_API_JWT_ISSUER')
    }
    if ([string]::IsNullOrWhiteSpace($GatewayJwtAudience)) {
        $missingGatewayJwtSettings.Add('FLOW_MEMORY_API_JWT_AUDIENCE')
    }
    if ($missingGatewayJwtSettings.Count -gt 0) {
        throw "Gateway JWT secret, issuer, and audience must be configured together when JWT smoke is configured: $($missingGatewayJwtSettings -join ', ')."
    }
    [void](New-GatewayJwt -Secret $GatewayJwtHs256Secret -Issuer $GatewayJwtIssuer -Audience $GatewayJwtAudience -Scopes 'compute:read' -TtlSeconds $GatewayJwtTtlSeconds)
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
Assert-True ($readinessData.production_safety_defaults.require_managed_sql_in_production -eq $true) 'readiness did not require managed SQL in production.'
Assert-True ($readinessData.production_safety_defaults.dry_run_required -eq $true) 'readiness did not report dry_run_required=true.'
Assert-True ($readinessData.production_safety_defaults.live_settlement_enabled -eq $false) 'readiness did not report live_settlement_enabled=false.'
Assert-True ($readinessData.production_safety_defaults.broadcast_enabled -eq $false) 'readiness did not report broadcast_enabled=false.'
Assert-True ($readinessData.production_safety_defaults.private_key_inputs_allowed -eq $false) 'readiness did not report private_key_inputs_allowed=false.'
Assert-True ($readinessData.production_safety_defaults.stripe_checkout_enabled -eq $false) 'readiness did not report stripe_checkout_enabled=false.'
Assert-True ($readinessData.production_safety_defaults.audit_required -eq $true) 'readiness did not report audit_required=true.'
Assert-True ($readinessData.production_safety_defaults.audit_export_required -eq $true) 'readiness did not report audit_export_required=true.'
$redisUrlScheme = $readinessData.production_safety_defaults.redis_url_scheme
$allowInternalRedis = $readinessData.production_safety_defaults.allow_internal_redis_in_production
$redisSchemeAllowed = ($redisUrlScheme -eq 'rediss') -or (($redisUrlScheme -eq 'redis') -and ($allowInternalRedis -eq $true))
Assert-True $redisSchemeAllowed "readiness Redis URL scheme was '$redisUrlScheme', expected rediss or explicitly allowed Render internal redis."

$planBody = @{
    idempotency_key = "public-smoke-plan-$([Guid]::NewGuid().ToString('N'))"
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
$planReplay = Invoke-ComputeMarketRequest -Method POST -Path '/compute/plan' -Scopes 'compute:plan' -Body @{
    task = 'public live Level 1 Flow Memory Compute Market smoke replay'
    idempotency_key = $planBody.idempotency_key
    dry_run = $true
}
Assert-Status -Response $planReplay -Expected 200 -Name 'plan replay'
Assert-True ($planReplay.Json.data.idempotent_replay -eq $true) 'plan replay did not return idempotent_replay=true.'
Assert-True ($planReplay.Json.data.compute_plan.decision_id -eq $computePlan.decision_id) 'plan replay decision_id did not match the original plan.'

$marketAlphaStatuses = [ordered]@{}
if ($IncludeMarketAlpha) {
    $inferenceOpportunity = Invoke-ComputeMarketRequest -Method POST -Path '/inference/opportunity-cost' -Scopes 'inference:plan' -Body @{
        task = 'public market alpha inference opportunity smoke'
        estimated_value = 25
        budget = 5
    }
    Assert-Status -Response $inferenceOpportunity -Expected 200 -Name 'inference opportunity-cost'
    Assert-True ((Get-DataField -Json $inferenceOpportunity.Json -Name 'ok') -eq $true) 'inference opportunity-cost did not return ok=true.'
    Assert-DataFlag -Response $inferenceOpportunity -Field 'dry_run_only' -Expected $true -Name 'inference opportunity-cost'
    Assert-DataFlag -Response $inferenceOpportunity -Field 'funds_moved' -Expected $false -Name 'inference opportunity-cost'
    $marketAlphaStatuses['inference_opportunity_cost'] = $inferenceOpportunity.StatusCode

    $inferenceOrderBook = Invoke-ComputeMarketRequest -Method GET -Path '/inference/market/order-book' -Scopes 'inference:read'
    Assert-Status -Response $inferenceOrderBook -Expected 200 -Name 'inference order-book'
    Assert-True ((Get-DataField -Json $inferenceOrderBook.Json -Name 'ok') -eq $true) 'inference order-book did not return ok=true.'
    Assert-DataFlag -Response $inferenceOrderBook -Field 'dry_run_only' -Expected $true -Name 'inference order-book'
    Assert-DataFlag -Response $inferenceOrderBook -Field 'funds_moved' -Expected $false -Name 'inference order-book'
    $marketAlphaStatuses['inference_order_book'] = $inferenceOrderBook.StatusCode

    $proxyBody = @{
        model = 'flow-local-small'
        messages = @(@{ role = 'user'; content = 'public alpha proxy smoke' })
    }
    $proxyChat = Invoke-ComputeMarketRequest -Method POST -Path '/v1/chat/completions' -Scopes 'inference:proxy' -Body $proxyBody
    Assert-Status -Response $proxyChat -Expected 200 -Name 'OpenAI-compatible proxy'
    $proxyData = $proxyChat.Json.data
    Assert-True ($proxyData.object -eq 'chat.completion') 'OpenAI-compatible proxy did not return chat.completion.'
    Assert-True ($proxyData.flow_memory.dry_run_only -eq $true) 'OpenAI-compatible proxy did not return dry_run_only=true.'
    Assert-True ($proxyData.flow_memory.funds_moved -eq $false) 'OpenAI-compatible proxy did not return funds_moved=false.'
    $marketAlphaStatuses['openai_proxy'] = $proxyChat.StatusCode
    $responsesBody = @{
        model = 'flow-local-small'
        input = 'public alpha responses smoke'
    }
    $proxyResponses = Invoke-ComputeMarketRequest -Method POST -Path '/v1/responses' -Scopes 'inference:proxy' -Body $responsesBody
    Assert-Status -Response $proxyResponses -Expected 200 -Name 'OpenAI-compatible responses proxy'
    $responsesData = $proxyResponses.Json.data
    Assert-True ($responsesData.object -eq 'response') 'OpenAI-compatible responses proxy did not return response.'
    Assert-True ($responsesData.flow_memory.dry_run_only -eq $true) 'OpenAI-compatible responses proxy did not return dry_run_only=true.'
    Assert-True ($responsesData.flow_memory.funds_moved -eq $false) 'OpenAI-compatible responses proxy did not return funds_moved=false.'
    $marketAlphaStatuses['openai_responses'] = $proxyResponses.StatusCode

    $embeddingsBody = @{
        model = 'flow-local-embedding'
        input = @('public', 'alpha', 'embeddings')
    }
    $proxyEmbeddings = Invoke-ComputeMarketRequest -Method POST -Path '/v1/embeddings' -Scopes 'inference:proxy' -Body $embeddingsBody
    Assert-Status -Response $proxyEmbeddings -Expected 200 -Name 'OpenAI-compatible embeddings proxy'
    $embeddingsData = $proxyEmbeddings.Json.data
    Assert-True ($embeddingsData.object -eq 'list') 'OpenAI-compatible embeddings proxy did not return list.'
    Assert-True ($embeddingsData.flow_memory.dry_run_only -eq $true) 'OpenAI-compatible embeddings proxy did not return dry_run_only=true.'
    Assert-True ($embeddingsData.flow_memory.funds_moved -eq $false) 'OpenAI-compatible embeddings proxy did not return funds_moved=false.'
    $marketAlphaStatuses['openai_embeddings'] = $proxyEmbeddings.StatusCode

    $capacityInventory = Invoke-ComputeMarketRequest -Method GET -Path '/capacity/inventory' -Scopes 'compute:read'
    Assert-Status -Response $capacityInventory -Expected 200 -Name 'capacity inventory'
    Assert-True ((Get-DataField -Json $capacityInventory.Json -Name 'ok') -eq $true) 'capacity inventory did not return ok=true.'
    Assert-DataFlag -Response $capacityInventory -Field 'dry_run_only' -Expected $true -Name 'capacity inventory'
    Assert-DataFlag -Response $capacityInventory -Field 'funds_moved' -Expected $false -Name 'capacity inventory'
    $marketAlphaStatuses['capacity_inventory'] = $capacityInventory.StatusCode

    $futuresMarkets = Invoke-ComputeMarketRequest -Method GET -Path '/futures/markets' -Scopes 'compute:read'
    Assert-Status -Response $futuresMarkets -Expected 200 -Name 'futures markets'
    Assert-True ((Get-DataField -Json $futuresMarkets.Json -Name 'ok') -eq $true) 'futures markets did not return ok=true.'
    Assert-DataFlag -Response $futuresMarkets -Field 'dry_run_only' -Expected $true -Name 'futures markets'
    Assert-DataFlag -Response $futuresMarkets -Field 'funds_moved' -Expected $false -Name 'futures markets'
    Assert-DataFlag -Response $futuresMarkets -Field 'live_trading_enabled' -Expected $false -Name 'futures markets'
    $marketAlphaStatuses['futures_markets'] = $futuresMarkets.StatusCode
}

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
if ($RequireImmutableAudit) {
    $auditExportConfigured = ($auditExport.Json.data.immutable -eq $true) -and ($auditExporter.exporter -eq 's3_object_lock')
    Assert-True $auditExportConfigured 'admin audit export did not report immutable S3 Object Lock storage.'
}
else {
    $auditExportConfigured = ($auditExport.Json.data.immutable -eq $true) -or ($auditExporter.exporter -eq 'local_file')
    Assert-True $auditExportConfigured 'admin audit export did not report configured immutable Object Lock or Render disk local-file storage.'
}

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
$requiredSchemaTableCount = 0
if ($schemaVerification.PSObject.Properties.Name -contains 'required_table_count') {
    $requiredSchemaTableCount = [int]$schemaVerification.required_table_count
}
$requiredSchemaIndexCount = 0
if ($schemaVerification.PSObject.Properties.Name -contains 'required_index_count') {
    $requiredSchemaIndexCount = [int]$schemaVerification.required_index_count
}
Assert-True ($requiredSchemaTableCount -ge $MinimumPostgresSchemaTableCount) "Postgres schema verification reported $requiredSchemaTableCount required tables, expected at least $MinimumPostgresSchemaTableCount."
Assert-True ($requiredSchemaIndexCount -ge $MinimumPostgresSchemaIndexCount) "Postgres schema verification reported $requiredSchemaIndexCount required indexes, expected at least $MinimumPostgresSchemaIndexCount."
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

$jwtHealth = $null
$jwtWrongAudience = $null
$jwtRoleHealth = $null
$jwtRoleInference = $null
$jwtRoleHealthStatus = 0
$jwtRoleInferenceStatus = 0
if (-not [string]::IsNullOrWhiteSpace($GatewayJwtHs256Secret)) {
    $jwtScopes = 'compute:read compute:plan compute:audit compute:admin'
    $jwtToken = New-GatewayJwt `
        -Secret $GatewayJwtHs256Secret `
        -Issuer $GatewayJwtIssuer `
        -Audience $GatewayJwtAudience `
        -Scopes $jwtScopes `
        -TtlSeconds $GatewayJwtTtlSeconds
    $badJwtToken = New-GatewayJwt `
        -Secret $GatewayJwtHs256Secret `
        -Issuer $GatewayJwtIssuer `
        -Audience "$GatewayJwtAudience-wrong" `
        -Scopes $jwtScopes `
        -TtlSeconds $GatewayJwtTtlSeconds
    $jwtRoleToken = New-GatewayJwt `
        -Secret $GatewayJwtHs256Secret `
        -Issuer $GatewayJwtIssuer `
        -Audience $GatewayJwtAudience `
        -Scopes 'compute:read' `
        -Roles 'inference-admin' `
        -TtlSeconds $GatewayJwtTtlSeconds

    $jwtHealth = Invoke-GatewayJwtRequest -Token $jwtToken -Path '/compute/health' -Scopes 'compute:read' -Label 'jwt-health'
    Assert-Status -Response $jwtHealth -Expected 200 -Name 'jwt health'
    Assert-True (($jwtHealth.Json.ok -eq $true) -or ((Get-DataField -Json $jwtHealth.Json -Name 'ok') -eq $true)) 'JWT health did not return ok=true.'

    $jwtWrongAudience = Invoke-GatewayJwtRequest -Token $badJwtToken -Path '/compute/health' -Scopes 'compute:read' -Label 'jwt-wrong-audience'
    Assert-Status -Response $jwtWrongAudience -Expected 401 -Name 'jwt wrong-audience health'

    $jwtRoleHealth = Invoke-GatewayJwtRequest -Token $jwtRoleToken -Path '/compute/health' -Scopes 'compute:read' -Label 'jwt-role-health'
    Assert-Status -Response $jwtRoleHealth -Expected 200 -Name 'jwt role health'
    Assert-True (($jwtRoleHealth.Json.ok -eq $true) -or ((Get-DataField -Json $jwtRoleHealth.Json -Name 'ok') -eq $true)) 'JWT role health did not return ok=true.'
    if ($IncludeMarketAlpha) {
        $jwtRoleInference = Invoke-GatewayJwtRequest -Token $jwtRoleToken -Path '/inference/market/order-book' -Scopes 'inference:read' -Label 'jwt-role-inference-order-book'
        Assert-Status -Response $jwtRoleInference -Expected 200 -Name 'jwt role inference order-book'
        Assert-True ((Get-DataField -Json $jwtRoleInference.Json -Name 'ok') -eq $true) 'JWT role inference order-book did not return ok=true.'
        $jwtRoleInferenceStatus = [int]$jwtRoleInference.StatusCode
    }

    $jwtHealthStatus = [int]$jwtHealth.StatusCode
    $jwtWrongAudienceStatus = [int]$jwtWrongAudience.StatusCode
    $jwtRoleHealthStatus = [int]$jwtRoleHealth.StatusCode
}
else {
    $jwtHealthStatus = 0
    $jwtWrongAudienceStatus = 0
}

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
    plan_idempotent_replay = [bool]$planReplay.Json.data.idempotent_replay
    audit_verify = $auditVerify.StatusCode
    metrics = [int]$metrics.StatusCode
    alerts = $alerts.StatusCode
    audit_export = $auditExport.StatusCode
    audit_export_write = $auditExportWrite.StatusCode
    audit_export_write_manifest_hash_present = -not [string]::IsNullOrWhiteSpace([string]$auditExportWriteData.manifest_hash)
    admin_storage_diagnostics = $storageDiagnostics.StatusCode
    postgres_required_table_count = $requiredSchemaTableCount
    postgres_required_index_count = $requiredSchemaIndexCount
    admin_redis_diagnostics = $redisDiagnostics.StatusCode
    audit_export_immutable = [bool]$auditExport.Json.data.immutable
    missing_key = $missingKey.StatusCode
    wrong_scope = $wrongScope.StatusCode
    jwt_health = $jwtHealthStatus
    jwt_wrong_audience = $jwtWrongAudienceStatus
    jwt_role_health = $jwtRoleHealthStatus
    jwt_role_inference_order_book = $jwtRoleInferenceStatus
    market_alpha = [bool]$IncludeMarketAlpha
    market_alpha_statuses = $marketAlphaStatuses
    dry_run_only = [bool]$computePlan.dry_run_only
    funds_moved = [bool]$computePlan.funds_moved
    broadcast_allowed = [bool]$computePlan.broadcast_allowed
    private_key_required = [bool]$computePlan.private_key_required
}

$result | ConvertTo-Json -Depth 8
