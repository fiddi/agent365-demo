# Design Decisions & Open Questions

## Decided

| # | Topic | Decision |
|---|-------|----------|
| D1 | Stack | .NET 10 |
| D2 | LLM | Azure OpenAI – existing account `dsc-p1-model-eo3aez4xziljo`, new deployment `agent365-chat` |
| D3 | Licensing | M365 tenant is Frontier-enabled; Agent 365, Copilot and Office E5 seats available |
| D4 | Repository | `fiddi/agent365-demo`, public, **no IDs committed** (`.env` + GitHub secrets) |
| D5 | Naming | `dsc-p1-<type>-agent365`, Switzerland North |
| D6 | Hosting | Azure App Service (Linux) |
| D7 | Sponsor | `dsc@fiddi.ch` (Global Administrator in the M365 tenant) |
| D8 | Agent | "Ava", `ava@fiddi.ch`, answers in the sender's language |
| D9 | Files | New SharePoint site "Agent365 Demo" with sample documents |
| D10 | Email | Agent sends mail (replies + proactive) to internal domains only |
| D11 | Behaviour | Reactive and proactive (welcome mail on install, follow-ups) |
| D12 | CI/CD | GitHub Actions with OIDC into the backend tenant; IDs as repository secrets |
| D13 | Conditional Access | Demo policy for the agent identity in report-only mode |
| D14 | Git workflow | Branch + PR per phase |
| D15 | Stop points | None besides interactive admin sign-ins |
| D16 | Identity placement | Blueprint in M365 tenant; secret in Key Vault, then FIC (see architecture §3) |

## Open / risks

| # | Item | Mitigation |
|---|------|-----------|
| R1 | No free Teams license in the M365 tenant (Teams EEA 2/2 used). The agent user may need one for Teams presence. | Check whether Agent 365 / Copilot licensing covers agent users; otherwise free up or buy one Teams seat. |
| R2 | Cross-tenant FIC on an agent blueprint is not documented. | Keep the Key Vault secret if FIC is rejected. |
| R3 | Work IQ MCP is in preview. | Fall back to Microsoft Graph calls for mail/files if a server is unavailable. |
