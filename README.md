# jdac6thedition-ai-dev-kit
Databricks User Group 6th Edition Virtual meetup Repo

A Declarative Automation Bundle (DAB) containing the Wanderbricks booking status
history solution.

* `resources/`: Resource configurations (pipeline, warehouse, dashboard, Genie agent, schema).
* `src/wanderbricks_etl/`: Pipeline source code.

### Getting started

Choose how you want to work on this project:

(a) Directly in your Databricks workspace, see
    https://docs.databricks.com/dev-tools/bundles/workspace.

(b) Locally with an IDE like Cursor or VS Code, see
    https://docs.databricks.com/dev-tools/vscode-ext.html.

(c) With command line tools, see https://docs.databricks.com/dev-tools/cli/databricks-cli.html

If you're developing with an IDE, dependencies for this project should be installed using uv:

*  Make sure you have the UV package manager installed.
   It's an alternative to tools like pip: https://docs.astral.sh/uv/getting-started/installation/.
*  Run `uv sync --dev` to install the project's dependencies.

### Using this project via the CLI

1. Authenticate to your Databricks workspace, if you have not done so already:
    ```
    $ databricks configure
    ```

2. To deploy a development copy of this project, type:
    ```
    $ databricks bundle deploy --target dev
    ```
    (Note that "dev" is the default target, so the `--target` parameter
    is optional here.)

3. Similarly, to deploy a production copy, type:
   ```
   $ databricks bundle deploy --target prod
   ```

4. To run a job or pipeline, use the "run" command:
   ```
   $ databricks bundle run
   ```

### Wanderbricks booking status history

A self-contained solution. Every object below is declared in `resources/*.yml` — nothing is
created by hand in the workspace.

* **Pipeline** (`resources/wanderbricks.pipeline.yml`, code in
  `src/wanderbricks_etl/transformations/`): a Spark Declarative Pipeline that runs
  bronze → silver → gold.
  * *bronze*: raw `bookings` and `booking_updates` streamed in as-is.
  * *silver*: `booking_status_history`, an SCD Type 2 table built with `AUTO CDC` — one row
    per status version per booking, with validity windows and a current-version flag.
  * *gold*: `booking_status_gold`, the history joined to booking attributes (destination,
    dates, amount) for BI and natural-language use.
* **Gold table**: `${var.catalog}.<schema>.booking_status_gold`; in dev that resolves to
  `databricks_user_group_aitoolkit.dev_bjamrozik_wanderbricks.booking_status_gold`.
* **SQL warehouse**: `wanderbricks_bi`, serving both the dashboard and the Genie agent.
* **Dashboard**: `wanderbricks_bookings` (`resources/wanderbricks_bookings.lvdash.json`) —
  an AI/BI dashboard over the gold table covering booking volume, status transitions over
  time, cancellation rate, and revenue.
* **Genie agent**: `wanderbricks_bookings_agent`, a curated space for natural-language
  questions against the gold table.
* **Access**: the bundle grants the `wanderbricks-viewers` group `USE_SCHEMA` + `SELECT` on
  the Wanderbricks schema. That group already holds `USE_CATALOG` on the catalog, so the
  read chain is complete and nothing outside this schema is modified.

Targets: `dev` (development mode, resources prefixed and scoped to your own user) and
`prod` (production mode, running as the `databricks_user_group_job_sp` service principal).
The `prod` target sets `git.branch: main`, so `databricks bundle deploy -t prod` refuses to
run from any other branch.
