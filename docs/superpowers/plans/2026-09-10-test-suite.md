# Wanderbricks Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pytest-based regression test suite for the `jdac6thedition_ai_dev_kit` bundle covering data quality on the live `bookings_gold` CDC/SCD2 table, bundle-validate behavior (including the `prod` git-branch guard), governance grants, and dashboard/Genie SQL drift.

**Architecture:** Four new pytest modules under `tests/`, plus fixture additions to the existing `tests/conftest.py` (following its established live-Databricks-Connect pattern — `DatabricksSession.builder.getOrCreate()`, no local mocking) and a `live_pipeline` marker registered in `pyproject.toml` to separate fast/always-runnable tests (bundle validate) from tests that require `wanderbricks_gold_pipeline` to already be deployed and run at least once (data quality, governance, dashboard/Genie SQL). None of these tests import or call the `@dp.table` / `dp.create_streaming_table` / `dp.create_auto_cdc_flow` functions in `src/wanderbricks_etl/transformations/*.py` directly — that code only runs inside the Lakeflow pipeline runtime (it depends on an injected `spark` global and pipeline graph resolution that only exists mid-pipeline-execution) and cannot be unit-tested with plain pytest. Every test in this plan instead exercises the *deployed output* of that pipeline: the live `bookings_gold` table, live grants, and live dashboard/Genie SQL — exactly the substitution this repo's own implementation plan already prescribes (`bundle validate` → `bundle deploy` → `bundle run` → inspect live state, in place of "write failing unit test → make it pass").

**Tech Stack:** pytest, `databricks-connect` (already a dev dependency per `pyproject.toml`), `subprocess` (for `databricks bundle validate` / `git worktree` shell-outs), the Databricks CLI (already required by the project).

**Spec:** `docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md` (the resources and constraints this suite tests — read its Global Constraints and Self-Review Notes) and `docs/superpowers/plans/2026-09-10-github-actions-cicd.md` (the not-yet-implemented CI pipeline this suite will eventually slot into — see the Notes section at the end of this plan).

## Global Constraints

- **No local mocking.** Every test that touches Databricks state uses the live `spark` fixture from `tests/conftest.py` (`DatabricksSession.builder.getOrCreate()`) or shells out to the real `databricks` CLI — matching the existing `tests/sample_taxis_test.py` pattern exactly. Do not introduce `unittest.mock`, `pytest-mock`, or any local Spark session for these tests.
- **Do not unit-test the Lakeflow decorator code.** Nothing in this plan imports from `src/wanderbricks_etl/transformations/`. `@dp.table`, `dp.create_streaming_table`, and `dp.create_auto_cdc_flow` only resolve inside the Lakeflow pipeline runtime graph; calling the decorated functions directly raises `NameError` on the injected `spark` global outside that runtime.
- **Profile:** `DEFAULT` (matches `docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md`'s Global Constraints). Tests default to it but read `DATABRICKS_CLI_PROFILE` from the environment so a different profile can be substituted without editing test code.
- **Target:** tests default to `dev` but read `DATABRICKS_BUNDLE_TARGET` from the environment, since `dev`'s schema name is prefixed (`dev_<user>_wanderbricks`, per `mode: development`) while `prod`'s is not (`wanderbricks`) — hardcoding either would break the other target.
- **Catalog/schema resolution is dynamic, never hardcoded.** Because the dev schema name embeds a username (see `src/genie/wanderbricks_gold.dev.geniespace.json`'s `databricks_user_group_aitoolkit.dev_bjamrozik_wanderbricks` identifier), tests resolve the actual deployed catalog/schema via `databricks bundle validate -t <target> --profile <profile> -o json`, never by string-hardcoding a schema name.
- **Governance non-negotiable (from `docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md` Global Constraints):** `wanderbricks-viewers` must have `SELECT` and nothing beyond `SELECT` on the `wanderbricks` schema, and must have zero grants on any `samples.wanderbricks.*` table. Any regression here is a hard test failure, not a warning.
- **These tests assume a deployed, already-run pipeline where noted.** Tests marked `live_pipeline` (data quality, governance, dashboard/Genie SQL) are not standalone or mockable — they require `databricks bundle deploy -t <target>` and at least one successful `databricks bundle run wanderbricks_gold_job -t <target>` to have already happened against the target being tested. Bundle-validate tests (Task 2) have no such dependency and can run at any time, including on a fresh checkout with nothing deployed.
- **Do not touch or query anything under `samples.*` beyond read-only `SELECT`/`SHOW GRANTS`.** No `INSERT`/`UPDATE`/`GRANT`/`REVOKE` statements appear anywhere in this suite.

---

### Task 1: Data-quality tests against the deployed `bookings_gold` table

**Files:**
- Modify: `tests/conftest.py`
- Modify: `pyproject.toml`
- Create: `tests/bookings_gold_data_quality_test.py`

**Interfaces:**
- Consumes: the existing `spark` fixture (`tests/conftest.py`); the live `bookings_gold` table (must already be deployed and populated — see Global Constraints); `samples.wanderbricks.bookings` (read-only).
- Produces: new session-scoped fixtures `bundle_target`, `bundle_profile`, `bundle_resources`, `bookings_gold_fqn` in `tests/conftest.py`, reused by Tasks 2–4; the `live_pipeline` pytest marker, reused by Tasks 3–4.

- [ ] **Step 1: Add target/profile/resource-resolution fixtures to `tests/conftest.py`**

Add these imports and fixtures to the end of `tests/conftest.py` (the file already imports `os`, `sys`, `pathlib`, `json`, `pytest` at the top — add `subprocess` alongside them):

```python
import subprocess
```

```python
@pytest.fixture(scope="session")
def bundle_target() -> str:
    """Which bundle target's deployed resources these tests check.

    Defaults to `dev`. Override with `DATABRICKS_BUNDLE_TARGET=prod` to check
    prod instead (only meaningful once someone has actually deployed prod).
    """
    return os.environ.get("DATABRICKS_BUNDLE_TARGET", "dev")


@pytest.fixture(scope="session")
def bundle_profile() -> str:
    """Which named CLI profile (from ~/.databrickscfg) these tests authenticate with."""
    return os.environ.get("DATABRICKS_CLI_PROFILE", "DEFAULT")


@pytest.fixture(scope="session")
def bundle_resources(bundle_target: str, bundle_profile: str) -> dict:
    """Resolve the target's resolved resource graph via `databricks bundle validate -o json`.

    This is how tests learn target-specific names (e.g. `dev`'s
    `dev_<user>_wanderbricks` schema prefix from `mode: development`) without
    hardcoding a developer's username or duplicating databricks.yml's
    variable substitution logic in Python.
    """
    result = subprocess.run(
        [
            "databricks", "bundle", "validate",
            "-t", bundle_target,
            "--profile", bundle_profile,
            "-o", "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="session")
def bookings_gold_fqn(bundle_resources: dict) -> str:
    """Fully-qualified, backtick-quoted name of the deployed bookings_gold table."""
    schema = bundle_resources["resources"]["schemas"]["wanderbricks"]
    return f"`{schema['catalog_name']}`.`{schema['name']}`.`bookings_gold`"
```

- [ ] **Step 2: Register the `live_pipeline` marker in `pyproject.toml`**

Add this section to `pyproject.toml` (after the `[tool.ruff]` section):

```toml
[tool.pytest.ini_options]
markers = [
    "live_pipeline: requires wanderbricks_gold_pipeline to already be deployed and run at least once against the target under test (see tests/bookings_gold_data_quality_test.py module docstring). Not standalone/mockable.",
]
```

- [ ] **Step 3: Write the data-quality test module**

Create `tests/bookings_gold_data_quality_test.py`:

```python
"""Data-quality regression tests against the DEPLOYED, LIVE bookings_gold table.

These tests do NOT build or run the Lakeflow pipeline themselves, and they do
not import anything from src/wanderbricks_etl/transformations/. The
`@dp.table` / `dp.create_streaming_table` / `dp.create_auto_cdc_flow` code
there only runs inside the Lakeflow pipeline runtime (it depends on an
injected `spark` global and pipeline graph resolution that only exist
mid-pipeline-execution) and cannot be unit-tested with plain pytest.

Instead, these tests assume `wanderbricks_gold_pipeline` has already been
deployed (`databricks bundle deploy -t <target>`) and run at least once
(`databricks bundle run wanderbricks_gold_job -t <target>`), and they assert
on the resulting bookings_gold table. They are NOT standalone or mockable:
running them against an undeployed or never-run pipeline will fail with
"table not found" or empty-table assertions, not a useful signal about the
pipeline code itself.

Run against dev (default):
    uv run pytest tests/bookings_gold_data_quality_test.py -m live_pipeline

Run against prod (after a prod deploy + run has happened):
    DATABRICKS_BUNDLE_TARGET=prod uv run pytest tests/bookings_gold_data_quality_test.py -m live_pipeline
"""

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

pytestmark = pytest.mark.live_pipeline


def test_exactly_one_current_row_per_booking_id(spark: SparkSession, bookings_gold_fqn: str):
    current = spark.table(bookings_gold_fqn).where("__END_AT IS NULL")
    total_current_rows = current.count()
    distinct_booking_ids = current.select("booking_id").distinct().count()
    assert total_current_rows == distinct_booking_ids, (
        f"Expected exactly one current row (__END_AT IS NULL) per booking_id, "
        f"got {total_current_rows} current rows across {distinct_booking_ids} "
        f"distinct booking_id values in {bookings_gold_fqn}"
    )


def test_end_at_null_or_strictly_after_start_at(spark: SparkSession, bookings_gold_fqn: str):
    bad_rows = spark.table(bookings_gold_fqn).where(
        "__END_AT IS NOT NULL AND NOT (__START_AT < __END_AT)"
    )
    bad_count = bad_rows.count()
    assert bad_count == 0, (
        f"Found {bad_count} row(s) in {bookings_gold_fqn} where __END_AT is set "
        "but is not strictly after __START_AT"
    )


def test_required_columns_have_no_nulls(spark: SparkSession, bookings_gold_fqn: str):
    df = spark.table(bookings_gold_fqn)
    for column in ("booking_id", "status", "destination"):
        null_count = df.where(F.col(column).isNull()).count()
        assert null_count == 0, (
            f"Found {null_count} row(s) with NULL {column} in {bookings_gold_fqn}"
        )


def test_status_values_within_expected_set(spark: SparkSession, bookings_gold_fqn: str):
    expected_statuses = {"pending", "confirmed", "completed", "cancelled"}
    actual_statuses = {
        row["status"]
        for row in spark.table(bookings_gold_fqn).select("status").distinct().collect()
    }
    unexpected = actual_statuses - expected_statuses
    assert not unexpected, (
        f"Found status value(s) in {bookings_gold_fqn} outside the expected set "
        f"{expected_statuses}: {unexpected}"
    )


def test_row_counts_sane_relative_to_source(spark: SparkSession, bookings_gold_fqn: str):
    gold = spark.table(bookings_gold_fqn)
    gold_total = gold.count()
    gold_current = gold.where("__END_AT IS NULL").count()
    distinct_booking_ids = gold.select("booking_id").distinct().count()
    source_bookings = spark.table("samples.wanderbricks.bookings").count()

    assert gold_total > 0, f"{bookings_gold_fqn} is empty — has the pipeline been run?"
    assert 0 < gold_current <= gold_total, (
        f"Expected 0 < current_rows ({gold_current}) <= total_rows ({gold_total}) "
        f"in {bookings_gold_fqn}"
    )
    # Every distinct booking_id in bookings_gold originates from a row in the
    # baseline `bookings` snapshot (booking_updates only adds status-history
    # rows for booking_ids that already exist there), so the number of
    # distinct booking_ids in gold should never exceed the source row count.
    assert distinct_booking_ids <= source_bookings, (
        f"{bookings_gold_fqn} has {distinct_booking_ids} distinct booking_id "
        f"values, more than the {source_bookings} rows in "
        "samples.wanderbricks.bookings"
    )
```

- [ ] **Step 4: Run the new tests against a deployed `dev` target**

```bash
uv run pytest tests/bookings_gold_data_quality_test.py -v
```

Expected: if `wanderbricks_gold_pipeline` has been deployed and run in `dev` (per `docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md` Task 8), all 5 tests PASS. If the pipeline hasn't been run yet, tests fail with a `bookings_gold` table lookup or empty-table error — that is the expected, correct failure mode for an unrun pipeline, not a bug in the test.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py pyproject.toml tests/bookings_gold_data_quality_test.py
git commit -m "$(cat <<'EOF'
test: add bookings_gold data-quality regression tests

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Bundle-validate regression tests (dev, prod, and the `prod` branch guard)

**Files:**
- Create: `tests/bundle_validate_test.py`

**Interfaces:**
- Consumes: `bundle_profile` fixture (Task 1); the `databricks` CLI on `PATH`; the repo's git history (must have a `main` branch reachable locally, e.g. via `git fetch origin main:main` or an existing local `main`).
- Produces: nothing consumed by later tasks. No `live_pipeline` marker — these tests need no deployed pipeline, only a workspace reachable via `bundle_profile`.

- [ ] **Step 1: Write the bundle-validate test module**

Create `tests/bundle_validate_test.py`:

```python
"""Regression tests for `databricks bundle validate --strict` behavior.

These tests shell out to the real Databricks CLI against the real workspace
config in databricks.yml — there is no local bundle simulator. They require
no deployed pipeline (unlike tests/bookings_gold_data_quality_test.py), only
a working CLI profile that can reach the workspace.
"""

import pathlib
import subprocess
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent


def _run_validate(cwd: pathlib.Path, target: str, profile: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["databricks", "bundle", "validate", "--strict", "-t", target, "--profile", profile],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_dev_target_validates_cleanly(bundle_profile: str):
    result = _run_validate(REPO_ROOT, "dev", bundle_profile)
    assert result.returncode == 0, (
        f"Expected `bundle validate --strict -t dev` to exit 0, got "
        f"{result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_prod_target_rejects_non_main_branch(bundle_profile: str):
    """Regression test for the `git: branch: main` guard on the `prod` target
    in databricks.yml. Catches the guard silently breaking later (e.g. the
    `git:` block being accidentally removed, or a CLI upgrade changing how
    the check reports failure).

    Skips itself when run from `main` directly, since the negative case can
    only be observed from a non-main branch.
    """
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if branch == "main":
        pytest.skip("current branch is main — cannot observe the non-main rejection from here")

    result = _run_validate(REPO_ROOT, "prod", bundle_profile)
    assert result.returncode != 0, (
        "Expected `databricks bundle validate --strict -t prod` to fail on "
        f"non-main branch {branch!r}, but it exited 0. The `git: branch: "
        "main` guard in databricks.yml's prod target may have been removed "
        "or broken."
    )
    combined_output = (result.stdout + result.stderr).lower()
    assert "branch" in combined_output or "git" in combined_output, (
        "prod validate failed as expected but the output doesn't mention "
        "'branch' or 'git' — confirm this is the branch guard firing and not "
        f"an unrelated failure.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_prod_target_validates_cleanly_from_main(bundle_profile: str):
    """Positive case for the same guard: validate -t prod from a `main`
    worktree, without touching the caller's current branch or working tree."""
    with tempfile.TemporaryDirectory(prefix="wanderbricks-prod-validate-") as worktree_dir:
        add_result = subprocess.run(
            ["git", "worktree", "add", "--detach", worktree_dir, "main"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if add_result.returncode != 0:
            pytest.skip(
                "could not create a `main` worktree (no local `main` ref? "
                f"try `git fetch origin main:main` first).\n{add_result.stderr}"
            )
        try:
            result = _run_validate(pathlib.Path(worktree_dir), "prod", bundle_profile)
            assert result.returncode == 0, (
                f"Expected `bundle validate --strict -t prod` to exit 0 from "
                f"main, got {result.returncode}.\nstdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", worktree_dir],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
```

- [ ] **Step 2: Run the new tests from the current (non-`main`) branch**

```bash
uv run pytest tests/bundle_validate_test.py -v
```

Expected: `test_dev_target_validates_cleanly` PASSES; `test_prod_target_rejects_non_main_branch` PASSES (asserting the expected non-zero exit); `test_prod_target_validates_cleanly_from_main` PASSES if a local `main` ref exists, otherwise SKIPS with the "could not create a `main` worktree" message.

- [ ] **Step 3: Commit**

```bash
git add tests/bundle_validate_test.py
git commit -m "$(cat <<'EOF'
test: add bundle validate regression tests, including prod branch guard

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Governance regression tests (`wanderbricks-viewers` grants)

**Files:**
- Create: `tests/governance_test.py`

**Interfaces:**
- Consumes: `spark` fixture (`tests/conftest.py`); `bundle_resources` fixture (Task 1); the live `wanderbricks` schema grant (must already be deployed — `resources/jdac6thedition_ai_dev_kit.schema.yml`'s `grants:` block).
- Produces: nothing consumed by later tasks. Marked `live_pipeline` — the grant is deployed alongside the pipeline's schema resource, so these tests share the same "already deployed" precondition as Task 1.

- [ ] **Step 1: Write the governance test module**

Create `tests/governance_test.py`:

```python
"""Regression tests for the wanderbricks-viewers governance grant.

Non-negotiable constraint (docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md,
Global Constraints): do not grant anything beyond SELECT on bookings_gold,
and do not touch grants on bookings / booking_updates / any other
samples.wanderbricks.* table. Any drift from this is a hard test failure,
not a warning.

Requires the wanderbricks schema (resources/jdac6thedition_ai_dev_kit.schema.yml)
to already be deployed with its `grants:` block applied.
"""

import pytest
from pyspark.sql import SparkSession

pytestmark = pytest.mark.live_pipeline


def _grant_rows(spark: SparkSession, show_grants_sql: str) -> list[dict]:
    return [row.asDict() for row in spark.sql(show_grants_sql).collect()]


def test_viewers_group_has_select_and_only_select_on_wanderbricks_schema(
    spark: SparkSession, bundle_resources: dict
):
    schema = bundle_resources["resources"]["schemas"]["wanderbricks"]
    schema_fqn = f"`{schema['catalog_name']}`.`{schema['name']}`"
    rows = _grant_rows(spark, f"SHOW GRANTS ON SCHEMA {schema_fqn}")
    viewer_grants = [r for r in rows if r.get("Principal") == "wanderbricks-viewers"]
    privileges = {r.get("ActionType") for r in viewer_grants}

    assert "SELECT" in privileges, (
        f"Expected wanderbricks-viewers to have SELECT on schema {schema_fqn}, "
        f"found grant rows: {viewer_grants}"
    )
    assert privileges <= {"SELECT"}, (
        f"wanderbricks-viewers has privileges beyond SELECT on schema "
        f"{schema_fqn}: {privileges}. Non-negotiable constraint: SELECT only."
    )


def test_viewers_group_has_no_grants_on_samples_wanderbricks_tables(spark: SparkSession):
    tables = ("bookings", "booking_updates", "properties", "destinations", "payments")
    for table in tables:
        rows = _grant_rows(spark, f"SHOW GRANTS ON TABLE samples.wanderbricks.{table}")
        viewer_grants = [r for r in rows if r.get("Principal") == "wanderbricks-viewers"]
        assert not viewer_grants, (
            f"wanderbricks-viewers must have NO grants on "
            f"samples.wanderbricks.{table} (non-negotiable constraint), "
            f"found: {viewer_grants}"
        )
```

- [ ] **Step 2: Run the new tests against a deployed `dev` target**

```bash
uv run pytest tests/governance_test.py -v
```

Expected: both tests PASS if Task 9 of `docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md` has been deployed. If the grant hasn't been deployed yet, `test_viewers_group_has_select_and_only_select_on_wanderbricks_schema` fails with an assertion that `SELECT` wasn't found — the expected, correct failure mode for an undeployed grant.

- [ ] **Step 3: Commit**

```bash
git add tests/governance_test.py
git commit -m "$(cat <<'EOF'
test: add governance regression tests for wanderbricks-viewers grants

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Dashboard and Genie SQL regression tests

**Files:**
- Create: `tests/dashboard_genie_sql_test.py`

**Interfaces:**
- Consumes: `spark` fixture (`tests/conftest.py`); `bundle_target`, `bundle_resources` fixtures (Task 1); `src/dashboards/wanderbricks_gold.lvdash.json`; `src/genie/wanderbricks_gold.geniespace.json`; `src/genie/wanderbricks_gold.dev.geniespace.json`.
- Produces: nothing consumed by later tasks. Marked `live_pipeline` — these queries run against the live, populated `bookings_gold` table.

- [ ] **Step 1: Write the dashboard/Genie SQL test module**

Create `tests/dashboard_genie_sql_test.py`:

```python
"""Regression tests for the SQL embedded in the AI/BI dashboard's dataset
queries and the Genie space's example_question_sqls.

These run the EXACT SQL text extracted live from the JSON files (never a
hand-retyped copy), against the live bookings_gold table, so a later schema
change to bookings_gold that breaks one of these queries fails a test
immediately instead of surfacing later as "the dashboard/Genie space is
silently broken."

Requires the wanderbricks_gold_pipeline to already be deployed and run (see
tests/bookings_gold_data_quality_test.py's module docstring for the same
precondition).
"""

import json
import pathlib

import pytest
from pyspark.sql import SparkSession

pytestmark = pytest.mark.live_pipeline

REPO_ROOT = pathlib.Path(__file__).parent.parent
DASHBOARD_JSON = REPO_ROOT / "src" / "dashboards" / "wanderbricks_gold.lvdash.json"
GENIE_JSON_PROD = REPO_ROOT / "src" / "genie" / "wanderbricks_gold.geniespace.json"
GENIE_JSON_DEV = REPO_ROOT / "src" / "genie" / "wanderbricks_gold.dev.geniespace.json"


def _dashboard_queries() -> list[tuple[str, str]]:
    """Return [(dataset_name, query), ...] read straight from the dashboard JSON."""
    payload = json.loads(DASHBOARD_JSON.read_text())
    return [(dataset["name"], dataset["query"]) for dataset in payload["datasets"]]


def _genie_example_sqls(genie_json_path: pathlib.Path) -> list[tuple[str, str]]:
    """Return [(question, sql), ...] read straight from the geniespace JSON."""
    payload = json.loads(genie_json_path.read_text())
    return [
        (entry["question"][0], entry["sql"][0])
        for entry in payload["instructions"]["example_question_sqls"]
    ]


_DASHBOARD_QUERIES = _dashboard_queries()


@pytest.fixture()
def genie_json_path(bundle_target: str) -> pathlib.Path:
    """Mirrors databricks.yml's per-target file_path override for
    resources.genie_spaces.wanderbricks_genie_space: `dev` uses the file with
    the dev schema name hardcoded, every other target uses the original."""
    return GENIE_JSON_DEV if bundle_target == "dev" else GENIE_JSON_PROD


@pytest.mark.parametrize(
    "dataset_name,query",
    _DASHBOARD_QUERIES,
    ids=[name for name, _ in _DASHBOARD_QUERIES],
)
def test_dashboard_dataset_query_runs_and_returns_rows(
    spark: SparkSession, bundle_resources: dict, dataset_name: str, query: str
):
    schema = bundle_resources["resources"]["schemas"]["wanderbricks"]
    spark.sql(f"USE CATALOG `{schema['catalog_name']}`")
    spark.sql(f"USE SCHEMA `{schema['name']}`")
    result_rows = spark.sql(query).collect()
    assert len(result_rows) > 0, (
        f"Dashboard dataset {dataset_name!r} returned no rows.\nquery: {query}"
    )


def test_genie_example_question_sqls_run_and_return_rows(
    spark: SparkSession, genie_json_path: pathlib.Path
):
    for question, sql in _genie_example_sqls(genie_json_path):
        result_rows = spark.sql(sql).collect()
        assert len(result_rows) > 0, (
            f"Genie example question {question!r} returned no rows.\nsql: {sql}"
        )
```

- [ ] **Step 2: Run the new tests against a deployed `dev` target**

```bash
uv run pytest tests/dashboard_genie_sql_test.py -v
```

Expected: `test_dashboard_dataset_query_runs_and_returns_rows[revenue_by_destination]`, `test_dashboard_dataset_query_runs_and_returns_rows[status_by_month]`, and `test_genie_example_question_sqls_run_and_return_rows` all PASS once `bookings_gold` is deployed and populated with at least one booking per destination/status/property combination exercised by these queries. If `status_by_month`'s parametrized case returns zero rows, `booking_updates_bronze` rows likely haven't landed yet (only the baseline `bookings` snapshot has) — this mirrors the same check called out in `docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md` Task 10, Step 1.

- [ ] **Step 3: Commit**

```bash
git add tests/dashboard_genie_sql_test.py
git commit -m "$(cat <<'EOF'
test: add dashboard and Genie SQL regression tests

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Notes: slotting into the (currently unimplemented) GitHub Actions CI/CD plan

`docs/superpowers/plans/2026-09-10-github-actions-cicd.md` is not yet implemented (it is blocked on account-admin OIDC setup — see that plan's "Needs Bradley" section). When it is:

- **`validate.yml`'s `pytest` job (that plan's Task 2)** should run `uv run pytest -m "not live_pipeline"` — this covers `tests/bundle_validate_test.py` (Task 2 here) plus the existing `tests/sample_taxis_test.py`, none of which need a deployed Wanderbricks pipeline, so they're safe to run unattended on every PR against whichever ref the PR proposes.
- **Tests marked `live_pipeline`** (`tests/bookings_gold_data_quality_test.py`, `tests/governance_test.py`, `tests/dashboard_genie_sql_test.py`, Tasks 1/3/4 here) should NOT run in `validate.yml` — a PR hasn't deployed anything yet, so these would only ever fail with "table not found." They belong in a follow-up step added to `deploy-dev.yml` (that plan's Task 3), run with `uv run pytest -m live_pipeline` immediately after `databricks bundle deploy -t dev` and a `databricks bundle run wanderbricks_gold_job -t dev`, so a merge to `main` that breaks `bookings_gold`'s data quality, grants, or dashboard/Genie SQL is caught right after the dev deploy that would have introduced the regression — before anyone promotes the change to `prod` via that plan's manually-gated `deploy-prod.yml`.
- No changes to the CI/CD plan's files are made by this plan — that GitHub Actions setup doesn't exist yet, so there's nothing to wire up until it's implemented.

## Self-Review Notes

- **Spec coverage:** the five requested layers all have tasks — data quality (Task 1), bundle validate + prod branch-guard regression (Task 2), governance grants (Task 3), dashboard/Genie SQL drift (Task 4), and the CI/CD slot-in note (Notes section above, deliberately not a task since the CI/CD plan itself isn't implemented yet and this plan must not create files outside its own scope).
- **Live-only constraint respected throughout:** every test either uses the existing `spark` fixture against the live Databricks Connect session, or shells out to the live `databricks` CLI / `git`. No test imports from `src/wanderbricks_etl/transformations/` or constructs a local/mock SparkSession.
- **Dynamic schema resolution:** deliberately avoided hardcoding `dev_bjamrozik_wanderbricks` (or any other username-prefixed dev schema) anywhere in test code — all four test modules resolve catalog/schema via the `bundle_resources` fixture (`databricks bundle validate -o json`), which is the same technique `docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md` itself uses post-deploy (e.g. Task 8 Step 3's `WH=$(databricks bundle validate ... | jq ...)`). The one deliberate exception is `genie_json_path` in Task 4, which mirrors databricks.yml's own per-target `file_path` override rather than inventing a new resolution mechanism.
- **Branch-guard test avoids mutating the caller's working tree:** `test_prod_target_rejects_non_main_branch` reads the current branch without changing it; `test_prod_target_validates_cleanly_from_main` uses a disposable `git worktree` instead of `git checkout main` (which the original implementation plan does inline as a manual step) — this keeps the test suite safe to run against a working tree with uncommitted changes.
- **Type/fixture consistency check:** `bundle_target`, `bundle_profile`, `bundle_resources`, and `bookings_gold_fqn` are defined once in Task 1's `tests/conftest.py` changes and referenced by identical names in Tasks 2–4 with no renaming drift. The `live_pipeline` marker string is identical everywhere it's used (`pyproject.toml` registration, and `pytestmark = pytest.mark.live_pipeline` in Tasks 1, 3, and 4's modules; Task 2 intentionally has no marker).
- **No placeholders:** every step includes complete, runnable code — no "add appropriate assertions" or TBD markers anywhere in this plan.
