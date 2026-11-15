#!/usr/bin/env bash
# Tears down the Agent 365 demo. DRY RUN by default – prints what would be deleted.
#
#   scripts/teardown.sh                # dry run
#   scripts/teardown.sh --yes          # delete M365 objects + Azure resources
#   scripts/teardown.sh --yes --github # additionally delete the GitHub environment "demo"
#
# Reads IDs from the git-ignored .env. Before running, `az account set` to a subscription in the
# M365 tenant (A365_TENANT_ID) – the script checks this. Azure resources are addressed explicitly
# via AZURE_SUBSCRIPTION_ID. The shared Azure OpenAI account is NOT deleted, only the demo deployment.
#
# Not automated (do it by hand): remove the custom agent "Ava" in the M365 admin center
# (Agents → All agents), and close the Microsoft support ticket.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
set -a; . "$root/.env"; set +a

YES=false; GITHUB=false
for a in "$@"; do case "$a" in --yes) YES=true;; --github) GITHUB=true;; *) echo "unknown option $a"; exit 2;; esac; done

run() { if $YES; then echo "+ $*"; "$@"; else echo "DRY: $*"; fi; }

graph() { # method url  (admin token for the M365 tenant)
  local tok; tok=$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv)
  if $YES; then
    curl -s -o /dev/null -w "  -> HTTP %{http_code}\n" -X "$1" -H "Authorization: Bearer $tok" "$2"
  else
    echo "DRY: $1 ${2%%\?*}"
  fi
}

echo "== Checks"
cur_tenant=$(az account show --query tenantId -o tsv)
[ "$cur_tenant" = "$A365_TENANT_ID" ] || { echo "az default account is not in the M365 tenant – run 'az account set' first"; exit 1; }
echo "M365 tenant ok; Azure subscription from .env; mode: $($YES && echo DELETE || echo DRY-RUN)"

echo "== 1. Microsoft 365 / Entra (agent tenant)"
G=https://graph.microsoft.com
graph DELETE "$G/v1.0/users/${AGENT_UPN}"                                   # agent user (soft-deleted 30 days)
[ -n "${A365_AGENT_ID:-}" ] && graph DELETE "$G/beta/servicePrincipals/${A365_AGENT_ID}"   # agent identity
tok=$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv)
gid=$(curl -s -H "Authorization: Bearer $tok" "$G/v1.0/groups?\$filter=mailNickname%20eq%20'agent365demo'&\$select=id" \
      | python -I -c "import json,sys;v=json.load(sys.stdin).get('value',[]);print(v[0]['id'] if v else '')")
[ -n "$gid" ] && graph DELETE "$G/v1.0/groups/$gid"                          # demo SharePoint site (group, soft-deleted)
if $YES; then (cd "$root/src/DemoAgent" && a365 cleanup blueprint -y); else echo "DRY: a365 cleanup blueprint -y   (blueprint app + SP + secrets)"; fi

echo "== 2. Azure (backend subscription)"
run az cognitiveservices account deployment delete --subscription "$AZURE_SUBSCRIPTION_ID" \
    -g "$AZURE_OPENAI_RESOURCE_GROUP" -n "$AZURE_OPENAI_ACCOUNT" --deployment-name agent365-chat
run az group delete --subscription "$AZURE_SUBSCRIPTION_ID" -n "${AZURE_RESOURCE_GROUP:-dsc-p1-rg-agent365}" --yes
echo "   note: Key Vault stays soft-deleted for 7 days; purge with"
echo "   az keyvault purge --subscription <sub> -n dsc-p1-kv-agent365"

echo "== 3. GitHub"
if $GITHUB; then run gh api -X DELETE repos/fiddi/agent365-demo/environments/demo; else echo "skip (use --github to delete environment 'demo' and its secrets)"; fi

echo "== Done$($YES || echo ' (dry run – nothing was deleted)')"
