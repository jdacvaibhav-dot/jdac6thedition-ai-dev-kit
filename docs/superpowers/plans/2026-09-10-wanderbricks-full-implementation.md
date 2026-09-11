# Wanderbricks Demo — Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full Wanderbricks demo — a Lakeflow Declarative Pipeline that produces an SCD Type 2 `bookings_gold` table via CDC, wired into a multi-target (`dev`/`prod`) Databricks Asset Bundle, with governance grants, an AI/BI dashboard, and a stretch Genie space.

**Architecture:** One Lakeflow pipeline (`wanderbricks_gold_pipeline`) with a Bronze → Enriched (temp view) → Gold (Auto CDC, SCD2) layering, added as new resources inside the *existing* `jdac6thedition_ai_dev_kit` bundle (not a new bundle — see Global Constraints). A job resource triggers the pipeline. A bundle-managed SQL warehouse and a bundle-managed schema grant provide the compute and governance the dashboard, Genie space, and viewer group need — everything is declared in `databricks.yml`/`resources/*.yml`, nothing is applied by hand after deploy.

**Tech Stack:** Databricks Lakeflow Declarative Pipelines (Python, `pyspark.pipelines` / `dp`), Databricks Asset Bundles (DABs), Databricks CLI v1.16.0, AI/BI (Lakeview) dashboards, Genie Agents (Conversation API v2 `serialized_space`).

**Spec:** `docs/presentation/wanderbricks-demo-spec.md` — this plan implements every component in that spec (Components 1–6). Executors should read both documents; where this plan makes an implementation decision not spelled out in the spec, the decision and its rationale are called out explicitly below.

## Global Constraints

- **Workspace/host:** same host for `dev` and `prod` — `https://adb-7405607396630555.15.azuredatabricks.net` (already set in `databricks.yml`, unchanged by this plan).
- **Catalog:** `databricks_user_group_aitoolkit` for both `dev` and `prod` (already wired via `var.catalog`, unchanged).
- **Schema:** `wanderbricks`, shared by both targets — **already exists** as `resources/jdac6thedition_ai_dev_kit.schema.yml` (resource key `wanderbricks`). Reuse it; do not create a second schema resource.
- **Profile:** `DEFAULT` (confirmed). Never auto-select a different profile in commands below — every CLI invocation in this plan passes `--profile DEFAULT` explicitly; swap it out only if the user says so.
- **Viewer group:** `wanderbricks-viewers` (already created in the workspace).
- **Prod `run_as`:** service principal via `${var.run_as_service_principal}` (already wired in `databricks.yml`, unchanged).
- **Bundle identity decision:** the spec's naming table lists a bundle named `wanderbricks-demo`, but this repo already has a working bundle named `jdac6thedition_ai_dev_kit` with the `dev`/`prod` targets, catalog variable, and `wanderbricks` schema resource the spec asks for already in place. Renaming the bundle is a disruptive, unforced move (it changes `root_path` under `/Workspace/.bundle/${bundle.name}/...` and orphans anything already deployed under the old name). **Decision: keep the existing bundle name `jdac6thedition_ai_dev_kit` and add the Wanderbricks resources alongside the existing taxi-sample resources.** Flag this to the user before Task 1 in case they want the rename instead.
- **Everything is bundle-managed — no post-deploy manual steps.** Per explicit direction: the SQL warehouse the dashboard/Genie/verification queries use is declared as a `resources.sql_warehouses` bundle resource (Task 7), and the `SELECT` grant for `wanderbricks-viewers` is declared as a `grants:` block on the existing `resources.schemas.wanderbricks` resource (Task 9) — not a hand-run `GRANT` statement. This is only safe because bronze tables are made pipeline-private (`private=True`, Task 2): a schema-level grant would otherwise also expose the raw bronze copies, which the spec never asked to share. Because tables aren't a DABs resource type, a schema-level grant is the only declarative way to grant `SELECT` on `bookings_gold` — making `bookings_gold` the *only* UC-visible object in the schema makes that schema-level grant equivalent to a table-level one.
- **Naming for new resources** (everything else matches the spec's naming table exactly):

  | Thing | Name |
  |---|---|
  | Pipeline | `wanderbricks_gold_pipeline` |
  | Job | `wanderbricks_gold_job` |
  | SQL warehouse | `wanderbricks_warehouse` |
  | Gold table | `bookings_gold` |
  | Pipeline source dir | `src/wanderbricks_etl/` |

- **Testing approach for this stack:** Lakeflow `@dp.table` / `dp.create_streaming_table` / `dp.create_auto_cdc_flow` code only runs inside the Lakeflow runtime (it depends on an injected `spark` global and pipeline graph resolution) — it cannot be unit-tested with plain `pytest` the way `tests/sample_taxis_test.py` tests `taxis.py`. This repo's own test fixtures (`tests/conftest.py`) already reflect that reality: they run against a **live** Databricks Connect session, not a local mock. Every task below therefore substitutes the "write failing test → make it pass" cycle with the equivalent Lakeflow/DABs cycle: **`bundle validate --strict` → `bundle deploy` → `bundle run` / `pipelines start-update` → poll the update via `databricks pipelines list-pipeline-events` and assert on the specific expected outcome (success, or a specific named failure).** This is not a shortcut — it is the actual feedback loop this stack has, and it still runs before/after each change per task.
- **Do not** write to or modify anything under `samples.*` at any point in this plan.
- **Do not** grant anything beyond `SELECT` on `bookings_gold`, and do not touch grants on `bookings` / `booking_updates` / any other `samples.wanderbricks.*` table.

---

### Task 1: Production git-branch guard

**Files:**
- Modify: `databricks.yml`

**Interfaces:**
- Consumes: nothing new — modifies the existing `prod` target block.
- Produces: `prod` target now refuses to validate/deploy unless the current git branch is `main`. No other task depends on this one; it can run first or last.

- [ ] **Step 1: Confirm current branch is not `main` (so we can observe the guard fail)**

```bash
git branch --show-current
```

Expected: `meetup-prep` (per repo state at plan-writing time). If this now returns `main`, this task's "expect failure" step will instead need to be checked out to a non-`main` branch temporarily (e.g. `git checkout -b tmp-branch-guard-check`) and back afterward — do not leave the repo on a throwaway branch.

- [ ] **Step 2: Validate prod target BEFORE the change — confirm it currently passes despite the branch**

```bash
databricks bundle validate --strict -t prod --profile DEFAULT
```

Expected: exits `0` (no git-branch enforcement configured yet).

- [ ] **Step 3: Add the git branch guard to the `prod` target**

Edit `databricks.yml`, adding a `git:` block to the `prod` target (leave `dev` untouched — only prod enforces a branch):

```yaml
  prod:
    mode: production
    git:
      branch: main
    workspace:
      host: https://adb-7405607396630555.15.azuredatabricks.net
      root_path: /Workspace/.bundle/${bundle.name}/${bundle.target}
    run_as:
      service_principal_name: ${var.run_as_service_principal}
    variables:
      catalog: databricks_user_group_aitoolkit
    permissions:
      - user_name: bjamrozik@origindigital.com
        level: CAN_MANAGE
```

- [ ] **Step 4: Re-run validation — expect it to now fail on the branch check**

```bash
databricks bundle validate --strict -t prod --profile DEFAULT
```

Expected: non-zero exit code, with an error/warning referencing the git branch mismatch (current branch `meetup-prep` vs. required `main`). Exact wording varies by CLI version — assert on the non-zero exit code and the presence of the word `branch` (or `git`) in the output, not an exact string match.

```bash
databricks bundle validate --strict -t prod --profile DEFAULT 2>&1 | grep -qi branch && echo "PASS: branch guard triggered"
```

- [ ] **Step 5: Confirm `dev` is unaffected**

```bash
databricks bundle validate --strict -t dev --profile DEFAULT
```

Expected: exits `0` — `dev` has no git guard and is unaffected by this change.

- [ ] **Step 6: Commit**

```bash
git add databricks.yml
git commit -m "$(cat <<'EOF'
feat: enforce main-branch requirement for prod bundle target

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Bronze layer — pipeline-private streaming reads of raw booking tables

**Files:**
- Create: `src/wanderbricks_etl/README.md`
- Create: `src/wanderbricks_etl/transformations/bookings_bronze.py`
- Create: `src/wanderbricks_etl/transformations/booking_updates_bronze.py`

**Interfaces:**
- Consumes: `samples.wanderbricks.bookings`, `samples.wanderbricks.booking_updates` (external, read-only, pre-existing — nothing to build).
- Produces: **pipeline-private** (`private=True`) streaming tables `bookings_bronze` and `booking_updates_bronze`, each with the same columns as their source table. Private means not published to Unity Catalog — only visible inside the pipeline. Consumed by Task 3's enrichment views. This is what makes the schema-level grant in Task 9 safe: `bookings_gold` (Task 4) is the only object this pipeline publishes into the `wanderbricks` schema, so a schema-level `SELECT` grant is scoped exactly to it.

- [ ] **Step 1: Add the pipeline README (mirrors the existing `jdac6thedition_ai_dev_kit_etl/README.md` convention)**

```markdown
# wanderbricks_etl

Lakeflow Declarative Pipeline producing `bookings_gold`: a CDC/SCD Type 2 booking
history table built from `samples.wanderbricks.bookings` and
`samples.wanderbricks.booking_updates`.

- `transformations/`: dataset definitions — one file per dataset.
  - `bookings_bronze.py` / `booking_updates_bronze.py`: raw streaming reads (Bronze),
    marked `private=True` — not published to Unity Catalog. `bookings_gold` is the
    only table this pipeline publishes.
  - `bookings_enriched.py` / `booking_updates_enriched.py`: stream-static joins adding
    `destination` (temporary views feeding Auto CDC).
  - `bookings_gold.py`: empty streaming table populated by two Auto CDC flows
    (SCD Type 2), one per source.

Run a single transformation from the CLI:
`databricks bundle run wanderbricks_gold_pipeline --refresh bookings_bronze -t dev`
```

- [ ] **Step 2: Write `bookings_bronze.py`**

```python
from pyspark import pipelines as dp


@dp.table(name="bookings_bronze", private=True)
def bookings_bronze():
    return spark.readStream.table("samples.wanderbricks.bookings")
```

- [ ] **Step 3: Write `booking_updates_bronze.py`**

```python
from pyspark import pipelines as dp


@dp.table(name="booking_updates_bronze", private=True)
def booking_updates_bronze():
    return spark.readStream.table("samples.wanderbricks.booking_updates")
```

- [ ] **Step 4: Confirm the files parse as valid Python (no pipeline runtime needed for this check)**

```bash
uv run python -m py_compile src/wanderbricks_etl/transformations/bookings_bronze.py src/wanderbricks_etl/transformations/booking_updates_bronze.py
```

Expected: no output, exit code `0`. (`spark` and `dp` are unresolved names at this stage — that's expected; `py_compile` only checks syntax, and the pipeline resource in Task 5 is what actually exercises these against the Lakeflow runtime.)

- [ ] **Step 5: Commit**

```bash
git add src/wanderbricks_etl/README.md src/wanderbricks_etl/transformations/bookings_bronze.py src/wanderbricks_etl/transformations/booking_updates_bronze.py
git commit -m "$(cat <<'EOF'
feat: add wanderbricks bronze layer (streaming reads of bookings/booking_updates)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Enrichment layer — temporary views joining in `destination`

**Files:**
- Create: `src/wanderbricks_etl/transformations/bookings_enriched.py`
- Create: `src/wanderbricks_etl/transformations/booking_updates_enriched.py`

**Interfaces:**
- Consumes: `bookings_bronze`, `booking_updates_bronze` (Task 2, pipeline-scoped names); `samples.wanderbricks.properties` (columns used: `property_id`, `destination_id`); `samples.wanderbricks.destinations` (columns used: `destination_id`, `destination`).
- Produces: pipeline-scoped temporary views `bookings_enriched` and `booking_updates_enriched` — each is the full source row (all bronze columns) plus one added `destination` column, with the transient `destination_id` join key dropped. Temporary views are never published to UC regardless of `private`, so no change needed here for the Task 9 grant scoping. Consumed by Task 4's Auto CDC flows.

- [ ] **Step 1: Write `bookings_enriched.py`**

```python
from pyspark import pipelines as dp


@dp.temporary_view(name="bookings_enriched")
def bookings_enriched():
    bookings = spark.readStream.table("bookings_bronze")
    properties = spark.read.table("samples.wanderbricks.properties").select(
        "property_id", "destination_id"
    )
    destinations = spark.read.table("samples.wanderbricks.destinations").select(
        "destination_id", "destination"
    )

    return (
        bookings.join(properties, on="property_id", how="left")
        .join(destinations, on="destination_id", how="left")
        .drop("destination_id")
    )
```

- [ ] **Step 2: Write `booking_updates_enriched.py` (identical join pattern, different source)**

```python
from pyspark import pipelines as dp


@dp.temporary_view(name="booking_updates_enriched")
def booking_updates_enriched():
    booking_updates = spark.readStream.table("booking_updates_bronze")
    properties = spark.read.table("samples.wanderbricks.properties").select(
        "property_id", "destination_id"
    )
    destinations = spark.read.table("samples.wanderbricks.destinations").select(
        "destination_id", "destination"
    )

    return (
        booking_updates.join(properties, on="property_id", how="left")
        .join(destinations, on="destination_id", how="left")
        .drop("destination_id")
    )
```

- [ ] **Step 3: Confirm syntax**

```bash
uv run python -m py_compile src/wanderbricks_etl/transformations/bookings_enriched.py src/wanderbricks_etl/transformations/booking_updates_enriched.py
```

Expected: exit code `0`.

- [ ] **Step 4: Commit**

```bash
git add src/wanderbricks_etl/transformations/bookings_enriched.py src/wanderbricks_etl/transformations/booking_updates_enriched.py
git commit -m "$(cat <<'EOF'
feat: add wanderbricks enrichment views (join in destination for CDC input)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Gold layer — `bookings_gold` via two Auto CDC (SCD2) flows

**Files:**
- Create: `src/wanderbricks_etl/transformations/bookings_gold.py`

**Interfaces:**
- Consumes: `bookings_enriched`, `booking_updates_enriched` (Task 3, pipeline-scoped names).
- Produces: streaming table `bookings_gold` — **published to UC** (no `private=True`; this is the one object this pipeline is meant to expose) — with columns inferred from the CDC sources plus Lakeflow-managed `__START_AT` / `__END_AT`. This is the table every remaining task (5–6 to run it, 8 to run/verify it, 9 to grant on it, 10 to dashboard it, 11 to Genie it) is built around. Current-row filter convention for all downstream consumers: `WHERE __END_AT IS NULL`.

- [ ] **Step 1: Write `bookings_gold.py`**

Schema is intentionally left unspecified (`dp.create_streaming_table(name=...)` with no `schema=`) so Lakeflow infers types from the CDC flows rather than us guessing exact column types (`total_amount` precision, `guests_count` width, etc.) that aren't documented in the spec.

```python
from pyspark import pipelines as dp

dp.create_streaming_table(name="bookings_gold")

dp.create_auto_cdc_flow(
    target="bookings_gold",
    source="bookings_enriched",
    keys=["booking_id"],
    sequence_by="updated_at",
    stored_as_scd_type=2,
    name="bookings_initial_cdc",
)

dp.create_auto_cdc_flow(
    target="bookings_gold",
    source="booking_updates_enriched",
    keys=["booking_id"],
    sequence_by="updated_at",
    stored_as_scd_type=2,
    name="booking_updates_cdc",
)
```

- [ ] **Step 2: Confirm syntax**

```bash
uv run python -m py_compile src/wanderbricks_etl/transformations/bookings_gold.py
```

Expected: exit code `0`.

- [ ] **Step 3: Commit**

```bash
git add src/wanderbricks_etl/transformations/bookings_gold.py
git commit -m "$(cat <<'EOF'
feat: add wanderbricks_gold SCD2 table via two Auto CDC flows

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Pipeline resource

**Files:**
- Create: `resources/wanderbricks_gold_pipeline.pipeline.yml`

**Interfaces:**
- Consumes: `src/wanderbricks_etl/transformations/**` (Tasks 2–4); `${var.catalog}`; `${resources.schemas.wanderbricks.name}` (existing resource key `wanderbricks` in `resources/jdac6thedition_ai_dev_kit.schema.yml`).
- Produces: bundle resource `resources.pipelines.wanderbricks_gold_pipeline`, whose `.id` substitution is consumed by Task 6's job resource.

- [ ] **Step 1: Write the pipeline resource, mirroring the existing `jdac6thedition_ai_dev_kit_etl.pipeline.yml` shape**

```yaml
resources:
  pipelines:
    wanderbricks_gold_pipeline:
      name: wanderbricks_gold_pipeline
      catalog: ${var.catalog}
      schema: ${resources.schemas.wanderbricks.name}
      serverless: true
      root_path: "../src/wanderbricks_etl"

      libraries:
        - glob:
            include: ../src/wanderbricks_etl/transformations/**

      environment:
        dependencies:
          - --editable ${workspace.file_path}
```

- [ ] **Step 2: Validate the bundle picks up the new resource**

```bash
databricks bundle validate --strict -t dev --profile DEFAULT
```

Expected: exits `0`. If it fails, read the error — it will point at a YAML/path issue in this file (most likely `root_path` or the glob) or a missing catalog/schema variable resolution.

- [ ] **Step 3: Confirm the resource shows up in the plan**

```bash
databricks bundle validate -t dev --profile DEFAULT -o json | jq '.resources.pipelines.wanderbricks_gold_pipeline.name'
```

Expected: `"wanderbricks_gold_pipeline"`.

- [ ] **Step 4: Commit**

```bash
git add resources/wanderbricks_gold_pipeline.pipeline.yml
git commit -m "$(cat <<'EOF'
feat: add wanderbricks_gold_pipeline bundle resource

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Job resource that triggers the pipeline

**Files:**
- Create: `resources/wanderbricks_gold_job.job.yml`

**Interfaces:**
- Consumes: `${resources.pipelines.wanderbricks_gold_pipeline.id}` (Task 5); `${var.catalog}`; `${resources.schemas.wanderbricks.name}`.
- Produces: bundle resource `resources.jobs.wanderbricks_gold_job`, named `wanderbricks_gold_job` — this is the name Task 8 passes to `databricks bundle run`.

- [ ] **Step 1: Write the job resource**

```yaml
resources:
  jobs:
    wanderbricks_gold_job:
      name: wanderbricks_gold_job

      parameters:
        - name: catalog
          default: ${var.catalog}
        - name: schema
          default: ${resources.schemas.wanderbricks.name}

      tasks:
        - task_key: refresh_wanderbricks_gold_pipeline
          pipeline_task:
            pipeline_id: ${resources.pipelines.wanderbricks_gold_pipeline.id}
```

- [ ] **Step 2: Validate**

```bash
databricks bundle validate --strict -t dev --profile DEFAULT
```

Expected: exits `0`.

- [ ] **Step 3: Confirm the job resolves the pipeline dependency**

```bash
databricks bundle validate -t dev --profile DEFAULT -o json | jq '.resources.jobs.wanderbricks_gold_job.tasks[0].pipeline_task.pipeline_id'
```

Expected: a non-empty string that is NOT the literal text `${resources.pipelines.wanderbricks_gold_pipeline.id}` (i.e., the substitution resolved — DABs resolves this to a placeholder ID pre-deploy, or the real ID post-deploy depending on CLI version; either way it must not be the raw unresolved token).

- [ ] **Step 4: Commit**

```bash
git add resources/wanderbricks_gold_job.job.yml
git commit -m "$(cat <<'EOF'
feat: add wanderbricks_gold_job to trigger the gold pipeline

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: SQL warehouse resource (bundle-managed)

Per explicit direction, the SQL warehouse used by verification queries (Task 8), the dashboard (Task 10), and the Genie space (Task 11) is declared in the bundle rather than assumed to already exist in the workspace.

**Files:**
- Create: `resources/wanderbricks_warehouse.warehouse.yml`

**Interfaces:**
- Consumes: nothing.
- Produces: bundle resource `resources.sql_warehouses.wanderbricks_warehouse`, whose `.id` substitution is consumed by Task 8 (verification queries), Task 9 (grant verification queries), Task 10 (dashboard `warehouse_id`), and Task 11 (Genie space `warehouse_id`).

- [ ] **Step 1: Write the warehouse resource — small, serverless, auto-stopping (this is a demo warehouse, not a production one)**

```yaml
resources:
  sql_warehouses:
    wanderbricks_warehouse:
      name: wanderbricks_warehouse
      cluster_size: "2X-Small"
      warehouse_type: PRO
      enable_serverless_compute: true
      auto_stop_mins: 10
```

- [ ] **Step 2: Validate**

```bash
databricks bundle validate --strict -t dev --profile DEFAULT
```

Expected: exits `0`.

- [ ] **Step 3: Confirm the resource is present and correctly typed in the plan**

```bash
databricks bundle validate -t dev --profile DEFAULT -o json | jq '.resources.sql_warehouses.wanderbricks_warehouse | {name, warehouse_type, enable_serverless_compute}'
```

Expected: `{"name": "wanderbricks_warehouse", "warehouse_type": "PRO", "enable_serverless_compute": true}`.

- [ ] **Step 4: Commit**

```bash
git add resources/wanderbricks_warehouse.warehouse.yml
git commit -m "$(cat <<'EOF'
feat: add bundle-managed SQL warehouse for wanderbricks demo

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Deploy and run in `dev`

**Files:**
- None (operational task — no new files; this is Component 3 of the spec).

**Interfaces:**
- Consumes: `resources.pipelines.wanderbricks_gold_pipeline`, `resources.jobs.wanderbricks_gold_job` (Tasks 5–6); `resources.sql_warehouses.wanderbricks_warehouse` (Task 7).
- Produces: a live, running `wanderbricks_gold_pipeline`, a live `wanderbricks_warehouse`, and a populated `bookings_gold` table under `databricks_user_group_aitoolkit.wanderbricks` in the dev catalog. Consumed by Task 9 (grants), Task 10 (dashboard), Task 11 (Genie).

- [ ] **Step 1: Deploy to dev**

```bash
databricks bundle deploy -t dev --profile DEFAULT
```

Expected: exits `0`, output confirms resources uploaded and deployed.

- [ ] **Step 2: Confirm the dev-prefixed resources exist**

```bash
databricks bundle summary -t dev --profile DEFAULT
```

Expected: output lists `wanderbricks_gold_pipeline`, `wanderbricks_gold_job`, and `wanderbricks_warehouse`, prefixed `[dev <user>]` per `mode: development`.

- [ ] **Step 3: Resolve the bundle-managed warehouse ID for use in this task's verification queries**

```bash
WH=$(databricks bundle validate -t dev --profile DEFAULT -o json | jq -r '.resources.sql_warehouses.wanderbricks_warehouse.id')
echo "$WH"
```

Expected: a non-empty warehouse ID (not the literal `${resources.sql_warehouses.wanderbricks_warehouse.id}` token).

- [ ] **Step 4: Run the job**

```bash
databricks bundle run wanderbricks_gold_job -t dev --profile DEFAULT
```

Expected: command blocks until the run completes, exits `0` on success. If it fails, do not immediately retry — inspect the failure per Step 5 before deciding whether to fix code or full-refresh.

- [ ] **Step 5: If the run failed, pull the pipeline update's actual error (not just top-level state)**

```bash
PIPELINE_ID=$(databricks bundle validate -t dev --profile DEFAULT -o json | jq -r '.resources.pipelines.wanderbricks_gold_pipeline.id')
databricks pipelines list-pipeline-events "$PIPELINE_ID" --profile DEFAULT -o json | jq -r '.[] | select(.error != null) | .error.exceptions[0].message'
```

Fix the root cause in the relevant `src/wanderbricks_etl/transformations/*.py` file, redeploy (Step 1), and rerun (Step 4) before continuing.

- [ ] **Step 6: Confirm `bookings_gold` exists and is populated, and that the bronze tables did NOT publish to UC**

```bash
databricks experimental aitools tools query --warehouse "$WH" \
  "SELECT COUNT(*) AS row_count, COUNT(*) FILTER (WHERE __END_AT IS NULL) AS current_row_count FROM databricks_user_group_aitoolkit.wanderbricks.bookings_gold" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "SHOW TABLES IN databricks_user_group_aitoolkit.wanderbricks" \
  --profile DEFAULT
```

Expected: `row_count` > 0, and `current_row_count` > 0 and ≤ `row_count` (SCD2 history rows exist, and the "current" filter returns a strict subset or all of them when no booking has ever changed status). `SHOW TABLES` lists only `bookings_gold` — `bookings_bronze` / `booking_updates_bronze` must NOT appear (they're `private=True`), which is what makes Task 9's schema-level grant scoped correctly.

- [ ] **Step 7: Confirm `prod` deploy is structurally valid without actually deploying it (per spec — prod deploy is not part of the live demo)**

```bash
git checkout main
databricks bundle validate --strict -t prod --profile DEFAULT
git checkout meetup-prep
```

Expected: exits `0` while on `main` (the Task 1 git guard passes here). Do not run `databricks bundle deploy -t prod` — out of scope for this task per the spec.

- [ ] **Step 8: No commit for this task** — it produced no file changes, only deployed/ran remote resources.

---

### Task 9: Governance — bundle-managed `SELECT` grant on the `wanderbricks` schema

Per explicit direction, this grant is declared on the existing schema resource in the bundle, not applied by hand after deploy. It is safe to scope at the schema level because Task 2 made `bookings_gold` the only table this pipeline publishes into that schema (Task 8, Step 6 already confirmed this).

**Files:**
- Modify: `resources/jdac6thedition_ai_dev_kit.schema.yml`

**Interfaces:**
- Consumes: the existing `resources.schemas.wanderbricks` resource; group `wanderbricks-viewers` (pre-existing); `resources.sql_warehouses.wanderbricks_warehouse` (Task 7, for this task's own verification queries).
- Produces: a bundle-declared `SELECT` grant on the `wanderbricks` schema for `wanderbricks-viewers`. Consumed by nothing else in this plan (terminal governance step) but is the fact Task 10's dashboard / Task 11's Genie space rely on being safe to share with that group.

- [ ] **Step 1: Confirm no grant exists yet (expected pre-state)**

```bash
databricks experimental aitools tools query --warehouse "$WH" \
  "SHOW GRANTS ON SCHEMA databricks_user_group_aitoolkit.wanderbricks" \
  --profile DEFAULT
```

Expected: no row for principal `wanderbricks-viewers`.

- [ ] **Step 2: Add the `grants:` block to the schema resource**

Read the current file first — it already has `catalog_name`, `name`, and `comment` fields (do not remove them):

```yaml
resources:
  schemas:
    wanderbricks:
      catalog_name: ${var.catalog}
      name: wanderbricks
      comment: Schema for the jdac6thedition_ai_dev_kit bundle.
      grants:
        - principal: wanderbricks-viewers
          privileges:
            - SELECT
```

- [ ] **Step 3: Validate and deploy**

```bash
databricks bundle validate --strict -t dev --profile DEFAULT
databricks bundle deploy -t dev --profile DEFAULT
```

Expected: both exit `0`.

- [ ] **Step 4: Confirm the grant now exists**

```bash
databricks experimental aitools tools query --warehouse "$WH" \
  "SHOW GRANTS ON SCHEMA databricks_user_group_aitoolkit.wanderbricks" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "SHOW GRANTS ON TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold" \
  --profile DEFAULT
```

Expected: the schema-level query shows a row with `principal = wanderbricks-viewers`, `action_type = SELECT`; the table-level query shows the same grant with `inherited_from` pointing at the schema (since `bookings_gold` is the only table there, this is functionally a table-scoped grant).

- [ ] **Step 5: Confirm nothing was granted on the raw source tables**

```bash
databricks experimental aitools tools query --warehouse "$WH" \
  "SHOW GRANTS ON TABLE samples.wanderbricks.payments" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "SHOW GRANTS ON TABLE samples.wanderbricks.bookings" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "SHOW GRANTS ON TABLE samples.wanderbricks.booking_updates" \
  --profile DEFAULT
```

Expected: no row for `wanderbricks-viewers` in any of these three — only whatever the workspace already granted by default (untouched by this task, since `samples.*` sits in a different catalog entirely and is unreachable by this schema-level grant).

- [ ] **Step 6: Commit**

```bash
git add resources/jdac6thedition_ai_dev_kit.schema.yml
git commit -m "$(cat <<'EOF'
feat: grant wanderbricks-viewers SELECT on the wanderbricks schema

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: AI/BI dashboard on `bookings_gold`

**Files:**
- Create: `src/dashboards/wanderbricks_gold.lvdash.json`
- Create: `resources/wanderbricks_dashboard.dashboard.yml`

**Interfaces:**
- Consumes: `databricks_user_group_aitoolkit.wanderbricks.bookings_gold` (Task 8); `resources.sql_warehouses.wanderbricks_warehouse.id` (Task 7).
- Produces: a deployed AI/BI dashboard resource `resources.dashboards.wanderbricks_gold`. Nothing downstream depends on it.

- [ ] **Step 1: Validate the SQL against `bookings_gold` directly before building the dashboard JSON**

```bash
DATABRICKS_WAREHOUSE_ID="$WH" databricks experimental aitools tools query --output json \
  "SELECT destination, SUM(total_amount) AS revenue FROM databricks_user_group_aitoolkit.wanderbricks.bookings_gold WHERE __END_AT IS NULL GROUP BY destination ORDER BY 2 DESC" \
  "SELECT DATE_TRUNC('MONTH', __START_AT) AS month, status, COUNT(*) AS bookings FROM databricks_user_group_aitoolkit.wanderbricks.bookings_gold GROUP BY 1, 2 ORDER BY 1" \
  --profile DEFAULT
```

(`$WH` here is `resources.sql_warehouses.wanderbricks_warehouse`'s id, already resolved in Task 8, Step 3.)

Expected: both statements return `state: "SUCCEEDED"` with non-empty, non-flat result sets. If the status-breakdown query returns only one distinct status total, the SCD2 history isn't showing status changes yet — re-check Task 8's run picked up `booking_updates_bronze` rows, not just the baseline `bookings` snapshot.

- [ ] **Step 2: Write the dashboard JSON**

Two widgets per the spec's minimum: revenue by destination (bar), and booking status breakdown over time (stacked bar using SCD2 history — the payoff for doing CDC/SCD2 instead of "latest status only"). Queries use bare table names (catalog/schema come from the bundle resource's `dataset_catalog`/`dataset_schema`, set in Step 3).

```json
{
  "datasets": [
    {
      "name": "revenue_by_destination",
      "displayName": "Revenue by destination",
      "query": "SELECT destination, SUM(total_amount) AS revenue FROM bookings_gold WHERE __END_AT IS NULL GROUP BY destination ORDER BY 2 DESC"
    },
    {
      "name": "status_by_month",
      "displayName": "Booking status by month",
      "query": "SELECT DATE_TRUNC('MONTH', __START_AT) AS month, status, COUNT(*) AS bookings FROM bookings_gold GROUP BY 1, 2 ORDER BY 1"
    }
  ],
  "pages": [
    {
      "name": "main",
      "displayName": "Wanderbricks Bookings",
      "layout": [
        {
          "widget": {
            "name": "header",
            "multilineTextboxSpec": {
              "lines": ["## Wanderbricks Bookings\n", "\n", "Revenue and booking-status history from the CDC/SCD2 gold table."]
            }
          },
          "position": {"x": 0, "y": 0, "width": 12, "height": 2}
        },
        {
          "widget": {
            "name": "revenue-by-destination",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "revenue_by_destination",
                  "fields": [
                    {"name": "destination", "expression": "`destination`"},
                    {"name": "revenue", "expression": "`revenue`"}
                  ],
                  "disaggregated": true
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {"fieldName": "destination", "displayName": "Destination", "scale": {"type": "categorical"}},
                "y": {"fieldName": "revenue", "displayName": "Revenue ($)", "scale": {"type": "quantitative"}, "format": {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 2}}}
              },
              "frame": {"showTitle": true, "title": "Revenue by Destination"}
            }
          },
          "position": {"x": 0, "y": 2, "width": 6, "height": 6}
        },
        {
          "widget": {
            "name": "status-by-month",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "status_by_month",
                  "fields": [
                    {"name": "month", "expression": "`month`"},
                    {"name": "status", "expression": "`status`"},
                    {"name": "bookings", "expression": "`bookings`"}
                  ],
                  "disaggregated": true
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {"fieldName": "month", "displayName": "Month", "scale": {"type": "temporal"}},
                "y": {"fieldName": "bookings", "displayName": "Bookings", "scale": {"type": "quantitative"}},
                "color": {"fieldName": "status", "displayName": "Status", "scale": {"type": "categorical"}}
              },
              "frame": {"showTitle": true, "title": "Booking Status Breakdown Over Time"}
            }
          },
          "position": {"x": 6, "y": 2, "width": 6, "height": 6}
        }
      ]
    }
  ]
}
```

- [ ] **Step 3: Add the dashboard bundle resource — `warehouse_id` points directly at the bundle-managed warehouse from Task 7**

```yaml
resources:
  dashboards:
    wanderbricks_gold:
      display_name: "Wanderbricks Bookings"
      file_path: ../src/dashboards/wanderbricks_gold.lvdash.json
      warehouse_id: ${resources.sql_warehouses.wanderbricks_warehouse.id}
      dataset_catalog: ${var.catalog}
      dataset_schema: ${resources.schemas.wanderbricks.name}
```

- [ ] **Step 4: Validate and deploy**

```bash
databricks bundle validate --strict -t dev --profile DEFAULT
databricks bundle deploy -t dev --profile DEFAULT
```

Expected: both exit `0`.

- [ ] **Step 5: Confirm the dashboard renders with real data**

```bash
databricks bundle run wanderbricks_gold --profile DEFAULT -t dev 2>&1 || true
databricks bundle summary -t dev --profile DEFAULT | grep -i dashboard
```

Then open the dashboard URL from `bundle summary` and visually confirm: the "Revenue by Destination" bar chart has more than one bar, and "Booking Status Breakdown Over Time" shows more than one status color across more than one month bucket (proof the SCD2 history, not just the latest snapshot, is driving the chart).

- [ ] **Step 6: Commit**

```bash
git add src/dashboards/wanderbricks_gold.lvdash.json resources/wanderbricks_dashboard.dashboard.yml
git commit -m "$(cat <<'EOF'
feat: add wanderbricks AI/BI dashboard (revenue by destination, status history)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11 (Stretch — cut first if the demo runs long): Genie space over `bookings_gold`

**Correction from the original draft:** `resources.genie_spaces` IS a real DABs bundle resource type (confirmed via `databricks bundle schema` — it takes `title`, `description`, `parent_path`, `warehouse_id`, and either an inline `serialized_space` or a `file_path` to a `.geniespace.json` file). The Genie space is therefore bundle-managed like everything else in this plan, not created via a separate `databricks genie create-space` CLI call.

**Files:**
- Create: `src/genie/wanderbricks_gold.geniespace.json`
- Create: `resources/wanderbricks_genie_space.genie_space.yml`

**Interfaces:**
- Consumes: `databricks_user_group_aitoolkit.wanderbricks.bookings_gold` (Task 8, referenced inside the serialized space JSON); `resources.sql_warehouses.wanderbricks_warehouse.id` (Task 7, referenced as the resource's `warehouse_id`).
- Produces: bundle resource `resources.genie_spaces.wanderbricks_genie_space`, deployed alongside everything else in Task 8's `bundle deploy`. Terminal — nothing else in this plan depends on it. Per spec: build it regardless of whether it's shown live in the demo.

- [ ] **Step 1: Write the `serialized_space` JSON with the three sample questions from the spec**

```json
{
  "version": 2,
  "config": {
    "sample_questions": [
      {"id": "a1000000000000000000000000000001", "question": ["What's our total revenue by destination?"]},
      {"id": "a1000000000000000000000000000002", "question": ["How many bookings are confirmed vs. cancelled this month?"]},
      {"id": "a1000000000000000000000000000003", "question": ["Which properties have the most bookings?"]}
    ]
  },
  "data_sources": {
    "tables": [
      {
        "identifier": "databricks_user_group_aitoolkit.wanderbricks.bookings_gold",
        "column_configs": [
          {"column_name": "status", "enable_format_assistance": true, "enable_entity_matching": true, "description": ["Current or historical booking status (e.g. confirmed, cancelled)."]},
          {"column_name": "destination", "enable_format_assistance": true, "enable_entity_matching": true, "description": ["Travel destination for the booked property."]},
          {"column_name": "__START_AT", "description": ["SCD Type 2: timestamp this row's status became effective."]},
          {"column_name": "__END_AT", "description": ["SCD Type 2: timestamp this row's status stopped being current. NULL means this is the current row for the booking."]}
        ]
      }
    ]
  },
  "instructions": {
    "example_question_sqls": [
      {
        "id": "a2000000000000000000000000000001",
        "question": ["What's our total revenue by destination?"],
        "sql": ["SELECT destination, SUM(total_amount) AS revenue FROM databricks_user_group_aitoolkit.wanderbricks.bookings_gold WHERE __END_AT IS NULL GROUP BY destination ORDER BY revenue DESC"]
      },
      {
        "id": "a2000000000000000000000000000002",
        "question": ["How many bookings are confirmed vs. cancelled this month?"],
        "sql": ["SELECT status, COUNT(*) AS bookings FROM databricks_user_group_aitoolkit.wanderbricks.bookings_gold WHERE __END_AT IS NULL AND DATE_TRUNC('MONTH', __START_AT) = DATE_TRUNC('MONTH', CURRENT_DATE()) GROUP BY status"]
      },
      {
        "id": "a2000000000000000000000000000003",
        "question": ["Which properties have the most bookings?"],
        "sql": ["SELECT property_id, COUNT(*) AS bookings FROM databricks_user_group_aitoolkit.wanderbricks.bookings_gold WHERE __END_AT IS NULL GROUP BY property_id ORDER BY bookings DESC LIMIT 20"]
      }
    ],
    "text_instructions": [
      {
        "id": "a3000000000000000000000000000001",
        "content": [
          "bookings_gold is a Type 2 slowly-changing-dimension table: each row is a status period for a booking. Always filter WHERE __END_AT IS NULL for 'current' or 'right now' questions. Only omit that filter when the question explicitly asks about history or status changes over time."
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Add the Genie space bundle resource**

```yaml
resources:
  genie_spaces:
    wanderbricks_genie_space:
      title: "Wanderbricks Bookings"
      description: "Ask questions about Wanderbricks booking revenue, status, and property demand using the bookings_gold CDC/SCD2 table."
      parent_path: /Workspace/Users/bjamrozik@origindigital.com/genie_spaces
      warehouse_id: ${resources.sql_warehouses.wanderbricks_warehouse.id}
      file_path: ../src/genie/wanderbricks_gold.geniespace.json
```

- [ ] **Step 3: Validate and deploy**

```bash
databricks bundle validate --strict -t dev --profile DEFAULT
databricks bundle deploy -t dev --profile DEFAULT
```

Expected: both exit `0`.

- [ ] **Step 4: Validate all three sample questions against the live space**

```bash
SPACE_ID=$(databricks bundle validate -t dev --profile DEFAULT -o json | jq -r '.resources.genie_spaces.wanderbricks_genie_space.id')
databricks genie get-space "$SPACE_ID" --include-serialized-space --profile DEFAULT
```

Then, for each of the three sample questions, start a conversation via the Conversation API (or the workspace UI) and confirm each returns a non-empty, correct-shaped answer — not an error or an empty result set. If a question fails, fix `text_instructions` / `column_configs` in `src/genie/wanderbricks_gold.geniespace.json` and redeploy (Step 3) — do not hand-edit the space via `genie update-space`, since the bundle owns it now and a future deploy would overwrite an out-of-band change.

- [ ] **Step 5: Commit**

```bash
git add src/genie/wanderbricks_gold.geniespace.json resources/wanderbricks_genie_space.genie_space.yml
git commit -m "$(cat <<'EOF'
feat: add wanderbricks Genie space bundle resource (stretch)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12 (added mid-execution, user-directed; SUPERSEDED — see note below): Table and column comments on `bookings_gold` for Genie quality

**Status: superseded by commit `d5e9d96` during Task 8's live-integration pass, via a better mechanism than this task originally specified.** Task 8's implementer, while debugging the Genie space live, independently added table/column comments to `bookings_gold` — but instead of the post-deploy `ALTER TABLE`/`COMMENT ON` SQL this task originally called for, it declared an explicit typed `schema=` string (with inline `COMMENT` clauses) directly in `src/wanderbricks_etl/transformations/bookings_gold.py`, using the EXACT column types Spark had already inferred for the live table (confirmed against the schema-mismatch error's own reported inferred types — not guessed). This is a cleaner, fully declarative, version-controlled approach that Task 4 originally avoided only because the exact inferred types weren't known yet; once the table existed and its real types were observable, specifying them explicitly became safe and is strictly better than a bolt-on SQL step. The steps below are left in place as a record of the original plan, but are NOT executed as written — see the Self-Review Notes for the full reconciliation.

<details>
<summary>Original Task 12 steps (superseded, kept for record)</summary>

Per explicit direction: Genie relies on Unity Catalog table/column comments (in addition to the `column_configs` descriptions already set in Task 11's `serialized_space` JSON) to understand table semantics. `bookings_gold` currently has no UC comment on the table or any column — this task adds them.

**Why this can't be done inside the pipeline definition:** Task 4 deliberately left `dp.create_streaming_table(name="bookings_gold")` with no explicit `schema=`, specifically so Lakeflow could infer column types rather than guessing undocumented ones (`total_amount` precision, etc.). Adding inline `COMMENT` clauses to columns requires specifying the full typed schema DDL, which would reintroduce that problem. Since tables aren't a DABs bundle resource type at all (confirmed in Task 9's research), there is no declarative bundle-native way to attach table/column comments either. The only mechanism is SQL (`COMMENT ON TABLE`, `ALTER TABLE ... ALTER COLUMN ... COMMENT`) run once against the live table — the same category of "no bundle-native equivalent exists" as the pre-Task-9 grant situation, except here no bundle-native alternative was ever discovered because none exists for tables.

**Files:**
- None (operational task — SQL run directly against the live `bookings_gold` table via the bundle-managed warehouse from Task 7).

**Interfaces:**
- Consumes: `databricks_user_group_aitoolkit.wanderbricks.bookings_gold` (Task 8, must already be deployed and populated); `resources.sql_warehouses.wanderbricks_warehouse.id` (Task 7).
- Produces: UC table comment + column comments on `bookings_gold`. Improves Task 11's Genie space answer quality (Genie reads UC comments as an additional semantic signal alongside `column_configs`) and Task 10's dashboard usability (comments show in the Catalog Explorer UI for anyone inspecting the table). Terminal — nothing else in this plan depends on it.

- [ ] **Step 1: Confirm current state (no comments yet)**

```bash
databricks experimental aitools tools query --warehouse "$WH" \
  "DESCRIBE TABLE EXTENDED databricks_user_group_aitoolkit.wanderbricks.bookings_gold" \
  --profile DEFAULT
```

Expected: no `Comment` value for the table, and column rows show no comment text.

- [ ] **Step 2: Set the table comment**

```bash
databricks experimental aitools tools query --warehouse "$WH" \
  "COMMENT ON TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold IS 'CDC/SCD Type 2 booking history for Wanderbricks. Each row is a status period for one booking; __END_AT IS NULL identifies the current row. Built from samples.wanderbricks.bookings and booking_updates via two Auto CDC flows.'" \
  --profile DEFAULT
```

- [ ] **Step 3: Set column comments on every column Genie/the dashboard actually reference**

Run one `ALTER TABLE ... ALTER COLUMN ... COMMENT '...'` per column below (the exact column list a downstream consumer touches — `booking_id`, `user_id`, `property_id`, `check_in`, `check_out`, `total_amount`, `status`, `destination`, `__START_AT`, `__END_AT`):

```bash
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN booking_id COMMENT 'Primary key for a booking; stable across all SCD2 history rows for that booking.'" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN user_id COMMENT 'Traveler who made the booking. Join key to samples.wanderbricks.users.'" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN property_id COMMENT 'Property that was booked. Join key to samples.wanderbricks.properties.'" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN check_in COMMENT 'Check-in date for the stay.'" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN check_out COMMENT 'Check-out date for the stay.'" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN total_amount COMMENT 'Total booking price in the source currency, as of this status period.'" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN status COMMENT 'Booking status as of this status period (e.g. confirmed, cancelled). For the CURRENT status of a booking, filter WHERE __END_AT IS NULL.'" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN destination COMMENT 'Travel destination for the booked property, denormalized in from samples.wanderbricks.destinations via properties.destination_id.'" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN __START_AT COMMENT 'SCD Type 2 (Lakeflow-managed): timestamp this row became the effective status for the booking.'" \
  --profile DEFAULT
databricks experimental aitools tools query --warehouse "$WH" \
  "ALTER TABLE databricks_user_group_aitoolkit.wanderbricks.bookings_gold ALTER COLUMN __END_AT COMMENT 'SCD Type 2 (Lakeflow-managed): timestamp this row stopped being current. NULL means this row is the current status for the booking.'" \
  --profile DEFAULT
```

If any `ALTER COLUMN` fails because the inferred column name differs from what's listed here (e.g. Lakeflow's inference produced a different casing or the join dropped/renamed a column), use the actual column list from Step 1's `DESCRIBE TABLE EXTENDED` output instead of guessing — do not skip a column silently.

- [ ] **Step 4: Confirm comments landed**

```bash
databricks experimental aitools tools query --warehouse "$WH" \
  "DESCRIBE TABLE EXTENDED databricks_user_group_aitoolkit.wanderbricks.bookings_gold" \
  --profile DEFAULT
```

Expected: the table-level `Comment` field is populated, and every column listed in Step 3 shows its comment text.

- [ ] **Step 5: No commit for this task** — no file changes, only UC metadata applied directly to the live table (same category as Task 8's `SHOW GRANTS` checks — this is metadata on a table Lakeflow owns, not something declared in the bundle).

</details>

---

## Self-Review Notes

- **Spec coverage:** Component 1 (bronze/enriched/gold) → Tasks 2–4. Component 2 (bundle/pipeline resource, dev/prod targets, git branch guard) → Tasks 1, 5, 6 (schema resource already existed and is reused, not recreated). Component 3 (deploy & run) → Task 8. Component 4 (governance) → Task 9. Component 5 (dashboard) → Task 10. Component 6 (Genie, stretch) → Task 11. Task 7 (SQL warehouse) is not a spec component by name but is required infrastructure the spec's Components 3–6 all implicitly depend on ("whichever warehouse" / query execution) — made explicit and bundle-managed per direction received mid-planning.
- **Bundle-name deviation:** flagged explicitly under Global Constraints — this plan keeps `jdac6thedition_ai_dev_kit` as the bundle name rather than renaming to `wanderbricks-demo`, since the existing bundle already satisfies every structural requirement in Component 2 (dev/prod targets, catalog var, service-principal run_as, shared `wanderbricks` schema resource). Executors should confirm this with the user before Task 1 if they'd prefer the rename.
- **Grants and warehouse moved into the bundle (mid-planning revision):** the original draft applied the `SELECT` grant via an ad hoc `GRANT` SQL statement after deploy and assumed a pre-existing SQL warehouse resolved via `databricks warehouses list`. Per explicit direction, both are now bundle-declared: Task 7 adds a `resources.sql_warehouses` resource, and Task 9 adds a `grants:` block to the existing `resources.schemas.wanderbricks` resource. Since DABs has no table-level resource type, the schema-level grant is the only declarative option — Task 2 was revised to mark the bronze tables `private=True` so `bookings_gold` is the only table that grant actually reaches, preserving the spec's "grant only `bookings_gold`" constraint.
- **Resource key correction (discovered during Task 7 implementation):** the plan initially used `resources.warehouses` as the bundle resource key; the live CLI's own JSON schema (`databricks bundle schema`) confirmed the correct key is `resources.sql_warehouses` (`resources.SqlWarehouse` type). Task 7's implementer self-corrected and validated against the live workspace; every other reference to this resource across Tasks 8-11 and Global Constraints was corrected to match in the same pass. The same schema inspection also revealed `resources.genie_spaces` is a real bundle resource type — Task 11 was rewritten from a raw `databricks genie create-space` CLI call to a proper `resources.genie_spaces` bundle resource, consistent with the "everything bundle-managed" direction.
- **Execution-order revision (mid-execution):** per explicit direction, Tasks 7, 9, 10, and 11 had their live-deploy/live-query verification steps deferred — implementers for these tasks write and locally syntax-check their files only (no `bundle deploy`, no SQL queries, no `genie create-space`/git commit for 9-11); a later serialized pass runs `bundle validate --strict` → `bundle deploy` → the full live verification steps as originally specified, once, across all of Tasks 7-11 together, then commits each task's files in plan order. This was safe because none of Tasks 9/10/11's *file content* depends on Task 8's live table data — only their *verification steps* do.
- **Task 8 real findings (live deploy):** the pipeline's transformation logic ran correctly on the first try — no bugs there. Two real, separate bugs surfaced deploying the *supporting* resources against a live workspace and were fixed and committed: (1) the Genie space's `serialized_space` JSON needed `column_configs` sorted by `column_name` — the Genie API rejects unsorted arrays; (2) the Genie space's table identifier is a literal string baked into the JSON body, so it doesn't pick up `mode: development`'s automatic schema-name prefixing (`dev_<user>_wanderbricks`) — fixed with a dev-target-only `resources.genie_spaces` override pointing at a second, dev-schema-hardcoded JSON file (`src/genie/wanderbricks_gold.dev.geniespace.json`), added via `databricks.yml`'s per-target `resources:` override block. This dev-specific file is hand-maintained and hardcodes the current user's dev-prefixed schema name — flagged as known technical debt (would need updating if a different developer's username changes the dev schema prefix), not fixed further since this is a demo project on a single developer's workspace. A stale `bookings_gold` table from an earlier partial run also needed one full pipeline refresh (`databricks pipelines start-update --full-refresh`) before it would accept a schema; this is expected Lakeflow behavior for a stateful streaming table, not a defect.
- **Task 12 superseded (see Task 12's section for detail):** while debugging the Genie space live, Task 8's implementer also added `bookings_gold` table/column comments — via an explicit typed `schema=` (using the exact types Spark had already inferred, confirmed from the live error's own reported schema, not guessed) with inline `COMMENT` clauses in `bookings_gold.py`, rather than Task 12's originally-planned post-deploy `ALTER TABLE`/`COMMENT ON` SQL. This is a better mechanism (declarative, version-controlled, no bundle-external step) and fully satisfies Task 12's intent; Task 12 as originally written is not executed.
- **Open items not blocking completion:** (1) Task 8's Step 7 (validate `prod` on `main`) could not be performed as written because `main` currently has no bundle files at all (all of Tasks 1-11 live only on `meetup-prep`, not yet merged) — this is expected mid-feature-branch state, not a defect, and should be re-checked once this branch merges to `main`. (2) Only 1 of the Genie space's 3 sample questions was tested live via `genie start-conversation` (time-boxed, matches the spec's own "cut first if the demo runs long" framing for this stretch component) — the other two are covered by the `example_question_sqls` in the JSON but not live-conversation-tested.
- **`schema` bundle-variable deviation (found in final review):** the spec (`docs/presentation/wanderbricks-demo-spec.md`) calls for a `schema` bundle variable; this implementation instead references `${resources.schemas.wanderbricks.name}` everywhere, and was never documented as an intentional deviation until now. This was the better choice: it resolves through `mode: development`'s automatic schema-name prefixing, whereas a literal `var.schema` would not — this is precisely why the Genie space needed the dev-schema-hardcoded override file described above (Task 8 real findings, bug 2).
