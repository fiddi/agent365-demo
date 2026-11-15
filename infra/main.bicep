// Agent 365 demo – backend infrastructure (subscription scope).
// Environment-specific IDs are passed as parameters at deploy time (from .env), never committed.
targetScope = 'subscription'

@description('Naming prefix, e.g. dsc')
param prefix string = 'dsc'
@description('Environment/stage token used in names')
param stage string = 'p1'
param workload string = 'agent365'
param location string = 'switzerlandnorth'

@description('Tenant ID of the M365 tenant that hosts the agent blueprint')
param a365TenantId string
@description('Client (app) ID of the agent blueprint')
param blueprintClientId string
@description('Agent identity ID (agentic app instance)')
param agentId string = ''

@description('Existing Azure OpenAI account to reuse')
param openAiAccountName string
param openAiResourceGroup string
param chatDeploymentName string = 'agent365-chat'
param chatModelName string = 'gpt-5.4-mini'
param chatModelVersion string = '2026-03-17'
param chatCapacity int = 50

@description('UPN of the agent user (loop guard: never answer own mails)')
param agentUpn string = ''

@description('GitHub repo (owner/name) allowed to deploy via OIDC')
param githubRepo string = 'fiddi/agent365-demo'

@description('Object ID of the deploying user – gets Key Vault Secrets Officer')
param deployerObjectId string

var tags = {
  workload: workload
  environment: 'demo'
  owner: prefix
}
var base = '${prefix}-${stage}'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: '${base}-rg-${workload}'
  location: location
  tags: tags
}

module core 'modules/core.bicep' = {
  scope: rg
  name: 'core'
  params: {
    base: base
    workload: workload
    storageName: toLower('${prefix}${stage}st${workload}')
    location: location
    tags: tags
    a365TenantId: a365TenantId
    blueprintClientId: blueprintClientId
    agentId: agentId
    openAiEndpoint: 'https://${openAiAccountName}.openai.azure.com/'
    chatDeploymentName: chatDeploymentName
    githubRepo: githubRepo
    agentUpn: agentUpn
    deployerObjectId: deployerObjectId
  }
}

module model 'modules/openai-deployment.bicep' = {
  scope: resourceGroup(openAiResourceGroup)
  name: 'openai-deployment'
  params: {
    accountName: openAiAccountName
    deploymentName: chatDeploymentName
    modelName: chatModelName
    modelVersion: chatModelVersion
    capacity: chatCapacity
    appPrincipalId: core.outputs.appIdentityPrincipalId
  }
}

output resourceGroup string = rg.name
output webAppName string = core.outputs.webAppName
output webAppHostName string = core.outputs.webAppHostName
output keyVaultName string = core.outputs.keyVaultName
output appIdentityClientId string = core.outputs.appIdentityClientId
output githubIdentityClientId string = core.outputs.githubIdentityClientId
