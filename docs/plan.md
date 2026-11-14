# Implementation Plan

Estimated effort: ~4–6 person-days for a working demo. Phases are sequential; Phase 0 de-risks
the cross-tenant identity setup before any real code is written.

## Phase 0 – Prerequisites & spike (0.5–1 d)

- [ ] Confirm Frontier preview is active in M365 tenant; Agent 365 enabled in admin center.
- [ ] Confirm licenses: Microsoft 365 Copilot (for agent user + Work IQ), E7 or Agent 365 for ≥1 user (observability).
- [ ] Global Admin of the M365 tenant available for consent; Agent ID Developer role for the builder.
- [ ] Azure backend subscription with Owner/Contributor + User Access Administrator on the RG.
- [ ] Azure OpenAI quota for the chosen model in the chosen region.
- [ ] Update `a365` CLI (`dotnet tool update -g Microsoft.Agents.A365.DevTools.Cli`, currently 1.1.226 → 2.x).
- [ ] Install Agent 365 skills: `gh skill add microsoft/agent365-skills`.
- [ ] **Spike:** create multitenant blueprint in the backend tenant, consent in the M365 tenant, create agent instance + agent user.
      If not supported → switch to fallback (single-tenant blueprint in the M365 tenant with cross-tenant MI FIC). Record result as ADR.

**Exit:** agent user exists in the M365 tenant and has a mailbox; chosen identity variant documented.

## Phase 1 – Azure infrastructure (0.5 d)

- [ ] `infra/main.bicep`: RG resources (App Service, UAMI, KV, Storage, App Insights; model deployment on the existing AOAI account).
- [ ] RBAC: UAMI → `Cognitive Services OpenAI User`, `Storage Blob Data Contributor`, `Key Vault Secrets User`.
- [ ] GitHub Actions OIDC federated credential (app registration in the backend tenant), workflow `infra.yml`.
- [ ] Deploy; verify `https://<app>.azurewebsites.net/healthz`.

## Phase 2 – Agent skeleton (1 d)

- [ ] `src/DemoAgent` from Agent 365 .NET sample (AI teammate template).
- [ ] `/api/messages` with Agents SDK JWT validation; health endpoint.
- [ ] Echo handler for Teams messages; Azure OpenAI chat via MI.
- [ ] Local test with Agents Playground (`test-local` skill).
- [ ] Workflow `app.yml`: build, test, deploy to App Service.
- [ ] Register messaging endpoint on blueprint: `a365 setup blueprint --endpoint-only <url>/api/messages`.

**Exit:** chat with the agent in Teams (M365 tenant) returns LLM answers served from the backend.

## Phase 3 – Capabilities (1.5 d)

- [ ] **C1** Email notification handler (incoming mail → activity).
- [ ] **C2** Work IQ Mail MCP: reply / send mail as agent user; recipient domain guardrail.
- [ ] **C3** Work IQ OneDrive/SharePoint MCP: search + read file content (text, docx, pdf).
- [ ] `a365 develop add-mcp-servers` → ToolingManifest; `a365 setup permissions mcp`; admin consent.
- [ ] Tool allow-list + system prompt (persona, guardrails).
- [ ] **C4** Teams: 1:1, group chat, @mention; welcome message on install.
- [ ] Lifecycle handler (agent user created → hello email to sponsor).

## Phase 4 – Publish to Teams & Copilot (0.5 d)

- [ ] Configure blueprint in Developer Portal (messaging, Teams & email channels).
- [ ] `a365 publish` → app package; upload in M365 admin center; make available in Copilot agent store.
- [ ] **C5** Verify agent can be added and used in M365 Copilot.

## Phase 5 – Observability & governance (0.5 d)

- [ ] Agent 365 observability exporter (`instrument-observability` skill); `invoke_agent` root span.
- [ ] Verify spans in Defender, Purview, M365 admin center; App Insights dashboards.
- [ ] Sponsor, Conditional Access policy demo (e.g. block agent identity outside working hours).
- [ ] Validate with Agent 365 validation checklist / `a365-code-validator`.

## Phase 6 – Demo hardening (0.5 d)

- [ ] Demo script (`docs/demo-script.md`): 5-minute walkthrough of C1–C6.
- [ ] Seed files in a SharePoint site for the "summarise the deck" scenario.
- [ ] Teardown script (`a365 cleanup`, `az group delete`).

## Optional / later

- Onboard a second M365 tenant to prove multitenancy.
- Purview DLP on prompts (`purview-dlp-integration` skill).
- Calendar tools (meeting scheduling).
