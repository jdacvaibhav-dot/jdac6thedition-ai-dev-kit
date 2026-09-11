# GitHub Actions CI/CD for the Bundle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run `databricks bundle validate`/`deploy` for this repo's DABs bundle (`jdac6thedition_ai_dev_kit`) through GitHub Actions: validate every PR, auto-deploy to `dev` on merge to `main`, and deploy to `prod` only via a manually-triggered, approval-gated workflow.

**Architecture:** Three workflow files under `.github/workflows/`, all authenticating to Databricks via **OAuth workload identity federation (OIDC)** — no long-lived Databricks secrets stored in GitHub at all. `validate.yml` runs on every pull request (bundle validate for both targets, plus the existing pytest suite against serverless compute). `deploy-dev.yml` runs on push to `main` and deploys `dev` automatically. `deploy-prod.yml` is `workflow_dispatch`-only, gated by a GitHub Environment (`prod`) that requires manual reviewer approval — matching this project's existing stance that prod deploys are deliberate, infrequent actions (the Wanderbricks demo spec explicitly keeps prod deploy out of the live demo). All three reuse the single service principal (`databricks_user_group_job_sp`) already wired into `databricks.yml` as `run_as_service_principal`, federated separately per GitHub Environment.

**Tech Stack:** GitHub Actions, `databricks/setup-cli` action, Databricks CLI v1.16.0+, Databricks OAuth token federation (workload identity), `uv` (existing project tooling).

**Spec:** No separate spec document exists for this work — it originates from a direct user request ("run this with a GitHub Actions CI/CD process — plan that out"). This plan's Global Constraints section is therefore the authoritative requirements source; every non-obvious decision below is justified inline rather than traced back to a spec line.

## Global Constraints

- **Auth mechanism: OIDC workload identity federation, not stored secrets.** Databricks' current recommendation for GitHub Actions (confirmed via Databricks' own GitHub Actions integration docs, both the AWS/GCP and Azure-specific pages — this workspace is Azure, host `https://adb-7405607396630555.15.azuredatabricks.net`) is `DATABRICKS_AUTH_TYPE: github-oidc` with the CLI/SDK exchanging a GitHub-issued OIDC token for a short-lived Databricks OAuth token. No `DATABRICKS_TOKEN`, client secret, or PAT is stored in GitHub at any point in this plan.
- **Repo identity (exact, not a placeholder):** GitHub org/repo is `jdacvaibhav-dot/jdac6thedition-ai-dev-kit` (confirmed via `git remote -v`). Every federation-policy `subject` value below uses this exact string.
- **Reused identity:** all three workflows authenticate as the existing service principal `databricks_user_group_job_sp` (already looked up in `databricks.yml` via the `run_as_service_principal` variable and already used as `prod`'s `run_as`). No new service principal is created — this keeps exactly one non-human identity to audit instead of three.
- **GitHub Environments:** two Environments must exist in the repo's Settings → Environments: `dev` (no protection rules — CI's `deploy-dev.yml` runs unattended) and `prod` (required reviewers = at minimum `bjamrozik@origindigital.com`'s GitHub account — CI's `deploy-prod.yml` pauses for approval before it can run). The PR-triggered `validate.yml` job does **not** declare a `environment:` — it authenticates via a separate, lower-privilege federation policy scoped to the `pull_request` event, not to either deploy environment.
- **One federation policy per GitHub Environment/event-type, all pointed at the same service principal:**

  | Policy purpose | GitHub-side trigger | Entity type | `subject` value |
  |---|---|---|---|
  | PR validate (read-only) | `pull_request` (any branch) | Branch | `repo:jdacvaibhav-dot/jdac6thedition-ai-dev-kit:pull_request` |
  | Deploy to `dev` | `push` to `main`, `environment: dev` | Environment | `repo:jdacvaibhav-dot/jdac6thedition-ai-dev-kit:environment:dev` |
  | Deploy to `prod` | `workflow_dispatch`, `environment: prod` | Environment | `repo:jdacvaibhav-dot/jdac6thedition-ai-dev-kit:environment:prod` |

  The `pull_request` subject is stable across every PR and branch in this repo (GitHub always issues `repo:OWNER/REPO:pull_request` for `pull_request`-triggered jobs, regardless of which branch opened the PR) — confirmed against GitHub's own OIDC subject-claim documentation.
- **Existing prod git-branch guard stays authoritative.** `databricks.yml`'s `prod` target already enforces `git: branch: main` (added in the Wanderbricks SDD plan, commit `10e50fd`) — `deploy-prod.yml` does not need to re-implement a branch check; a `workflow_dispatch` run from a non-`main` ref will still be rejected by the CLI itself at deploy time (confirmed behavior: the guard fires on `bundle deploy`, not `bundle validate`).
- **`databricks bundle validate` in CI never uses `--profile`.** Locally this repo authenticates via the named CLI profile `DEFAULT`; in GitHub Actions there is no `.databrickscfg` file, so every CLI invocation in every workflow in this plan relies purely on the `DATABRICKS_AUTH_TYPE`/`DATABRICKS_HOST`/`DATABRICKS_CLIENT_ID` environment variables set on the job — never pass `--profile` in CI.
- **Testing approach for the workflow YAML itself:** these files cannot be unit-tested locally without actually running them on GitHub's runners (which requires a push/PR — a real side effect this plan doesn't take without explicit approval per the "actions visible to others" rule). Verification in each task below is therefore: (a) YAML syntax validity (`python -c "import yaml; yaml.safe_load(open(...))"`), (b) `actionlint` if available locally (a static analyzer for GitHub Actions YAML — flags unknown keys, bad expressions, missing permissions), and (c) a manual read-through confirming the `env:`/`permissions:`/`environment:` blocks match this Global Constraints table exactly. Actually exercising the workflows (opening a real PR, merging to `main`, or running `workflow_dispatch`) is the executor's / Bradley's action to take after this plan's tasks are merged, not something a task in this plan does itself.
- **pytest in CI:** yes, `uv run pytest` runs as a second job in `validate.yml`, using the existing `tests/conftest.py` serverless-compute fallback (`DatabricksSession.builder.getOrCreate()` auto-falls-back to `DATABRICKS_SERVERLESS_COMPUTE_ID=auto` when no compute is configured — no CI-specific compute setup needed). This only works because CI authenticates to a real workspace via OIDC — the same identity as the validate job, no separate credential.

---

## ⚠️ Needs Bradley before Task 1 can be fully executed

These require **account-level** Databricks CLI access (a different auth surface than the workspace-level `DEFAULT`/`ORIGINOS` profiles currently in `.databrickscfg`) and/or GitHub repo-admin access — an agent working from the workspace-level `DEFAULT` profile cannot create these on its own:

1. **An account-level CLI profile.** Bradley needs an account admin login configured for `databricks account service-principal-federation-policy create` (this is an *account* API, not a *workspace* API — a workspace profile like `DEFAULT` cannot call it). Run `databricks auth login --account-id <account-id>` (or add an `[ACCOUNT]` profile to `.databrickscfg`) if one doesn't already exist.
2. **The account ID.** Needed as the federation policy's `audiences` value (Databricks' own recommendation: set `audiences` to the Azure Databricks account ID). Find it in the account console URL or via `databricks account metastore-assignments ...` — Task 1 below includes the exact lookup command; Bradley runs it once account CLI access exists.
3. **The service principal's numeric ID** (distinct from its application/client ID already used as `run_as_service_principal`). Task 1 includes the exact lookup command using the application ID this repo already has.
4. **Creating the two GitHub Environments** (`dev`, `prod`) in the repo's Settings → Environments, and adding Bradley (or another designated approver) as a required reviewer on `prod`. This is a GitHub UI/API action requiring repo-admin permission — Task 1 documents the exact steps but cannot perform them from the CLI.

Task 1 below produces a runbook document with the exact commands for all four items, so Bradley (or whoever holds these credentials) can execute them in one pass — it does not attempt to run them itself.

---

### Task 1: OIDC prerequisite runbook (Needs Bradley to execute; this task only documents it)

**Files:**
- Create: `docs/ci-cd/oidc-setup.md`

**Interfaces:**
- Consumes: `databricks.yml`'s existing `run_as_service_principal` variable (application ID of `databricks_user_group_job_sp`, already resolved via `lookup: service_principal: databricks_user_group_job_sp`).
- Produces: a runbook document. Nothing in this plan is machine-consumed from it — Tasks 2–4's workflow YAML hardcode the `DATABRICKS_CLIENT_ID` value (the service principal's application ID, which is already known and public within the workspace config — it is not a secret) directly, since it's the same value already committed in `databricks.yml`. The three federation policies this runbook has Bradley create are what makes those `DATABRICKS_CLIENT_ID` values actually usable from GitHub's runners; without them, Tasks 2–4's workflows will authenticate-fail (a safe, visible failure — not a silent one).

- [ ] **Step 1: Look up the service principal's application ID (already known, just confirm it hasn't changed)**

```bash
databricks bundle validate -t prod --profile DEFAULT -o json | jq -r '.variables.run_as_service_principal.value // .variables.run_as_service_principal.default'
```

Expected: a UUID-shaped application ID. Record it — it's the value that goes in every workflow's `DATABRICKS_CLIENT_ID` below (Tasks 2–4).

- [ ] **Step 2: Write the runbook**

```markdown
# Databricks OIDC Federation Setup for GitHub Actions

Run these once, from an account-admin-authenticated shell (NOT the workspace `DEFAULT` profile —
these are account-level APIs). One-time setup; re-run only if the service principal or repo changes.

## 0. Prerequisites

- An account-level CLI profile with account-admin privileges. If you don't have one:
  `databricks auth login --host https://accounts.azuredatabricks.net --account-id <your-account-id>`
  (find `<your-account-id>` in the Azure Databricks account console URL, or via your Azure AD tenant's
  Databricks account configuration — this is account-console metadata, not something the CLI can discover
  from a workspace profile).

## 1. Find the service principal's numeric ID

The application ID (`run_as_service_principal`, already in `databricks.yml`) is a UUID; federation
policies key off the *numeric* internal ID instead.

```bash
APP_ID=$(databricks bundle validate -t prod --profile DEFAULT -o json | jq -r '.variables.run_as_service_principal.value // .variables.run_as_service_principal.default')
databricks account service-principals list --account-id <your-account-id> --profile <your-account-profile> \
  | jq --arg app "$APP_ID" '.[] | select(.applicationId == $app) | .id'
```

Record the numeric `id` this prints — call it `SP_NUMERIC_ID` below.

## 2. Create three federation policies (one per GitHub trigger context)

All three point at the same service principal (`SP_NUMERIC_ID`) and the same GitHub repo
(`jdacvaibhav-dot/jdac6thedition-ai-dev-kit`) — they differ only in `subject` (which GitHub
event/environment is allowed to mint a token this service principal will accept) and `audiences`
(set to your account ID per Databricks' recommendation).

```bash
ACCOUNT_ID=<your-account-id>

# Policy A — PR validation (read-only, no deploy)
databricks account service-principal-federation-policy create "$SP_NUMERIC_ID" --account-id "$ACCOUNT_ID" --profile <your-account-profile> --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["'"$ACCOUNT_ID"'"],
    "subject": "repo:jdacvaibhav-dot/jdac6thedition-ai-dev-kit:pull_request"
  }
}'

# Policy B — deploy to dev
databricks account service-principal-federation-policy create "$SP_NUMERIC_ID" --account-id "$ACCOUNT_ID" --profile <your-account-profile> --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["'"$ACCOUNT_ID"'"],
    "subject": "repo:jdacvaibhav-dot/jdac6thedition-ai-dev-kit:environment:dev"
  }
}'

# Policy C — deploy to prod
databricks account service-principal-federation-policy create "$SP_NUMERIC_ID" --account-id "$ACCOUNT_ID" --profile <your-account-profile> --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["'"$ACCOUNT_ID"'"],
    "subject": "repo:jdacvaibhav-dot/jdac6thedition-ai-dev-kit:environment:prod"
  }
}'
```

## 3. Create the two GitHub Environments

In the repo (Settings → Environments):

1. Create environment `dev` — no protection rules.
2. Create environment `prod` — under "Deployment protection rules", add a required reviewer
   (at minimum `bjamrozik@origindigital.com`'s GitHub account). This is what makes
   `deploy-prod.yml` (Task 4) pause for approval before it can run.

## 4. Confirm the service principal can actually deploy

The service principal also needs the same Unity Catalog / workspace permissions any deploying
identity needs for this bundle (e.g., `CAN_MANAGE` on the bundle's resources, `USE CATALOG` on
`databricks_user_group_aitoolkit`). It already has `run_as` on `prod` in `databricks.yml`, which
implies these permissions exist for prod; confirm the same identity also has what it needs to
deploy `dev` (dev has no explicit `run_as`, so today it deploys as whichever human/identity is
authenticated — once CI deploys `dev` too, that becomes this service principal for CI-driven
deploys, while Bradley's local `bundle deploy -t dev` continues to work unchanged under his own
user identity).
```

- [ ] **Step 3: Commit**

```bash
git add docs/ci-cd/oidc-setup.md
git commit -m "$(cat <<'EOF'
docs: add Databricks OIDC federation setup runbook for GitHub Actions

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `validate.yml` — PR-triggered bundle validate (both targets) + pytest

**Files:**
- Create: `.github/workflows/validate.yml`

**Interfaces:**
- Consumes: Policy A from Task 1 (`repo:jdacvaibhav-dot/jdac6thedition-ai-dev-kit:pull_request`, must exist in the workspace for this workflow's CLI calls to actually authenticate — the workflow YAML itself doesn't fail to *exist* without it, but every run will fail at the `databricks current-user me` / `bundle validate` step until Task 1 is done).
- Produces: nothing consumed by other tasks — this is the PR gate, independent of the two deploy workflows.

- [ ] **Step 1: Write the workflow**

```yaml
name: Validate bundle

on:
  pull_request:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  bundle-validate:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        target: [dev, prod]
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: https://adb-7405607396630555.15.azuredatabricks.net
      DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_SP_CLIENT_ID }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install Databricks CLI
        uses: databricks/setup-cli@main

      - name: Validate bundle
        run: databricks bundle validate --strict -t ${{ matrix.target }}

  pytest:
    runs-on: ubuntu-latest
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: https://adb-7405607396630555.15.azuredatabricks.net
      DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_SP_CLIENT_ID }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Install dependencies
        run: uv sync

      - name: Run tests
        run: uv run pytest
```

`vars.DATABRICKS_SP_CLIENT_ID` is a repo-level (not environment-level) **Actions variable** (Settings → Secrets and variables → Actions → Variables tab — not Secrets, since an application/client ID is not sensitive; it's already committed in plaintext in `databricks.yml`'s `run_as_service_principal` lookup). Set it once to the application ID recorded in Task 1, Step 1.

- [ ] **Step 2: Validate YAML syntax locally**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`, no exception.

- [ ] **Step 3: Static-lint the workflow if `actionlint` is available**

```bash
if command -v actionlint >/dev/null 2>&1; then actionlint .github/workflows/validate.yml; else echo "actionlint not installed — skipping (install via 'brew install actionlint' for local linting, not required for this task)"; fi
```

Expected: either clean output (no findings) or the "not installed" message — either is an acceptable pass for this task; installing `actionlint` is optional tooling, not a project dependency.

- [ ] **Step 4: Confirm the matrix targets and permissions block match Global Constraints exactly**

Read the file back and confirm: `permissions.id-token: write` is present (required for OIDC — GitHub only issues the token if this is set), no `environment:` key is set on either job (this workflow must NOT require approval — it's read-only validate and test), and `strategy.matrix.target` is exactly `[dev, prod]`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "$(cat <<'EOF'
feat: add PR-triggered bundle validate + pytest GitHub Actions workflow

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `deploy-dev.yml` — auto-deploy to `dev` on merge to `main`

**Files:**
- Create: `.github/workflows/deploy-dev.yml`

**Interfaces:**
- Consumes: Policy B from Task 1 (`...:environment:dev`); the GitHub Environment `dev` (Task 1, Step 3); the same `vars.DATABRICKS_SP_CLIENT_ID` Actions variable Task 2 introduced (reused, not redefined).
- Produces: nothing consumed by other tasks in this plan.

- [ ] **Step 1: Write the workflow**

```yaml
name: Deploy to dev

on:
  push:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  deploy-dev:
    runs-on: ubuntu-latest
    environment: dev
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: https://adb-7405607396630555.15.azuredatabricks.net
      DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_SP_CLIENT_ID }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install Databricks CLI
        uses: databricks/setup-cli@main

      - name: Deploy bundle to dev
        run: databricks bundle deploy -t dev
```

- [ ] **Step 2: Validate YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-dev.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`.

- [ ] **Step 3: Confirm the trigger and environment binding**

Read the file back and confirm: `on.push.branches` is exactly `[main]` (deploy-dev must not fire on every branch push, only merges into `main`), and `jobs.deploy-dev.environment` is exactly `dev` (this is what makes the OIDC subject claim match Policy B — get this wrong and the job will authenticate-fail with a subject-mismatch error, not silently deploy under the wrong policy).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy-dev.yml
git commit -m "$(cat <<'EOF'
feat: add auto-deploy-to-dev GitHub Actions workflow on merge to main

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `deploy-prod.yml` — manual, approval-gated prod deploy

**Files:**
- Create: `.github/workflows/deploy-prod.yml`

**Interfaces:**
- Consumes: Policy C from Task 1 (`...:environment:prod`); the GitHub Environment `prod` with its required reviewer (Task 1, Step 3); `vars.DATABRICKS_SP_CLIENT_ID`; the existing `git: branch: main` guard already in `databricks.yml`'s `prod` target (no new branch check needed here — the CLI itself refuses to deploy `prod` unless `main` is checked out, and `workflow_dispatch` runs check out whatever ref the user picks when triggering, defaulting to the workflow's default branch).
- Produces: nothing consumed by other tasks in this plan — this is the plan's final, most-gated workflow.

- [ ] **Step 1: Write the workflow**

```yaml
name: Deploy to prod

on:
  workflow_dispatch: {}

permissions:
  id-token: write
  contents: read

jobs:
  deploy-prod:
    runs-on: ubuntu-latest
    environment: prod
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: https://adb-7405607396630555.15.azuredatabricks.net
      DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_SP_CLIENT_ID }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install Databricks CLI
        uses: databricks/setup-cli@main

      - name: Deploy bundle to prod
        run: databricks bundle deploy -t prod
```

- [ ] **Step 2: Validate YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-prod.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`.

- [ ] **Step 3: Confirm this workflow is manual-only and environment-gated**

Read the file back and confirm: the only trigger is `workflow_dispatch` (no `push` or `pull_request` trigger — a prod deploy must never fire automatically), and `jobs.deploy-prod.environment` is exactly `prod`. Cross-check against Task 1's runbook that the `prod` GitHub Environment has a required reviewer configured — without that reviewer, `environment: prod` alone does not gate anything.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy-prod.yml
git commit -m "$(cat <<'EOF'
feat: add manual approval-gated prod deploy GitHub Actions workflow

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Auth approach:** OIDC workload identity federation end-to-end — confirmed as Databricks' current recommendation for both AWS/GCP and Azure Databricks (this workspace is Azure) via their respective GitHub Actions integration docs, and confirmed the exact `subject` claim format for both `pull_request`-triggered and `environment`-gated jobs against GitHub's own OIDC reference. No Databricks secret, PAT, or long-lived token is ever stored in GitHub.
- **No new service principal:** reused `databricks_user_group_job_sp` (already wired as `prod`'s `run_as` in `databricks.yml`) for all three workflows, differentiated only by federation-policy `subject` per GitHub Environment/event — one identity to audit, not three.
- **Open gaps (Task 1's "Needs Bradley" section):** account-level CLI access, the account ID, the service principal's numeric ID, and creating the two GitHub Environments with `prod`'s required-reviewer rule. All four require credentials or permissions (account-admin, GitHub repo-admin) this plan's executor does not have — Task 1 produces the exact runbook rather than guessing at values or skipping the requirement.
- **pytest decision:** run it in CI (Task 2), reusing the existing `tests/conftest.py` serverless-compute auto-fallback — no new compute configuration needed, and it exercises the same OIDC-authenticated path as `bundle validate`, so a broken federation policy fails loudly on every PR rather than silently.
- **Deliberately not automated:** prod deploys stay `workflow_dispatch`-only rather than triggered by any push, consistent with the Wanderbricks demo spec's own stance that prod deploy is "not part of the live demo" and should remain a deliberate, approved action.
