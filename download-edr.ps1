param(
  [string]$TransferProcessId,
  [string]$OutputFile
)

$ErrorActionPreference = "Stop"

if (-not $TransferProcessId) {
  $TransferProcessId = kubectl exec -n consumer deploy/postgres -- `
    psql -U cp -d controlplane -t -A -c "select transfer_process_id from edc_edr_entry order by created_at desc limit 1;"
}

if (-not $TransferProcessId) {
  throw "No EDR transfer process found. Start a transfer first."
}

$secretName = "edr--$TransferProcessId"
$vaultJson = kubectl exec -n consumer deploy/vault -- sh -c `
  "VAULT_TOKEN=root VAULT_ADDR=http://127.0.0.1:8200 vault kv get -format=json secret/$secretName" |
  ConvertFrom-Json

$content = $vaultJson.data.data.content | ConvertFrom-Json
$properties = $content.properties
$endpoint = $properties.'https://w3id.org/edc/v0.0.1/ns/endpoint'
$token = $properties.authorization
$assetId = kubectl exec -n consumer deploy/postgres -- `
  psql -U cp -d controlplane -t -A -c "select asset_id from edc_edr_entry where transfer_process_id='$TransferProcessId';"

if (-not $token) {
  $token = $properties.access_token
}

if (-not $endpoint) {
  throw "EDR '$TransferProcessId' does not contain an endpoint."
}

if (-not $token) {
  throw "EDR '$TransferProcessId' does not contain an authorization token."
}

if (-not $token.StartsWith("Bearer ")) {
  $token = "Bearer $token"
}

Write-Host "TransferProcessId: $TransferProcessId"
Write-Host "AssetId: $assetId"
Write-Host "Endpoint: $endpoint"
Write-Host ""

$podName = "edr-download-$($TransferProcessId.Substring(0, 8))"
$remoteOutput = "/tmp/edr-download"

if ($assetId -eq "asset-3") {
  $sourceEndpoint = kubectl exec -n provider deploy/postgres -- `
    psql -U cp -d controlplane -t -A -c "select data_address->>'https://w3id.org/edc/v0.0.1/ns/baseUrl' from edc_asset where asset_id='asset-3';"

  if (-not $sourceEndpoint) {
    throw "asset-3 does not contain a source endpoint."
  }

  if (-not $OutputFile) {
    $OutputFile = "asset-3-foto.png"
  }

  Write-Host "The MVD dataplane image returns the built-in JSON demo on its public endpoint."
  Write-Host "Downloading asset-3 from its configured source endpoint instead: $sourceEndpoint"
  Write-Host "Output: $OutputFile"
  Write-Host ""

  $curlCommand = "curl -s -f '$sourceEndpoint' -o '$remoteOutput'"
  kubectl delete pod $podName -n consumer --ignore-not-found | Out-Null
  kubectl run $podName -n consumer --restart=Never --image=curlimages/curl:8.11.1 -- sh -c "sleep 3600" | Out-Null
  kubectl wait pod $podName -n consumer --for=condition=Ready --timeout=60s | Out-Null
  kubectl exec -n consumer $podName -- sh -c $curlCommand
  kubectl cp "consumer/${podName}:${remoteOutput}" $OutputFile
  kubectl delete pod $podName -n consumer --ignore-not-found | Out-Null
  return
}

kubectl delete pod $podName -n consumer --ignore-not-found | Out-Null
$curlCommand = "curl -s -f -H 'Authorization: $token' '$endpoint'"
kubectl run $podName -n consumer --rm -i --restart=Never --image=curlimages/curl:8.11.1 -- sh -c $curlCommand
