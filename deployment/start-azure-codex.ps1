param([switch]$TestConnection)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path $PSScriptRoot -Parent
$codexExecutable = 'C:/Users/tjm06/AppData/Local/OpenAI/Codex/bin/12219cbfbcbddde7/codex.exe'
if (-not (Test-Path -LiteralPath $codexExecutable)) { $codexExecutable = (Get-Command codex -ErrorAction Stop).Source }
$previousKey = $env:AZURE_OPENAI_API_KEY
try {
    $azureKey = & az cognitiveservices account keys list --subscription ab14cf7b-0ed0-4736-bbed-369540c08251 --resource-group rg-codex --name ridcode --query key1 --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($azureKey)) { throw 'Azure authentication failed. Run az login and try again.' }
    $env:AZURE_OPENAI_API_KEY = $azureKey.Trim()
    $azureKey = $null
    $arguments = @(
        '-C', $projectDirectory,
        '-c', 'model="pridict-gpt56-sol"',
        '-c', 'model_provider="pridict_azure"',
        '-c', 'model_providers.pridict_azure.name="Azure OpenAI"',
        '-c', 'model_providers.pridict_azure.base_url="https://ridcode.openai.azure.com/openai/v1"',
        '-c', 'model_providers.pridict_azure.env_key="AZURE_OPENAI_API_KEY"',
        '-c', 'model_providers.pridict_azure.wire_api="responses"',
        '-c', 'model_reasoning_effort="medium"'
    )
    if ($TestConnection) {
        & $codexExecutable @arguments exec --ephemeral --sandbox read-only 'Do not use tools or read files. Reply with exactly: Azure Codex connection successful.'
    } else {
        $arguments += @('-c', 'approvals_reviewer="user"', '-c', 'approval_policy="on-request"')
        Write-Host 'Azure pay-per-token session. Budget alerts are not a hard spending cap.'
        & $codexExecutable @arguments --sandbox workspace-write 'Read deployment/PRIDICT-HANDOFF.md and summarize the next step. Do not implement changes until I ask.'
    }
    if ($LASTEXITCODE -ne 0) { throw "Codex exited with code $LASTEXITCODE" }
} finally {
    $env:AZURE_OPENAI_API_KEY = $previousKey
    $azureKey = $null
}
