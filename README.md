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
- [Implementation plan](docs/plan.md)
- [Open design questions](docs/open-questions.md)

## Repository layout (target)

```
docs/                 architecture, plan, decisions
infra/                Bicep for the backend tenant (Phase 1)
src/DemoAgent/        .NET 10 agent backend (Phase 2+)
a365.config.sample.json
.github/workflows/    infra + app deployment via OIDC
```

## Status

Design phase. No code deployed yet.
