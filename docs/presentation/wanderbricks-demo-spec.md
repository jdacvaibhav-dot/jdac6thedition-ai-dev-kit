# Wanderbricks Demo — Build Specification

This is the functional/technical spec for the demo project referenced in the DBUG 6th Edition presentation plan. That doc covers stage narrative and timing; this doc covers what the thing being built actually needs to do. Claude Code should treat this as the source of truth for behavior — ask before deviating from it.

---

## ⚠️ Needs Bradley before this can be fully executed

These are real gaps, not defaults — Claude Code should stop and ask (or you should fill these in) rather than guessing:

- [x] Exact Databricks CLI profile name / auth config for the Origin Digital Lab workspace — `DEFAULT` profile (confirmed 2026-09-10).
- [x] Service principal for the `prod` target's `run_as` — already wired up in `databricks.yml` via the `run_as_service_principal` variable, looked up as `databricks_user_group_job_sp` (confirmed to exist, 2026-09-10). No change needed.
- [x] Viewer group name for the governance grant — `wanderbricks-viewers` (created, 2026-09-10).
- [x] Dev and prod catalog names — **both targets use `databricks_user_group_aitoolkit`** (confirmed 2026-09-10; the only other option, creating new `wanderbricks_dev`/`wanderbricks_prod` catalogs, was declined). Note: this means dev/prod share a catalog, which departs from the environment-separation goal below — schema-level and `mode: development`/`mode: production` separation still apply, but there is no catalog-level isolation. Naming-defaults table updated to match.
- [x] Exact column names in `samples.wanderbricks.booking_updates` — confirmed live via schema discovery (2026-09-10). See finalized design in Component 1 below.

---

## Environment

- **Workspace:** Origin Digital Lab — **same workspace/host for both `dev` and `prod` bundle targets.** Environment separation was originally planned via **separate catalogs**; as confirmed 2026-09-10, both targets instead share the `databricks_user_group_aitoolkit` catalog. Separation now comes from schema/resource-prefix behavior plus DABs' built-in `mode: development` / `mode: production` behaviors only — no catalog-level isolation.
- **Auth:** Databricks CLI, existing configured profile (see gap above).
- **Source data:** `samples.wanderbricks` — Databricks-provided sample dataset, read-only, preloaded in any Unity Catalog–enabled workspace. Do not attempt to write to or modify anything under `samples.*`.

---

## Source data reference (`samples.wanderbricks`)

| Table | Contents | Known join keys |
|---|---|---|
| `users` | Traveler/customer profiles: name, email, country/region, user type | `user_id` |
| `hosts` | Property owner/operator profiles | — |
| `properties` | Listings: title, type, price, destination | `property_id`, `destination_id` → `destinations` |
| `destinations` | Destination names/descriptions | `destination_id` |
| `bookings` | Check-in/out, guest count, `total_amount`, `status` | `user_id`, `property_id` |
| `payments` | Method, amount, status | `booking_id` |
| `booking_updates` | Booking state-change records for CDC | `booking_id` (exact columns TBD — see gap above) |
| `reviews` | Ratings, comments, `is_deleted` soft-delete flag | `property_id` |
| `clickstream` | Browse/click/search events, nested `metadata.device` etc. | `user_id`, `property_id` |
| `page_views` | Page view events | `user_id`, `property_id` |
| `customer_support_logs` | Support tickets, nested message arrays | `user_id` |

Not all of these are used in this project — see per-component sections below for what's actually touched.

---

## Component 1: Pipeline (`databricks-pipelines` skill)

**Goal:** Spark Declarative Pipeline producing a clean, queryable gold table of booking history, demonstrating CDC → SCD Type 2.

- **Sources:** `samples.wanderbricks.bookings`, `samples.wanderbricks.booking_updates`

### Finalized design (confirmed via live schema discovery, 2026-09-10)

**Schema findings:**
- `booking_updates` is **not a diff/delta feed** — it's a full row snapshot per change event: same columns as `bookings` (`booking_id`, `user_id`, `property_id`, `check_in`, `check_out`, `guests_count`, `total_amount`, `status`, `created_at`, `updated_at`), plus a `booking_update_id` surrogate key. Sequence column is `updated_at`.
- `destinations` has no `name` column (as originally assumed) — the display column is `destinations.destination`.

**Layer design (Python, matching the existing `@dp.table` style already in `src/jdac6thedition_ai_dev_kit_etl/transformations/`):**

1. **Bronze — streaming reads, no Auto Loader** (sources are static Delta tables, not a landing zone):
   - `bookings_bronze` ← `spark.readStream.table("samples.wanderbricks.bookings")`
   - `booking_updates_bronze` ← `spark.readStream.table("samples.wanderbricks.booking_updates")`

2. **Enrichment — temporary views** (stream-static join, feeding Auto CDC per the standard "preprocess before CDC" pattern):
   - `bookings_enriched`: `bookings_bronze` ⋈ `properties` (batch read) on `property_id` ⋈ `destinations` (batch read) on `destination_id` → adds `destination`
   - `booking_updates_enriched`: same join applied to `booking_updates_bronze`

3. **Gold — one empty streaming table, populated by two AUTO CDC flows into the same target:**
   - `dp.create_streaming_table("bookings_gold", schema=...)`
   - Flow `bookings_initial_cdc`: `create_auto_cdc_flow(target="bookings_gold", source="bookings_enriched", keys=["booking_id"], sequence_by="updated_at", stored_as_scd_type=2)` — treats the baseline `bookings` table as the first CDC event per booking.
   - Flow `booking_updates_cdc`: same target, source `booking_updates_enriched`, same keys/sequence_by/SCD type — applies subsequent status changes.
   - This yields full per-booking history with `__START_AT` / `__END_AT` set automatically by Lakeflow.

- **Output:** `bookings_gold`, containing at minimum: `booking_id`, `user_id`, `property_id`, `check_in`, `check_out`, `total_amount`, `status`, `destination`, `__START_AT`, `__END_AT` (Lakeflow-managed SCD2 columns).
- **Current-row flag:** no stored boolean column — current row = `WHERE __END_AT IS NULL`. This is the standard Lakeflow SCD2 pattern; the dashboard and Genie space queries should filter on `__END_AT IS NULL` rather than expecting a dedicated flag column. (Deviates from the original ask for an explicit current-flag column — confirmed acceptable.)
- **Denormalization for downstream use:** `destination` (not `destinations.name`) is joined in at the gold layer via `properties.destination_id`, rather than left to the dashboard — simplifies the AI/BI dashboard step below and keeps the Genie space (stretch) answering geography questions without needing multi-table joins.
- **Where it writes:** the catalog/schema are **not hardcoded** — they come from bundle variables (see Component 2). The pipeline resource in the bundle should reference `${var.catalog}.${var.schema}`.

### Resolved follow-up

`databricks.yml` sets the same catalog (`databricks_user_group_aitoolkit`) for both `dev` and `prod` targets — confirmed 2026-09-10 as the intended final config (see gaps section and Component 2 above). No changes needed to this file for catalog handling.

---

## Component 2: Multi-target Bundle (`databricks-dabs` skill)

**Goal:** one `databricks.yml`, two environment behaviors, same workspace.

- **Bundle name:** `wanderbricks-demo` (override if desired)
- **Variables:**
  - `catalog` — **same value for both targets**: `databricks_user_group_aitoolkit` (confirmed 2026-09-10 — dev/prod share a catalog; no per-target override needed)
  - `schema` — single shared default, `wanderbricks`
- **Resources:**
  - `resources.schemas` — a Unity Catalog schema resource, parameterized by `${var.catalog}` / `${var.schema}`. **The bundle creates this schema on deploy.** Note: DABs supports creating a *schema* this way but **not a catalog** — the catalog must already exist before `bundle deploy` runs (confirmed to exist).
  - `resources.pipelines` — the pipeline from Component 1, writing into that schema
  - `resources.jobs` — a job that triggers the pipeline (used in the deploy/run demo step)
- **Targets:**
  - `dev`:
    - `mode: development` → auto-prefixes resource names `[dev <user>]`, tags `dev`, marks the pipeline `development: true`
    - `variables.catalog:` `databricks_user_group_aitoolkit`
    - same `workspace.host` as prod (no separate workspace)
  - `prod`:
    - `mode: production` → validates pipeline is `development: false`, validates current git branch equals `main` (add `git: branch: main` to the target), recommends `run_as` a service principal
    - `variables.catalog:` `databricks_user_group_aitoolkit`
    - `run_as`: service principal `databricks_user_group_job_sp`, resolved via the `run_as_service_principal` variable lookup (already configured in `databricks.yml`, confirmed to exist)

This is the "one file, two behaviors" moment for the demo — worth generating the YAML with both targets visible side by side rather than as two separate files.

---

## Component 3: Deploy & Run

- `databricks bundle deploy -t dev`
- `databricks bundle run <job_name> -t dev`
- Confirm in the workspace UI: the `[dev <user>]`-prefixed pipeline and job exist, and the `wanderbricks` schema was created under the **dev catalog**.
- `prod` deploy is **not** part of the live demo (no need to actually run it on stage) — but the bundle should be structured so it *would* work if someone ran `databricks bundle deploy -t prod` with a valid service principal and the `main` branch checked out.

---

## Component 4: Governance (`databricks-unity-catalog` skill)

**Goal:** show governance as part of the build, not a follow-up ticket. Grants-based, not masking-based (masking needs a second test identity to actually demonstrate, which isn't in scope here).

- Grant `SELECT` on `${catalog}.${schema}.bookings_gold` to group **`wanderbricks-viewers`** (or Bradley's actual group name — see gap above). Bradley is creating this group; assume it exists.
- Explicitly **do not** grant anything on the raw/source tables this project touches (`bookings`, `booking_updates`) beyond what already exists by default in the workspace.
- Confirm via `SHOW GRANTS ON TABLE ${catalog}.${schema}.bookings_gold` (should show the new grant) and `SHOW GRANTS ON TABLE samples.wanderbricks.payments` (should show no grants added by this project — `samples.*` access is whatever the workspace already had, untouched by this build).

---

## Component 5: Dashboard (`databricks-aibi-dashboards` skill)

**Goal:** AI/BI dashboard on `bookings_gold`.

- **Widgets (minimum):**
  - Revenue by destination (uses the denormalized `destination` field from Component 1)
  - Booking status breakdown over time (uses SCD2 history — this is the payoff for having done CDC/SCD2 properly instead of just taking latest status)
- Source: `${catalog}.${schema}.bookings_gold` in whichever target was deployed for the demo (`dev`).

---

## Component 6 (Stretch — cut first if the demo runs long): Genie Space (`databricks-genie-agents` skill)

Keep this built out regardless of whether it's shown live — useful for people to reference in the repo afterward.

- Genie space over `${catalog}.${schema}.bookings_gold`.
- Sample natural-language questions to validate it against:
  - "What's our total revenue by destination?"
  - "How many bookings are confirmed vs. cancelled this month?"
  - "Which properties have the most bookings?"

---

## Naming defaults (all overridable — flag if you want different names)

| Thing | Default |
|---|---|
| Bundle name | `wanderbricks-demo` |
| Pipeline | `wanderbricks_gold_pipeline` |
| Job | `wanderbricks_gold_job` |
| Gold table | `bookings_gold` |
| Dev catalog | `databricks_user_group_aitoolkit` |
| Prod catalog | `databricks_user_group_aitoolkit` |
| Schema (both catalogs) | `wanderbricks` |
| Viewer group | `wanderbricks-viewers` |

---

## Skill-to-component map (quick reference)

| Component | Skill |
|---|---|
| Schema exploration | `databricks-core` / `databricks-dbsql` |
| Pipeline | `databricks-pipelines` |
| Bundle | `databricks-dabs` |
| Governance | `databricks-unity-catalog` |
| Dashboard | `databricks-aibi-dashboards` |
| Genie (stretch) | `databricks-genie-agents` |
