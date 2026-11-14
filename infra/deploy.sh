#!/usr/bin/env bash
# Deploys the backend infrastructure. Reads environment-specific IDs from ../.env (git-ignored).
# Usage: infra/deploy.sh [what-if]
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
set -a; . "$root/.env"; set +a

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
deployer=$(az ad signed-in-user show --query id -o tsv)

if [ "${1:-}" = "what-if" ]; then cmd=(what-if); else cmd=(create --query properties.outputs -o json); fi
az deployment sub "${cmd[0]}" "${cmd[@]:1}" \
  --name agent365-infra \
  --location "${AZURE_LOCATION:-switzerlandnorth}" \
  --template-file "$root/infra/main.bicep" \
  --parameters \
    a365TenantId="$A365_TENANT_ID" \
    blueprintClientId="$A365_BLUEPRINT_ID" \
    agentId="${A365_AGENT_ID:-}" \
    openAiAccountName="$AZURE_OPENAI_ACCOUNT" \
    openAiResourceGroup="$AZURE_OPENAI_RESOURCE_GROUP" \
    deployerObjectId="$deployer"
