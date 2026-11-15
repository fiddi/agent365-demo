# Agent 365 Demo

A minimal **Microsoft Agent 365** agent with its **own identity** (Entra Agent ID + its own user
account with mailbox and Teams presence). It receives and sends email, reads files from
OneDrive/SharePoint, and talks to people in Teams and Microsoft 365 Copilot.

| | Where | Configured via |
|---|---|---|
| Backend (Azure, multitenant) | backend tenant / subscription | `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` |
| Agent (Microsoft 365) | M365 tenant | `A365_TENANT_ID` |

Tenant and subscription IDs are **not** stored in this repo. Copy `.env.example` to `.env`
(git-ignored) and fill in your values.

## Docs

- [Solution architecture](docs/architecture.md)
- [Implementation plan](docs/plan.md) – status per phase
- [Open design questions, decisions and risks](docs/open-questions.md)
- [Demo script](docs/demo-script.md) – ~10-minute walkthrough

## Repository layout

```
docs/                    architecture, plan, decisions, demo script
infra/                   Bicep (subscription scope) + deploy.sh (reads .env)
src/DemoAgent/           .NET 10 agent backend (Agents SDK, Agent Framework, Work IQ MCP)
scripts/
  create-agent-user.py   agent identity + agent user + consents via Graph (admin center workaround)
  create-ca-policy.py    report-only Conditional Access policy for the agent identity (needs Entra ID P1/P2)
  teardown.sh            removes everything (dry run by default)
demo/sample-docs/        documents for the "Agent365 Demo" SharePoint site
.githooks/               pre-commit guard against tenant/subscription IDs and secrets
.github/workflows/       CI (build, Bicep, ID check) and deploy via OIDC
```

## Status

| Capability | Status |
|---|---|
| Own identity (blueprint, agent identity, agent user with mailbox) | ✅ (agent user created via Graph – admin center activation blocked, R4) |
| Receive and answer email | ✅ |
| Several instances of one blueprint (e.g. "Ava", "Peter Helfer"), each with own name, mailbox and telemetry | ✅ (`scripts/create-agent-user.py --name … --upn …`) |
| Read files from SharePoint/OneDrive (Work IQ MCP) | ✅ |
| Send email, internal domains only (enforced in code) | ✅ |
| Agent 365 observability exporter | ✅ enabled, admin center view not yet verified |
| Teams chat / Microsoft 365 Copilot | ⏳ needs a Teams license and the admin center activation |
| Conditional Access for the agent | ⏸ skipped – tenant has no Entra ID P1/P2 (R5) |

Setup: `git config core.hooksPath .githooks`, copy `.env.example` to `.env`, then follow [docs/plan.md](docs/plan.md).
