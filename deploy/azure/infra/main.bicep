// =============================================================================
// Kronos on Azure — infrastructure skeleton (Bicep)
// Provisions the Azure-side plumbing: Event Hubs (ingestion), Key Vault
// (secrets), and an Azure ML workspace (model train + serve).
//
// Fabric items (Eventhouse, Eventstream, Real-Time Dashboards, Data Activator)
// are provisioned through Fabric REST / Git integration + the KQL scripts in
// deploy/azure/fabric/eventhouse/, not through Bicep.
//
//   az deployment group create -g <rg> -f main.bicep -p namePrefix=kronos
// =============================================================================

@description('Prefix for resource names.')
param namePrefix string = 'kronos'

@description('Azure region.')
param location string = resourceGroup().location

@description('Event Hubs throughput units.')
param eventHubCapacity int = 2

// ---- Ingestion: Event Hubs --------------------------------------------------
resource ehNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: '${namePrefix}-ehns'
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: eventHubCapacity
  }
  properties: {
    isAutoInflateEnabled: true
    maximumThroughputUnits: 10
  }
}

resource marketHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: ehNamespace
  name: 'market-ticks'
  properties: {
    messageRetentionInDays: 3
    partitionCount: 16          // partitioned by symbol for per-symbol ordering
    captureDescription: {
      enabled: true             // cheap raw archive to storage / OneLake
      encoding: 'Avro'
      intervalInSeconds: 300
      sizeLimitInBytes: 314572800
    }
  }
}

// ---- Secrets: Key Vault -----------------------------------------------------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${namePrefix}-kv'
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: tenant().tenantId
    enableRbacAuthorization: true      // grant Fabric MI + AML MI via RBAC
    enableSoftDelete: true
  }
}

// ---- Model plane: Azure ML workspace ---------------------------------------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: toLower('${namePrefix}mlsa')
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-ai'
  location: location
  kind: 'web'
  properties: { Application_Type: 'web' }
}

resource amlWorkspace 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: '${namePrefix}-mlw'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    friendlyName: 'Kronos model plane'
    storageAccount: storage.id
    keyVault: keyVault.id
    applicationInsights: appInsights.id
  }
}

// The GPU online endpoint + deployment are created from deploy/azure/azureml/*.yml
// (endpoint.yml / deployment.yml) once the workspace exists, so model lifecycle
// stays in the MLOps pipeline rather than in infra templates.

output eventHubNamespace string = ehNamespace.name
output keyVaultName string = keyVault.name
output amlWorkspaceName string = amlWorkspace.name
