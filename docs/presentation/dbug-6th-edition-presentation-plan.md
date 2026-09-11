# Databricks User Group 6th Edition — AI Dev Kit Presentation Plan

*Project repo: [jdac6thedition-ai-dev-kit](https://github.com/jdacvaibhav-dot/jdac6thedition-ai-dev-kit) (Bradley + Vaibhav), built on top of [databricks-solutions/ai-dev-kit](https://github.com/databricks-solutions/ai-dev-kit)*

---

## Presentation Structure

Three sections:

1. **Install & Configure** (~2 min)
2. **Best Practices**
3. **Live Demo / Walkthrough**

**Open decision:** the originally-planned ~3-slide deck ("install instructions + interactive Demo page") was scoped for a much lighter demo than what's now planned. Still need to decide whether the deck stays a thin intro that hands off to live terminal work, or grows to carry the best-practices content too.

---

## 1. Install & Configure (quick, ~2 min)

- **Prerequisite:** Databricks CLI v1.0.0+ must already be installed (`aitools` ships with the CLI, so this comes first — not something to install live on stage). Platform-native installers, pick whichever fits the room:
  - **macOS (Homebrew):** `brew tap databricks/tap && brew install databricks`
  - **Windows (WinGet):** `winget install Databricks.DatabricksCLI`
  - **Windows (Chocolatey, experimental):** `choco install databricks-cli`
  - **Linux / cross-platform fallback:** `curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh`
  - Verify (any platform): `databricks --version`
- Run: `databricks aitools install --skills-only`
- Curate `.claude/settings.local.json` using `skillOverrides` with mode `"user-invocable-only"` to suppress most skills from auto-trigger, leaving only project-relevant skills active by default.
- Brief contrast with the **default path**: plain `databricks aitools install` installs the official `databricks` plugin via marketplace for Claude Code / Codex / GitHub Copilot — auto-triggers everything it ships, no curation.
- Clarify scope is orthogonal to the plugin-vs-file distinction: both paths default to `project` scope, both support `--global`. The real contrast is **plugin-managed (auto-trigger everything)** vs. **file-managed + curated (allowlist only)** — not project vs. global.
- Skip MCP server setup entirely — it's a separate, now-deprecated/optional installer (`databricks-mcp-server/mcp_install.sh`). Worth a one-line mention of where it lives, not stage time.

### Skill profiles

A coarser, install-time filter — separate from (and one layer earlier than) `skillOverrides` curation. Selected via `--skills-profile <name>` (or the interactive prompt), it determines which skill files land on disk in the first place:

| Profile | Includes |
|---|---|
| `all` (default) | Everything |
| `data-engineer` | Pipelines, Structured Streaming, Jobs, DABs, DBSQL, Iceberg, Lakeflow Connect, Zerobus, metric views, synthetic data |
| `analyst` | AI/BI dashboards, DBSQL, Genie, metric views |
| `ai-ml-engineer` | Agent Bricks, AI Functions, Vector Search, Model Serving, Genie, PDF generation, MLflow evaluation + full MLflow skill set |
| `app-developer` | Apps, Lakebase, Model Serving, DBSQL, Jobs, DABs |

`databricks-core`, `databricks-docs`, `databricks-python-sdk`, `databricks-unity-catalog` are always installed regardless of profile. Profiles can be stacked (`--skills-profile data-engineer,ai-ml-engineer`) and the installer unions them.

**Key distinction for the deck:** profiles control *what's present on disk / managed by the CLI* (install-time). `skillOverrides` controls *how installed skills behave at runtime* (auto-trigger vs. invocation-only). They're independent layers — someone could install the `analyst` profile alone and still curate which of those skills auto-trigger, or install `all` and rely entirely on `skillOverrides` to do the narrowing (closer to this project's approach).

> **Naming check before slides/docs go out** — some skills were renamed when sourcing moved to `databricks-agent-skills`:
>
> | Old name | New name |
> |---|---|
> | `databricks-bundles` | `databricks-dabs` |
> | `databricks-genie` | `databricks-genie-agents` |
> | `databricks-spark-declarative-pipelines` | `databricks-pipelines` |
> | `databricks-lakebase-autoscale` / `-provisioned` | `databricks-lakebase` (merged) |
> | `databricks-config` | `databricks-core` (merged) |

---

## 2. Best Practices

- **Why curate at all**: default `aitools install` pulls every stable skill into auto-trigger context — fine for exploration, noisy for focused agent behavior.
- **Staying current**: skills are CLI-managed now (`databricks aitools update`/`uninstall`), decoupled from `ai-dev-kit` repo version bumps — don't confuse "update the kit" with "update the skills."
- **Scope discipline**: pick project vs. global deliberately rather than defaulting.
- **Manual vs. auto-trigger during a live demo**: auto-trigger reads naturally for "watch the agent figure out what to do" moments (schema explore, pipeline build, dashboard build). Manual invocation (`/skill-name`) reads better for "watch me control this precisely" moments (bundle packaging, governance) — lets the audience see exactly which skill just engaged.

---

## 3. Live Demo / Walkthrough

**Dataset:** [Wanderbricks](https://docs.databricks.com/aws/en/discover/wanderbricks-dataset) — Databricks' built-in simulated vacation-rental marketplace dataset, preloaded in the `samples` catalog on any Unity Catalog–enabled workspace (`samples.wanderbricks`). Tables include `users`, `hosts`, `properties`, `bookings`, `payments`, `booking_updates` (CDC feed), `reviews`, `clickstream`/`page_views`, `customer_support_logs`. No data staging needed.

### Full build list (in order)

| # | Step | Skill(s) | Notes |
|---|------|----------|-------|
| 1 | **Explore the schema** — inspect `samples.wanderbricks`, especially `booking_updates` | `databricks-core` / `databricks-dbsql` | Auto-trigger; "agent figures it out" moment |
| 2 | **Build a gold table with a pipeline** — Spark Declarative Pipeline: `bookings` + `booking_updates` (CDC) → SCD Type 2 gold table of booking history | `databricks-pipelines` | Auto-trigger |
| 3 | **Package as a multi-target bundle** — `databricks.yml` with `dev` (`mode: development`) and `prod` (`mode: production`) targets | `databricks-dabs` | Manual invoke recommended. `dev` auto-prefixes resources `[dev <user>]`, tags dev, marks pipeline `development: true`. `prod` validates pipeline `development: false`, checks git branch, expects `run_as` service principal. All from one file, one workspace, no extra infra. |
| 4 | **Deploy & run the dev target** — `databricks bundle deploy -t dev` → `databricks bundle run <job_name>` | — | Show the `[dev ...]`-prefixed resource in the workspace UI as visual proof |
| 5 | **Governance pass** — grant `SELECT` on the new gold table to a demo/reporting group; confirm via `SHOW GRANTS` that `payments`/`users` stay locked down | `databricks-unity-catalog` | Manual invoke recommended. **Decision made:** using grants (simple, always demoable solo) rather than column masking (flashier but needs a second test identity/role provisioned ahead of time to actually show the mask working — not doing this for now) |
| 6 | **Build a dashboard on top** — AI/BI dashboard from the gold table (revenue by destination, booking status over time) | `databricks-aibi-dashboards` | Auto-trigger; visual payoff moment |
| 7 | *(Stretch — cut first if short on time)* **Ask it in plain English** — Genie space over the gold table, natural-language question live | `databricks-genie-agents` | Decide after dry run whether this survives |

**Explicitly excluded:** Databricks Apps / AppKit demo — bigger lift (frontend + backend), belongs in its own session, not a bolt-on here.

**Skills in active rotation:** 6 core (`databricks-core`, `databricks-dbsql`, `databricks-pipelines`, `databricks-dabs`, `databricks-unity-catalog`, `databricks-aibi-dashboards`), 7 with the Genie stretch. `skillOverrides` allowlist should be finalized against whichever steps make the final cut, with auto-trigger vs. manual-invoke assigned per the table above.

---

## Demo Environment Plan

- **"Empty" repo** with the standard `ai-dev-kit` scaffolding — the starting point for the live build.
- **A separate branch with the project already completed** — fallback/reference if something breaks live, and possibly useful for before/after comparison during the walkthrough.

---

## Open Items / Still to Decide

- [ ] Overall time budget across the three sections (install/config, best practices, demo) — not yet fixed
- [ ] Whether the deck stays a thin intro or absorbs the best-practices content
- [ ] Full dry run of steps 1–6 to get real timing (pipeline + bundle deploy wait times are the main risk)
- [ ] Whether the Genie stretch (step 7) survives after the dry run
- [ ] Finalize `.claude/settings.local.json` `skillOverrides` once the build list above is locked
- [ ] Build out the "empty" scaffolding repo and the completed-project branch
