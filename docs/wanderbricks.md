# Wanderbricks Demo

## Overview

Wanderbricks is a demo built inside this bundle's existing `jdac6thedition_ai_dev_kit` project (it is **not** a separate bundle, despite what the original spec's naming table said). It shows three things at once: turning raw change-event data into a proper CDC/SCD Type 2 history table with a Lakeflow Declarative Pipeline; governing that table with a bundle-managed grant instead of a manual `GRANT` statement run by hand after the fact; and doing all of it — pipeline, job, warehouse, schema grant, dashboard, and Genie space — as declarative resources in one bundle that deploys to both a `dev` and a `prod` target from the same `databricks.yml`. The payoff is a `bookings_gold` table that doesn't just show a booking's current status, but its full status history, and a dashboard/Genie space that can answer questions like "how did this change over time" as easily as "what does it look like right now."

## Architecture

The pipeline (`src/wanderbricks_etl/`) follows a Bronze → Enriched → Gold layering, implemented as Lakeflow Declarative Pipeline Python transformations (`pyspark.pipelines as dp`):

- `transformations/bookings_bronze.py` — streaming read of `samples.wanderbricks.bookings` (`spark.readStream.table(...)`). `private=True`: not published to Unity Catalog.
- `transformations/booking_updates_bronze.py` — same pattern, streaming read of `samples.wanderbricks.booking_updates`. Also `private=True`.
- `transformations/bookings_enriched.py` — a `dp.temporary_view` that stream-joins `bookings_bronze` against batch reads of `samples.wanderbricks.properties` (for `destination_id`) and `samples.wanderbricks.destinations` (for the display column `destination` — note `destinations` has no `name` column, only `destination`), dropping the join key afterward.
- `transformations/booking_updates_enriched.py` — identical join pattern applied to `booking_updates_bronze`.
- `transformations/bookings_gold.py` — declares an empty streaming table `dp.create_streaming_table(name="bookings_gold")` (schema left unspecified, inferred from the CDC sources), then attaches **two** `dp.create_auto_cdc_flow` flows into that same target:
  - `bookings_initial_cdc` — source `bookings_enriched`, treats each row of the baseline `bookings` table as the first CDC event for that booking.
  - `booking_updates_cdc` — source `booking_updates_enriched`, applies every subsequent status-change event.
  - Both flows use `keys=["booking_id"]`, `sequence_by="updated_at"`, `stored_as_scd_type=2`.

Two flows writing into one Auto CDC target is the reason it's a single `bookings_gold` table with full history rather than two separate tables: Lakeflow merges both event streams by `booking_id`/`updated_at` and materializes SCD Type 2 rows automatically, stamping each with `__START_AT` (when that row's status became effective) and `__END_AT` (when it stopped being current). There is no separate boolean "is current" column — the convention, used consistently by the dashboard and Genie space, is `WHERE __END_AT IS NULL` for "current row." This deviates from the original spec's ask for an explicit current-flag column, confirmed acceptable during implementation since it's the standard Lakeflow SCD2 pattern.

`bookings_gold` is the only table this pipeline publishes to Unity Catalog; `bookings_bronze` and `booking_updates_bronze` never leave the pipeline.

## Why the bronze tables are private

Declarative Automation Bundles has no table-level grant resource — the only declarative way to grant `SELECT` is at the schema level (see `resources/jdac6thedition_ai_dev_kit.schema.yml`, Governance below). A schema-level grant would normally expose *everything* published into that schema, including intermediate bronze copies of raw booking data that nobody asked to share. Marking `bookings_bronze` and `booking_updates_bronze` `private=True` means they never get published as Unity Catalog objects in the first place — `bookings_gold` is the only UC-visible table in the `wanderbricks` schema. That makes the schema-level grant functionally equivalent to a table-level grant on `bookings_gold`, without DABs needing to support one directly.

## Bundle resources

| File | Resource type / key | Purpose |
|---|---|---|
| `resources/wanderbricks_gold_pipeline.pipeline.yml` | `resources.pipelines.wanderbricks_gold_pipeline` | The Lakeflow pipeline itself: serverless, rooted at `src/wanderbricks_etl`, catalog/schema from `${var.catalog}` / `${resources.schemas.wanderbricks.name}`. |
| `resources/wanderbricks_gold_job.job.yml` | `resources.jobs.wanderbricks_gold_job` | A job with one `pipeline_task` that triggers `wanderbricks_gold_pipeline`; this is the job named in `databricks bundle run`. |
| `resources/wanderbricks_warehouse.warehouse.yml` | `resources.sql_warehouses.wanderbricks_warehouse` | A small (2X-Small, serverless, `auto_stop_mins: 10`), bundle-managed PRO SQL warehouse backing verification queries, the dashboard, and the Genie space. Note the resource type is `resources.sql_warehouses`, not `resources.warehouses` — the plan's original draft used the wrong key and was corrected against the live CLI schema (`databricks bundle schema`). |
| `resources/jdac6thedition_ai_dev_kit.schema.yml` | `resources.schemas.wanderbricks` | The pre-existing `wanderbricks` schema resource (shared with the taxi-sample scaffold's bundle), now carrying a `grants:` block (see Governance). |
| `resources/wanderbricks_dashboard.dashboard.yml` + `src/dashboards/wanderbricks_gold.lvdash.json` | `resources.dashboards.wanderbricks_gold` | The AI/BI (Lakeview) dashboard over `bookings_gold`, using the bundle-managed warehouse. |
| `resources/wanderbricks_genie_space.genie_space.yml` + `src/genie/wanderbricks_gold.geniespace.json` (`src/genie/wanderbricks_gold.dev.geniespace.json` for `dev`) | `resources.genie_spaces.wanderbricks_genie_space` | The stretch Genie space over `bookings_gold`. |

`resources.genie_spaces` is a real bundle resource type (confirmed via `databricks bundle schema`), not a raw `databricks genie create-space` CLI call as the implementation plan originally drafted — it is bundle-managed and deployed alongside everything else.

## Governance

`resources/jdac6thedition_ai_dev_kit.schema.yml` grants `SELECT` on the `wanderbricks` schema to the group `wanderbricks-viewers`:

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

Because `bookings_gold` is the only table published into that schema (see "Why the bronze tables are private" above), this schema-level grant is scoped exactly to `bookings_gold` in practice. Nothing is granted on the source tables in `samples.wanderbricks.*` (`bookings`, `booking_updates`, or any other table in that catalog) — that catalog is untouched by this project; whatever access the workspace already had on `samples.*` before this demo remains unchanged.

## Dashboard

`src/dashboards/wanderbricks_gold.lvdash.json`, deployed via `resources/wanderbricks_dashboard.dashboard.yml`, has two widgets on one page ("Wanderbricks Bookings"):

- **Revenue by Destination** (bar chart) — `SELECT destination, SUM(total_amount) AS revenue FROM bookings_gold WHERE __END_AT IS NULL GROUP BY destination ORDER BY 2 DESC`. Filters to current rows only, since revenue-by-destination is a snapshot metric.
- **Booking Status Breakdown Over Time** (stacked bar, colored by status) — `SELECT DATE_TRUNC('MONTH', __START_AT) AS month, status, COUNT(*) AS bookings FROM bookings_gold GROUP BY 1, 2 ORDER BY 1`. This query deliberately does **not** filter `__END_AT IS NULL` — it counts every SCD2 row, current or historical, bucketed by the month each status period started (`__START_AT`). That's the actual payoff of doing CDC/SCD2 properly instead of just keeping the latest status: this widget can show how the mix of statuses (e.g. confirmed vs. cancelled) has shifted over time, which a "just overwrite the row" table could never do.

The dashboard's `warehouse_id` points at the bundle-managed `wanderbricks_warehouse`, and `dataset_catalog`/`dataset_schema` resolve from `${var.catalog}` / `${resources.schemas.wanderbricks.name}`, so the dataset queries in the JSON use bare table names (`bookings_gold`) rather than fully-qualified ones.

## Genie space (stretch)

`resources/wanderbricks_genie_space.genie_space.yml` deploys a Genie space titled "Wanderbricks Bookings" over `bookings_gold`, using the same bundle-managed warehouse. It is bundle-managed like every other resource here — not a separate CLI-created space — so a future `bundle deploy` is the only supported way to change it (hand-editing via `genie update-space` would be overwritten on the next deploy).

The serialized space (`src/genie/wanderbricks_gold.geniespace.json`) ships three sample questions from the spec:

1. "What's our total revenue by destination?"
2. "How many bookings are confirmed vs. cancelled this month?"
3. "Which properties have the most bookings?"

Each has a paired example SQL query (all filtering `__END_AT IS NULL` for "current" semantics) plus column descriptions for `status`, `destination`, `__START_AT`, and `__END_AT`, and a text instruction telling Genie that `bookings_gold` is a Type 2 SCD table and to filter `__END_AT IS NULL` for "current"/"right now" questions, omitting it only when a question explicitly asks about history or change over time.

One implementation wrinkle not in the original plan: bundle variable substitution does not reach inside a Genie space's `file_path` JSON body, but `mode: development` still prefixes the UC schema name for the `dev` target (e.g. `dev_bjamrozik_wanderbricks`). Since the serialized space hardcodes the fully-qualified table identifier and SQL text, `databricks.yml`'s `dev` target overrides `file_path` to a separate file, `src/genie/wanderbricks_gold.dev.geniespace.json`, with the dev-prefixed schema name baked in; `prod` keeps the original `src/genie/wanderbricks_gold.geniespace.json` with the unprefixed `wanderbricks` schema name.

## Deploying and running

This demo deploys and runs like any other resource in the bundle — see `docs/deployment.md` for the full workflow. In short, from the repo root:

```bash
databricks bundle validate --strict -t dev --profile DEFAULT
databricks bundle deploy -t dev --profile DEFAULT
databricks bundle run wanderbricks_gold_job -t dev --profile DEFAULT
```

The `prod` target additionally requires the current git branch to be `main` (`git: branch: main` in `databricks.yml`) and runs as the `databricks_user_group_job_sp` service principal via the `run_as_service_principal` variable lookup; it is not part of the live demo flow but is structurally deployable the same way.
