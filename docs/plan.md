# Implementation Plan

Estimated effort: ~4–6 person-days for a working demo. Phases are sequential; Phase 0 de-risks
the cross-tenant identity setup before any real code is written.

## Phase 0 – Prerequisites & spike (0.5–1 d)

- [x] Frontier preview / Agent 365 enabled in M365 tenant (CLI can't verify automatically – warning only).
- [x] Licenses checked: Agent 365 (25 free), Copilot (3 free), Office E5 (6 free); **no free Teams license** (see R1).
- [x] Global Admin of the M365 tenant used for consent (dsc@fiddi.ch).
- [x] Azure backend subscription access (Owner) confirmed.
- [x] Reuse existing Azure OpenAI account (Switzerland North); new deployment `agent365-chat` in Phase 1.
- [x] `a365` CLI updated to 2.0.4.
- [x] Agent 365 skills installed (user scope).
- [x] Sample agent (.NET 10, Agent Framework) imported to `src/DemoAgent`, persona "Ava", keyless AOAI auth.
- [x] Pre-commit hook blocks tenant/subscription/blueprint IDs and client secrets.
- [x] **Spike result:** blueprint `Ava Blueprint` created in the **M365 tenant** (multitenant flag) via
      `a365 setup all --agent-name Ava --aiteammate --m365`; inheritable permissions + tenant-wide admin consent granted.
      Backend tenant has no Agent 365 → identity lives in the M365 tenant, backend authenticates with
      blueprint secret from Key Vault (later: cross-tenant MI FIC). See architecture AD "identity placement".
- [ ] Rotate the blueprint secret into Key Vault (first secret was shown in CLI output) – Phase 1.
- [ ] Agent instance + agent user `ava@fiddi.ch` – created after publish/instance request (Phase 4 flow).

**Exit:** agent user exists in the M365 tenant and has a mailbox; chosen identity variant documented.

## Phase 1 – Azure infrastructure (0.5 d)

- [x] `infra/main.bicep` (subscription scope) + `modules/core.bicep`: RG `dsc-p1-rg-agent365`, App Service B1 Linux (.NET 10),
      UAMI, Key Vault (RBAC), Storage (no shared key), Log Analytics + App Insights.
- [x] `modules/openai-deployment.bicep`: deployment `agent365-chat` (gpt-5.4-mini, GlobalStandard 50) on the existing AOAI account.
- [x] RBAC: app UAMI → `Cognitive Services OpenAI User`, `Storage Blob Data Contributor`, `Key Vault Secrets User`.
- [x] Blueprint secret rotated: new secret created directly into Key Vault (`blueprint-client-secret`), CLI-shown secret deleted.
      App settings reference it via Key Vault reference.
- [x] GitHub OIDC: user-assigned identity `dsc-p1-github-agent365-uaid` with federated credential
      `repo:fiddi/agent365-demo:environment:demo` (Website Contributor on the web app); secrets in GitHub environment `demo`.
- [x] Workflows: `ci.yml` (build + bicep + placeholder check), `deploy.yml` (publish → App Service, health check).
- [x] Deploy with `infra/deploy.sh` (reads `.env`); `infra/deploy.sh what-if` for a dry run.

## Phase 2 – Agent skeleton (1 d)

- [x] `src/DemoAgent` from Agent 365 .NET sample (AI teammate template) – done in Phase 0.
- [x] `/api/messages` requires a valid Agents SDK JWT outside Development/Playground (401 for anonymous); `/api/health` → 200.
- [x] Azure OpenAI chat via user-assigned MI (`AIServices__AzureOpenAI__ManagedIdentityClientId`).
- [x] Key Vault references for the blueprint secret resolved (refresh after secret creation, then restart).
- [x] Local-only files (`appsettings.Development.json`, `a365*.json`) excluded from publish output.
- [x] Deployed (zip deploy; GitHub `deploy.yml` does the same after merge to `main`).
- [x] Messaging endpoint registered: `a365 setup blueprint --endpoint-only --messaging-endpoint https://<app>/api/messages`.
      Note: the CLI re-stamps IDs into `appsettings.json` – run `git checkout -- src/DemoAgent/appsettings.json` afterwards.
- [ ] Local test with Agents Playground (`test-local` skill) – optional.
- [ ] Teams chat test – needs the agent instance (published app + instance request, Phase 4).

**Exit:** chat with the agent in Teams (M365 tenant) returns LLM answers served from the backend.

## Phase 3 – Capabilities (1.5 d)

- [x] **C1** Email notification handler (`OnAgenticEmailNotification`): replies via `EmailResponse` to internal senders only; external senders are ignored.
- [x] **C2** Work IQ Mail MCP + **code-level recipient guard** (`Tools/RecipientGuard.cs`): send/reply/forward tools are wrapped and
      blocked if any address is outside `Guardrails:AllowedEmailDomains`. The prompt says the same, but the guard also holds under prompt injection.
      Limitation: a reply by message ID goes to the original sender – covered because external senders are never answered.
- [x] **C3** `mcp_OneDriveRemoteServer` + `mcp_SharePointRemoteServer` added to ToolingManifest.
- [x] `a365 setup permissions mcp` (provisioned 2 missing Agent 365 Tools service principals; admin consent already granted).
- [x] System prompt: persona Ava, user's language, guardrails; email content treated as data.
- [x] **C4** Welcome on members added, hire message on install.
- [x] **Proactive:** on hire, Ava emails a short welcome to the person who hired her (internal addresses only, best effort).
- [x] SharePoint site **Agent365 Demo** (M365 group `agent365demo`) with sample documents in `Demo/` (`demo/sample-docs`).
- [ ] Add Ava's agent user as member of the group once it exists (Phase 4).

## Phase 4 – Publish to Teams & Copilot (0.5 d)

- [x] `a365 publish` → package (manifest branded "Ava", developer = this repo); uploaded in the M365 admin center.
- [x] Developer Portal: notification URL = `https://<app>/api/messages` (already registered by the CLI).
- [ ] ~~Activate agent / approve instance in admin center~~ – **blocked by an admin center bug**: the default policy
      template requires ProductSkuId `304b93a3-…` (not in Microsoft's public SKU list), the tenant owns Agent 365 SKU
      `796a6fb4-…` (AGENT_365); the custom template wizard does not recognise it either. Microsoft support ticket open.
- [x] **Workaround via Microsoft Graph** – `scripts/create-agent-user.py` (idempotent):
      agent identity "Ava" (created by the blueprint), agent user `ava@fiddi.ch` (admin token), and delegated consents
      mirrored from the blueprint plus `Tools.ListInvoke.All` (all Work IQ MCP servers) and Graph `User.Read`.
      Licenses assigned via Graph: Agent 365, Office 365 E5 (no Teams), M365 Copilot. Ava added to the demo group.
- [x] Fix: `ServiceConnection` scope must be the Messaging Bot API (`5a807f24-…/.default`), not the blueprint ID.
- [x] Fix: sample transcript logger removed (crashed on `EmailResponse`, wrote PII to disk); loop guard for own mails,
      auto-replies and bounces.
- [x] **C1–C3 verified:** email from an internal user → Ava reads the SharePoint document → exactly one reply.
- [ ] **C4/C5** Teams chat and M365 Copilot – need a Teams license for Ava and/or the admin center activation (R1, R4).

## Phase 5 – Observability & governance (0.5 d)

- [x] Agent 365 observability exporter enabled (`EnableAgent365Exporter=true`, S2S route, app-only token for the
      agent identity via the blueprint). Fix: the provider reads `Agent365Observability:BlueprintClientSecret`
      (was set as `ClientSecret`). Token acquisition for the observability resource verified.
- [ ] Verify spans in the M365 admin center (Agents → Ava → Activity) after the next real email turn.
- [x] Sponsor: `dsc@fiddi.ch` on the agent identity.
- [ ] ~~Conditional Access (report-only) for the agent identity~~ – **skipped**: the tenant has no Entra ID P1/P2;
      Graph returns 403 "tenant is not licensed" (the Agent 365 plan `ENTRA_CONDITIONAL_ACCESS_FOR_AGENTS` alone is
      not enough). `scripts/create-ca-policy.py` is ready (report-only, block on medium/high agent risk) for tenants
      with P1/P2 – see R5.
- [ ] Optional: `a365-code-validator` skill against the observability code.

## Phase 6 – Demo hardening (0.5 d)

- [x] Demo script `docs/demo-script.md` (identity, email, files + language, guardrails incl. prompt injection,
      governance/observability; Teams/Copilot optional).
- [x] Seed files in the SharePoint site "Agent365 Demo" (done in Phase 3, `demo/sample-docs`).
- [x] `scripts/teardown.sh` – dry run by default; `--yes` deletes agent user, agent identity, demo group,
      blueprint (`a365 cleanup blueprint`), model deployment and resource group; `--github` removes the environment.

## Optional / later

- Onboard a second M365 tenant to prove multitenancy.
- Purview DLP on prompts (`purview-dlp-integration` skill).
- Calendar tools (meeting scheduling).
