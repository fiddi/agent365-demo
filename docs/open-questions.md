# Open Design Questions

## Decided (2026-11-14)

| # | Question | Decision |
|---|----------|----------|
| D1 | Stack | .NET 10 |
| D2 | LLM | Azure OpenAI in Foundry (backend tenant) |
| D3 | Frontier / licensing | The M365 tenant is Frontier-enabled with Copilot licenses → Agentic-User mode + Work IQ MCP |
| D4 | Repository | `fiddi/agent365-demo`, public |

## Still open

| # | Question | Proposed default |
|---|----------|------------------|
| Q1 | Azure subscription to use? | Stored locally in `.env` (`AZURE_SUBSCRIPTION_ID`), never committed |
| Q2 | Azure region for compute and for Azure OpenAI? | Switzerland North (compute) / Sweden Central (AOAI, broad model availability) |
| Q3 | Which model? | `gpt-4.1` (cost-effective, tool calling) – or `gpt-5-mini` if available in region |
| Q4 | Agent name, UPN and persona? | "Ava – Demo Agent", `ava@<m365-domain>`, friendly assistant tone |
| Q5 | Who is sponsor of the blueprint / agent identity? | Project owner (user account in the M365 tenant) |
| Q6 | Which SharePoint site / OneDrive does the agent read files from? | One dedicated demo SharePoint site shared with the agent user |
| Q7 | Email guardrail: who may the agent send mail to? | Only internal domains of the M365 tenant |
| Q8 | Should the agent proactively email (e.g. daily digest) or only react? | React only (simpler) |
| Q9 | Is a second customer tenant available to demonstrate multitenancy? | Not in scope v1 |
| Q10 | Hosting: App Service OK, or prefer Container Apps / AKS? | App Service |
| Q11 | Identity variant: multitenant blueprint in the backend tenant (preferred) vs. single-tenant blueprint in the M365 tenant | Decided by Phase 0 spike |
