# Deployment

Specifics-level reference for how this repo's Databricks Asset Bundle (DAB) is
structured and deployed. Assumes familiarity with DABs in general; see the
[README](../README.md) for the basic getting-started commands. This doc goes
deeper on the two-target model, auth, and the CI/CD plan.

## Overview

Bundle name: `jdac6thedition_ai_dev_kit` (`databricks.yml`, `bundle.name`).

There are two targets: `dev` (default) and `prod`. Both point at the same
workspace host, `https://adb-7405607396630555.15.azuredatabricks.net`.

Core commands, run from the repo root:

```bash
databricks bundle validate --strict -t <target> --profile <profile>
databricks bundle deploy -t <target> --profile <profile>
databricks bundle run -t <target> --profile <profile>
databricks bundle summary -t <target> --profile <profile>
```

`-t dev` can be omitted since `dev` is `default: true`. Locally this repo uses
`--profile DEFAULT` throughout (see Local auth below).

## Targets

### `dev`

- `mode: development` — DABs prefixes resource names (e.g. `[dev <user>]`),
  applies dev tags, and marks pipelines `development: true`.
- `default: true` — the target used when `-t` is omitted.
- `variables.catalog: databricks_user_group_aitoolkit`.
- No `git:` branch restriction — deployable from any branch/state.
- Has a target-specific override for the `wanderbricks_genie_space` resource:
  Genie space `file_path` content is a serialized JSON body that does not go
  through bundle variable substitution, so the fully-qualified dev schema name
  has to be hardcoded in a separate file
  (`src/genie/wanderbricks_gold.dev.geniespace.json`) rather than templated.
  `prod` uses the original, unprefixed genie space file.

### `prod`

- `mode: production`.
- `git: branch: main` — a deploy guard: `databricks bundle deploy -t prod`
  fails unless the working tree is on `main`. This check fires at deploy time,
  not at `validate` time.
- `run_as: service_principal_name: ${var.run_as_service_principal}` — prod
  resources run as a service principal, not as whichever human deploys. The
  application ID is resolved via the `run_as_service_principal` variable's
  `lookup: service_principal: databricks_user_group_job_sp`.
- `workspace.root_path: /Workspace/.bundle/${bundle.name}/${bundle.target}` —
  explicit root path (dev uses the DABs default).
- `permissions: CAN_MANAGE` granted to `bjamrozik@origindigital.com`.
- `variables.catalog: databricks_user_group_aitoolkit` — **the same catalog as
  `dev`.**

### Shared workspace, no catalog-level isolation

Both targets deploy to the same workspace host and the same Unity Catalog
catalog (`databricks_user_group_aitoolkit`). This is a deliberate deviation
from the more typical dev/prod-catalog split, decided and documented in
`docs/presentation/wanderbricks-demo-spec.md` (see its "Environment" section):
a separate-catalog approach was considered and declined. Environment
separation instead comes entirely from:

- `mode: development` vs `mode: production` behaviors (resource name
  prefixing/tagging, pipeline `development` flag, etc.), and
- schema/resource-prefix naming under the shared catalog.

There is no catalog-level blast-radius isolation between dev and prod in this
bundle — keep that in mind when granting permissions or writing
destructive/DDL logic.

## Local auth

This repo authenticates via a named Databricks CLI profile, `DEFAULT`, used
consistently across the README's commands and this doc's examples. Profiles
are configured in `~/.databrickscfg` (via `databricks configure` or
`databricks auth login`) and selected per-command with `--profile <name>`. See
the `databricks-core` skill for authentication/profile setup help.

CI does not use profile-based auth — see CI/CD (planned) below.

## Resource layout

Resources are defined in `resources/*.yml` and wired into the bundle via the
top-level `include: - resources/*.yml` directive in `databricks.yml`. Each
file follows the naming convention `<name>.<resource_type>.yml`, e.g.:

- `jdac6thedition_ai_dev_kit.schema.yml` — a Unity Catalog schema resource
- `jdac6thedition_ai_dev_kit_etl.pipeline.yml`, `wanderbricks_gold_pipeline.pipeline.yml` — pipelines
- `sample_job.job.yml`, `wanderbricks_gold_job.job.yml` — jobs
- `wanderbricks_warehouse.warehouse.yml` — a SQL warehouse
- `wanderbricks_dashboard.dashboard.yml` — a Lakeview/AI-BI dashboard
- `wanderbricks_genie_space.genie_space.yml` — a Genie space

Adding a new resource means dropping a new `<name>.<resource_type>.yml` file
under `resources/`; the glob include picks it up automatically. For what each
resource actually does (business purpose), see `docs/wanderbricks.md`.

## Running tests locally

```bash
uv run pytest
```

`tests/conftest.py` initializes a real `DatabricksSession` (Databricks
Connect) as a pytest fixture — there is no local/mocked Spark session. This
means `uv run pytest` requires a working, authenticated connection to a
Databricks workspace before it can run (the same profile-based auth as bundle
commands). If no compute is configured, `conftest.py` falls back to serverless
compute automatically (`DATABRICKS_SERVERLESS_COMPUTE_ID=auto`).

## CI/CD (planned)

**Status: planned, not yet implemented.** No `.github/workflows/` exist in
this repo yet. The full task-by-task implementation plan lives at
[`docs/superpowers/plans/2026-09-10-github-actions-cicd.md`](superpowers/plans/2026-09-10-github-actions-cicd.md)
— treat that plan as the source of truth; this section is a pointer/summary,
not a duplicate.

Planned approach, in brief:

- **Auth:** OAuth workload identity federation (OIDC) — GitHub-issued OIDC
  tokens exchanged for short-lived Databricks OAuth tokens
  (`DATABRICKS_AUTH_TYPE: github-oidc`). No Databricks PAT, client secret, or
  other long-lived credential is stored in GitHub. All workflows authenticate
  as the same existing service principal already wired into `databricks.yml`
  (`databricks_user_group_job_sp`), differentiated by a separate federation
  policy per GitHub trigger/Environment.
- **Workflow split:**
  - `validate.yml` — runs on every pull request; `databricks bundle validate
    --strict` across both `dev` and `prod` targets, plus `uv run pytest`.
  - `deploy-dev.yml` — runs on push to `main`; deploys `dev` automatically.
  - `deploy-prod.yml` — `workflow_dispatch`-only (never triggered
    automatically), gated by a required-reviewer approval on the GitHub
    `prod` Environment.
- **GitHub Environments:** `dev` (no protection rules) and `prod` (required
  reviewer, at minimum `bjamrozik@origindigital.com`) — the approval gate for
  prod deploys lives in GitHub's Environment protection rules, not in the
  workflow YAML itself. The existing `git: branch: main` guard on `prod` in
  `databricks.yml` remains the deploy-time backstop.

**Before this can run**, it needs setup that requires account-admin-level
Databricks access and GitHub repo-admin access — neither of which is available
from the workspace-level `DEFAULT` profile:

1. An account-level Databricks CLI profile (for
   `databricks account service-principal-federation-policy create`).
2. The Azure Databricks account ID.
3. The service principal's numeric ID (distinct from its application ID
   already used as `run_as_service_principal`).
4. Creating the `dev` and `prod` GitHub Environments and configuring the
   required reviewer on `prod`.

The plan's Task 1 produces an OIDC setup runbook
(`docs/ci-cd/oidc-setup.md`, not yet created) with the exact commands for all
four items — see the plan doc linked above for details.
