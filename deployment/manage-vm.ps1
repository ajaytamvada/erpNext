param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('start', 'stop', 'status')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
$subscriptionId = 'ab14cf7b-0ed0-4736-bbed-369540c08251'
$resourceGroup = 'rg-erpnext'
$vmName = 'erpnext-demo-vm'

switch ($Action) {
    'start' {
        az vm start --subscription $subscriptionId --resource-group $resourceGroup --name $vmName
        if ($LASTEXITCODE -ne 0) { throw 'VM start failed.' }
        Write-Output 'Allow a minute for Pridict to start, then open https://pridict-demo.centralindia.cloudapp.azure.com'
    }
    'stop' {
        az vm deallocate --subscription $subscriptionId --resource-group $resourceGroup --name $vmName
        if ($LASTEXITCODE -ne 0) { throw 'VM deallocation failed.' }
    }
    'status' {
        az vm get-instance-view --subscription $subscriptionId --resource-group $resourceGroup --name $vmName --query 'instanceView.statuses[].displayStatus' -o tsv
        if ($LASTEXITCODE -ne 0) { throw 'VM status check failed.' }
    }
}
