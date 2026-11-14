// Core backend resources in dsc-p1-rg-agent365.
param base string
param workload string
param storageName string
param location string
param tags object
param a365TenantId string
param blueprintClientId string
param agentId string
param openAiEndpoint string
param chatDeploymentName string
param githubRepo string
param deployerObjectId string

var roles = {
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  keyVaultSecretsOfficer: 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
  websiteContributor: 'de139f84-1756-47ae-9be6-808fbbe84772'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
}
var blueprintSecretName = 'blueprint-client-secret'

// ---------- Monitoring ----------
resource log 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${base}-log-${workload}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: '${base}-appi-${workload}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: log.id
    DisableLocalAuth: false
  }
}

// ---------- Identities ----------
resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${base}-app-${workload}-uaid'
  location: location
  tags: tags
}

resource githubIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${base}-github-${workload}-uaid'
  location: location
  tags: tags
}

resource githubFic 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: githubIdentity
  name: 'github-environment-demo'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepo}:environment:demo'
    audiences: [ 'api://AzureADTokenExchange' ]
  }
}

// ---------- Key Vault (RBAC) ----------
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${base}-kv-${workload}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource kvAppRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, appIdentity.id, roles.keyVaultSecretsUser)
  properties: {
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsUser)
  }
}

resource kvDeployerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, deployerObjectId, roles.keyVaultSecretsOfficer)
  properties: {
    principalId: deployerObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsOfficer)
  }
}

// ---------- Storage (persistent agent state) ----------
resource st 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource stBlob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: st
  name: 'default'
}

resource stateContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: stBlob
  name: 'agent-state'
}

resource stAppRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: st
  name: guid(st.id, appIdentity.id, roles.storageBlobDataContributor)
  properties: {
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
  }
}

// ---------- App Service ----------
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${base}-asp-${workload}'
  location: location
  tags: tags
  kind: 'linux'
  sku: { name: 'B1', tier: 'Basic' }
  properties: { reserved: true }
}

var kvRef = '@Microsoft.KeyVault(VaultName=${kv.name};SecretName=${blueprintSecretName})'

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: '${base}-app-${workload}'
  location: location
  tags: union(tags, { 'azd-service-name': 'agent' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${appIdentity.id}': {} }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    keyVaultReferenceIdentity: appIdentity.id
    siteConfig: {
      linuxFxVersion: 'DOTNETCORE|10.0'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      healthCheckPath: '/api/health'
      appSettings: [
        { name: 'ASPNETCORE_ENVIRONMENT', value: 'Production' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appi.properties.ConnectionString }
        { name: 'AZURE_CLIENT_ID', value: appIdentity.properties.clientId }
        // Azure OpenAI – keyless via user-assigned managed identity
        { name: 'AIServices__AzureOpenAI__Endpoint', value: openAiEndpoint }
        { name: 'AIServices__AzureOpenAI__DeploymentName', value: chatDeploymentName }
        { name: 'AIServices__AzureOpenAI__ManagedIdentityClientId', value: appIdentity.properties.clientId }
        { name: 'AIServices__AzureOpenAI__TenantId', value: subscription().tenantId }
        // Blueprint connection (M365 tenant) – secret from Key Vault
        { name: 'Connections__ServiceConnection__Settings__AuthType', value: 'ClientSecret' }
        { name: 'Connections__ServiceConnection__Settings__AuthorityEndpoint', value: '${environment().authentication.loginEndpoint}${a365TenantId}' }
        { name: 'Connections__ServiceConnection__Settings__ClientId', value: blueprintClientId }
        { name: 'Connections__ServiceConnection__Settings__ClientSecret', value: kvRef }
        { name: 'Connections__ServiceConnection__Settings__Scopes__0', value: '${blueprintClientId}/.default' }
        { name: 'Connections__ServiceConnection__Settings__AgentId', value: agentId }
        // Incoming token validation
        { name: 'TokenValidation__Enabled', value: 'true' }
        { name: 'TokenValidation__TenantId', value: a365TenantId }
        { name: 'TokenValidation__Audiences__0', value: blueprintClientId }
        // Observability (exporter enabled in Phase 5)
        { name: 'Agent365Observability__TenantId', value: a365TenantId }
        { name: 'Agent365Observability__AgentBlueprintId', value: blueprintClientId }
        { name: 'Agent365Observability__BlueprintClientId', value: blueprintClientId }
        { name: 'Agent365Observability__ClientId', value: blueprintClientId }
        { name: 'Agent365Observability__ClientSecret', value: kvRef }
        { name: 'Agent365Observability__AgentId', value: agentId }
        { name: 'Agent365Observability__UseManagedIdentity', value: 'false' }
        { name: 'EnableAgent365Exporter', value: 'false' }
        // State storage
        { name: 'Storage__BlobServiceUri', value: st.properties.primaryEndpoints.blob }
        { name: 'Storage__ContainerName', value: stateContainer.name }
      ]
    }
  }
}

// GitHub deploy identity: may deploy code to this RG's web app
resource ghRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: app
  name: guid(app.id, githubIdentity.id, roles.websiteContributor)
  properties: {
    principalId: githubIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.websiteContributor)
  }
}

output webAppName string = app.name
output webAppHostName string = app.properties.defaultHostName
output keyVaultName string = kv.name
output appIdentityPrincipalId string = appIdentity.properties.principalId
output appIdentityClientId string = appIdentity.properties.clientId
output githubIdentityClientId string = githubIdentity.properties.clientId
