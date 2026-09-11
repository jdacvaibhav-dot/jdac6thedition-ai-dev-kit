# Demo Branch Cleanup & Talking Points

Planning document only — nothing in this repo is changed by writing this file. Everything
below describes work Bradley executes himself, later, on a **new branch**. It is written
against the repo state as of 2026-09-10 (branch `meetup-prep`, latest commit `367601a`).

**Premise:** the DBUG 6th Edition demo works best if the audience watches an AI coding
agent actually build the Wanderbricks CDC/SCD2 pipeline live, using the Databricks AI
Tools, the same way it was actually built this session (see
`docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md`). That only reads
as real if the repo on stage doesn't already contain the finished pipeline, the finished
bundle resources, or (critically) a pre-installed `.claude/` skills setup — otherwise the
"install & configure" and "watch it figure out the schema" beats in
`dbug-6th-edition-presentation-plan.md` are theater, not demonstration.

---

## Non-negotiable safety constraints

- **Nothing in this plan touches `meetup-prep` or `main` destructively.** Both stay
  exactly as they are.
- All wiping happens on a **new branch**, created only after the current state is fully
  captured (see Step 0 below).
- The finished reference implementation is **preserved**, not deleted — either left
  intact on `meetup-prep` (already true) and/or tagged, so it's a permanent fallback and
  a source for a future blog post / repo README.
- **Important pre-existing fact to account for:** as of this writing, several files that
  the AI tools need to function are *uncommitted* on `meetup-prep` — `AGENTS.md`,
  `CLAUDE.md`, `docs/`, `tests/`, `fixtures/`, `pyproject.toml`, `uv.lock`, `.claude/`,
  and the original taxi-sample scaffold (`resources/jdac6thedition_ai_dev_kit_etl.pipeline.yml`,
  `resources/sample_job.job.yml`, `src/jdac6thedition_ai_dev_kit/`,
  `src/jdac6thedition_ai_dev_kit_etl/`, `src/sample_notebook.ipynb`) are all untracked.
  `README.md` and `src/wanderbricks_etl/transformations/bookings_gold.py` have unstaged
  edits. **Before creating the demo branch, commit (or explicitly decide to discard) this
  working-tree state on `meetup-prep` first** — otherwise "preserve the finished work" is
  not actually true yet, it only exists on disk.

---

## Part 1 — Repo cleanup checklist for the demo branch

### Step 0: Checkpoint the current state (on `meetup-prep`, before branching)

- [ ] Review `git status` / `git diff` on `meetup-prep`; commit the outstanding changes
      (`README.md`, `src/wanderbricks_etl/transformations/bookings_gold.py`, and the
      untracked files listed above) as one or more normal commits. This is the "finished
      reference implementation" checkpoint.
- [ ] Tag it for safekeeping, e.g. `git tag wanderbricks-reference-v1` (or push a
      long-lived branch like `wanderbricks-complete`) — this is the fallback/reference
      copy called for in the presentation plan's "Demo Environment Plan" section.
- [ ] Create the demo branch from this checkpoint: `git checkout -b demo-live-build`
      (name it whatever — just not `main`/`meetup-prep`). All remaining steps happen on
      `demo-live-build` only.

### Category-by-category calls

| Category | Path(s) | Call | Why |
|---|---|---|---|
| **Databricks AI Tools skill install (`.claude/`)** | `.claude/` (entire directory — currently untracked/local-only) | **REMOVE** | This is the single most consequential removal. Presentation plan Section 1 ("Install & Configure") is scripted as a *live* `databricks aitools install --skills-only` + `.claude/settings.local.json` curation. If `.claude/` already exists with skills installed, that opening beat is fake. Delete the local directory before going on stage (it's gitignored/untracked already, so this is a filesystem `rm -rf .claude/`, not a git operation). |
| **Wanderbricks pipeline source** | `src/wanderbricks_etl/` (README, `transformations/bookings_bronze.py`, `booking_updates_bronze.py`, `bookings_enriched.py`, `booking_updates_enriched.py`, `bookings_gold.py`, plus `__pycache__/`) | **REMOVE** | This is the actual artifact the live demo exists to (re)build via `databricks-pipelines`. Keeping it defeats the premise. |
| **Pipeline/job/warehouse bundle resources** | `resources/wanderbricks_gold_pipeline.pipeline.yml`, `resources/wanderbricks_gold_job.job.yml`, `resources/wanderbricks_warehouse.warehouse.yml` | **REMOVE** | Rebuilt live via `databricks-dabs` in the "package as a bundle" / "deploy & run" steps. |
| **Governance grant** | The `grants:` block inside `resources/jdac6thedition_ai_dev_kit.schema.yml` | **REMOVE** the `grants:` block | Rebuilt live via `databricks-unity-catalog` in the governance step. |
| **Wanderbricks schema resource itself** | `resources/jdac6thedition_ai_dev_kit.schema.yml` (the base `wanderbricks` schema declaration, minus grants) | **JUDGMENT CALL — lean REMOVE** | Tradeoff: the demo spec treats schema creation as part of Component 2 (bundle packaging), so rebuilding it live is more authentic and costs almost no stage time (one short YAML block). Keeping it is defensible if you want one less thing that could go wrong live and don't consider "create a UC schema resource" an interesting thing to watch an agent do. Pick one and be consistent — don't half-remove it. |
| **Dashboard** | `src/dashboards/wanderbricks_gold.lvdash.json`, `resources/wanderbricks_dashboard.dashboard.yml` | **REMOVE** | Rebuilt live via `databricks-aibi-dashboards` — this is the "visual payoff" step in the presentation plan and loses its payoff if the chart already exists. |
| **Genie space (stretch)** | `src/genie/wanderbricks_gold.geniespace.json`, `src/genie/wanderbricks_gold.dev.geniespace.json`, `resources/wanderbricks_genie_space.genie_space.yml` | **REMOVE** | Marked "stretch — cut first if short on time" in both the stage plan and the spec. If it's cut live, its files shouldn't be sitting there anyway; if there's time, rebuild it live for the same reason as the dashboard. |
| **Prod git-branch guard** | The `git: branch: main` block inside the `prod` target of `databricks.yml` | **JUDGMENT CALL — lean REMOVE, rebuild live** | This is genuinely one of the best "wow" moments available (see Part 2) — a real safety feature, not staged. It reads *better* if the agent adds it live during the "package as a bundle" step (framed as "let's also make prod safe") and is then immediately triggered by attempting a prod validate/deploy from the demo branch (which, correctly, is not `main`). Keeping it pre-built and only triggering the failure is a smaller but still valid version of the same beat — acceptable if stage time is tight. |
| **Base bundle skeleton** | `databricks.yml` (bundle name, `workspace.host`, `dev`/`prod` target shells, `catalog`/`run_as_service_principal` variables — everything except the wanderbricks-specific resource references and the git-branch guard covered above) | **KEEP** | Explicit tradeoff, as requested: removing this and running `databricks bundle init` live would be maximally "from scratch," but it adds real stage time and a new failure surface (workspace host entry, template selection, auth) for very little audience payoff — the presentation plan's own "Demo Environment Plan" already assumes an "'Empty' repo with the standard ai-dev-kit scaffolding" as the starting point, i.e. a scaffolded-but-unbuilt bundle, not a from-nothing `bundle init`. Recommendation: **keep the skeleton**, spend the saved time on the pipeline/CDC build instead. If Bradley wants the extra authenticity beat anyway, `bundle init` is a fine cold-open before the recorded steps begin (not during the timed demo). |
| **Original taxi-sample scaffold** | `resources/jdac6thedition_ai_dev_kit_etl.pipeline.yml`, `resources/sample_job.job.yml`, `src/jdac6thedition_ai_dev_kit/`, `src/jdac6thedition_ai_dev_kit_etl/`, `src/sample_notebook.ipynb` | **KEEP** | This *is* "the standard ai-dev-kit scaffolding" the presentation plan's Demo Environment Plan calls for as the starting point. Removing it doesn't buy anything and would make the "empty" repo look hand-crafted rather than template-generated. |
| **AGENTS.md / CLAUDE.md** | `AGENTS.md`, `CLAUDE.md` | **KEEP** | Required — these are exactly the files that tell a fresh coding agent to read the `databricks-core` skill and run `databricks aitools install` if it's missing. Removing them breaks the bootstrap story the demo is trying to tell. |
| **README.md** | `README.md` | **KEEP** | The DAB-generated "Getting started" section added this session is harmless, accurate boilerplate. No reason to revert it for the demo; it doesn't spoil anything. |
| **`tests/`, `fixtures/`, `pyproject.toml`, `uv.lock`** | as named | **KEEP** | Project plumbing (`uv sync`, `pytest` against `taxis.py`) unrelated to the wanderbricks build; needed for the repo to function at all. |
| **`.vscode/`, `assets/`** | as named | **KEEP** | Local editor config and (presumably) presentation image/asset files; harmless, not part of the "what does the agent build" story either way. |
| **Presentation spec** | `docs/presentation/wanderbricks-demo-spec.md` | **ARCHIVE-ELSEWHERE (remove from demo branch)** | This is the exact finalized design — schema layout, table names, join keys, naming defaults — i.e. the answer key. If it's present, an agent (or a curious audience member glancing at the repo) can just read the answer instead of exploring `samples.wanderbricks` live. It stays fully intact on `meetup-prep`/the tag for Bradley's own reference while presenting. |
| **Implementation ledger** | `docs/superpowers/plans/2026-09-10-wanderbricks-full-implementation.md` | **ARCHIVE-ELSEWHERE (remove from demo branch)** | Even more so than the spec — this is literal working code for every file, task-by-task. Must not be visible/discoverable on the demo branch. Preserve it; it's genuinely valuable as a "here's what really happened" writeup afterward. |
| **CI/CD planning doc** | `docs/superpowers/plans/2026-09-10-github-actions-cicd.md` | **REMOVE from demo branch** | Not part of this demo's scope; unrelated planning clutter. Low stakes either way, but a "clean" repo reads better without an unrelated in-flight plan sitting in `docs/`. Preserve on `meetup-prep`. |
| **Wanderbricks reference docs** | `docs/wanderbricks.md`, `docs/deployment.md` | **ARCHIVE-ELSEWHERE (remove from demo branch)** | Same spoiler risk as the spec doc if these describe the finished pipeline/deployment — worth a quick read before deciding, but default to removing since "finished-state documentation" undercuts a from-scratch build. Preserve on `meetup-prep`. |
| **Presentation stage plan itself** | `docs/presentation/dbug-6th-edition-presentation-plan.md` | **KEEP (arguably), but consider ARCHIVE-ELSEWHERE too** | This is Bradley's own speaker notes, not agent-facing spec content — it doesn't tell an agent how to build anything, so it's lower spoiler risk than the spec/ledger. Fine to leave in the repo for anyone who finds it after the talk, or pull it out if the goal is a maximally minimal "empty" repo. Not consequential either way — presenter's call. |
| **SDD ledger** | `.superpowers/sdd/2026-09-10-wanderbricks-full-implementation/` (task briefs, reports, diffs) | **N/A for git — already gitignored** | `.superpowers/` is in `.gitignore`; this never gets committed regardless of branch. The only action needed is *local filesystem* hygiene: if presenting from this same working directory/clone, delete this local folder (or use a fresh `git clone`/worktree for the demo) so a `Cmd+Space` file search or an errant `ls .superpowers` on stage doesn't reveal it. Preserve a copy elsewhere first if it has value as a build log. |
| **`notes_as_i_do_things.md`** | `notes_as_i_do_things.md` (repo root, untracked) | **REMOVE from demo branch** | Reads as Bradley's personal scratch notes; no reason for it to be in a repo the audience sees. Keep on `meetup-prep`. |

### Execution order (once on `demo-live-build`)

1. [ ] `git rm -r` the REMOVE-tier tracked paths (pipeline source, resource YAMLs,
       dashboard/genie files, grants block edit, spec/ledger/CI-CD/wanderbricks docs,
       `notes_as_i_do_things.md`, and the prod git-branch block/schema resource per
       whichever judgment call was made above).
2. [ ] `rm -rf .claude/` (filesystem only — untracked, no git action needed) and confirm
       `git status` shows it gone from the working tree.
3. [ ] `rm -rf .superpowers/` locally if reusing this clone for the live demo (or just
       demo from a fresh clone/worktree instead — simpler and safer).
4. [ ] Run `databricks bundle validate --strict -t dev` on what remains — it should still
       pass (original taxi scaffold + trimmed `databricks.yml` + `AGENTS.md`/`CLAUDE.md`
       + project plumbing). Fix anything that doesn't validate before calling the branch
       demo-ready.
5. [ ] Commit the wipe as a single clear commit on `demo-live-build` (e.g. "reset to
       pre-build state for live demo") so the branch has an obvious, reviewable diff from
       `meetup-prep`.
6. [ ] Do a full dry run from this exact branch state before the actual talk — the
       presentation plan's own "Open Items" list already calls for "a full dry run of
       steps 1–6 to get real timing," and that dry run should happen *against this
       cleaned branch*, not against the already-built one.

---

## Part 2 — Demo talking points

Aligned to the existing structure in `dbug-6th-edition-presentation-plan.md`: three
sections — **1. Install & Configure (~2 min)**, **2. Best Practices**, **3. Live Demo /
Walkthrough** — with the live-build sequence following that doc's "Full build list"
table order (schema explore → pipeline/CDC/SCD2 → bundle package → deploy/run →
governance → dashboard → Genie stretch). No new structure invented here.

### Hook / why (open with this, before touching a keyboard)

- CDC → SCD Type 2 is one of the most reliably painful things in data engineering:
  hand-rolled merge logic, manual `__START_AT`/`__END_AT` bookkeeping, easy to get subtly
  wrong (duplicate current rows, wrong ordering column, forgetting a tie-breaker).
- Lakeflow's `create_auto_cdc_flow(..., stored_as_scd_type=2)` collapses that into a
  declarative one-liner per source — but the *interesting* claim isn't "the feature
  exists," it's "an AI agent, using the right skill, picks the right pattern (bronze →
  enriched → Auto CDC gold) without being told the pattern in advance."
- The rest of the stack — packaging as a DAB, governance, dashboard, Genie — is the same
  claim repeated: not "AI writes code," but "AI, given the right tool-use skills, does
  the whole platform-engineering lifecycle, not just the transform."

### Live-build sequence (mirrors the actual task order that worked this session)

1. **Install & Configure (~2 min)** — `databricks aitools install` (the marketplace
   plugin, default) on a repo with no `.claude/` yet. Show the plugin land, then show
   curating `skillOverrides` to `user-invocable-only` so only project-relevant skills
   auto-trigger. Mention `databricks aitools install --skills-only --scope project` as an
   **option** — raw skills only, no plugin wrapper, project-scoped — for teams that want
   skills without the marketplace packaging. Leading with the plugin install and treating
   `--skills-only` as a variant (not the reverse) is a **best-practices** point, not filler.
2. **Explore the schema** (`databricks-core`/`databricks-dbsql`, auto-trigger) — point the
   agent at `samples.wanderbricks`, specifically `booking_updates`. Let it discover live
   that `booking_updates` is a full-row snapshot per event (not a diff feed) and that
   `destinations.destination` (not `.name`) is the display column. This is a genuine
   "agent figures it out" moment — it's exactly what had to be discovered this session.
3. **Build the pipeline** (`databricks-pipelines`) — bronze (streaming reads,
   `private=True`) → enriched (temp views, stream-static join in `destination`) → gold
   (`create_streaming_table` + two `create_auto_cdc_flow`s, SCD2). Narrate *why*
   bronze is pipeline-private as it's decided: it's what makes the later governance grant
   safe to scope at the schema level.
4. **Package as a multi-target bundle** (`databricks-dabs`, manual invoke) — one
   `databricks.yml`, `dev`/`prod` targets side by side. This is also where the
   git-branch guard gets added if that's the judgment call made in Part 1.
5. **Deploy & run `dev`** — `bundle deploy -t dev` → `bundle run wanderbricks_gold_job`.
   Show the `[dev <user>]`-prefixed resources in the workspace UI as visual proof.
6. **Governance** (`databricks-unity-catalog`, manual invoke) — grant `SELECT` on the
   `wanderbricks` schema to `wanderbricks-viewers`; `SHOW GRANTS` to prove `payments`/
   `bookings`/`booking_updates` are untouched.
7. **Dashboard** (`databricks-aibi-dashboards`, auto-trigger) — revenue by destination,
   booking-status-over-time. The status-over-time chart is the actual payoff for having
   done CDC/SCD2 properly: it only shows multiple status colors across time because the
   history is real, not "latest status only."
8. **Stretch: Genie space** (`databricks-genie-agents`) — only if time allows; ask it one
   of the three validated sample questions live. Cut first if the demo is running long,
   per the existing plan.

### 2–3 moments designed to land

- **The git-branch guard actually blocking a prod deploy.** Not staged — running
  `databricks bundle validate --strict -t prod` (or `deploy -t prod`) from
  `demo-live-build` (which is not `main`) will genuinely fail with a branch-mismatch
  error, because that's a real DABs `mode: production` + `git: branch: main` check, not a
  scripted failure. This is the single best "this isn't a canned demo" beat available —
  call it out explicitly as such in the moment ("this isn't a trick, watch what happens
  if I try to deploy to prod from the wrong branch").
- **The schema-discovery moment on `booking_updates`.** Let the agent genuinely explore
  instead of narrating the answer — the reveal that it's a full snapshot rather than a
  diff feed is a real "aha" that happened this session; it reads as authentic because it
  is.
- **The SCD2 payoff in the dashboard.** The booking-status-over-time chart showing
  multiple statuses across multiple months is the visual proof that the CDC/SCD2 design
  actually worked, not just that a chart got built. Point at it explicitly: "if we'd just
  taken the latest status, this chart would be one flat line."

### If something fails live

- **Decide in advance to mention, not hide, a real fix if one is needed.** This session's
  first live run of `bookings_gold` did in fact need a follow-up fix (the pipeline's
  schema was left un-typed for `create_streaming_table` initially, then given an explicit
  typed schema with column comments once that mattered for Genie/UC metadata quality —
  see the uncommitted diff on `src/wanderbricks_etl/transformations/bookings_gold.py` at
  planning time). **Recommendation: treat a real fix as an authenticity beat, not
  something to route around.** An AI-assisted build that never needs a single correction
  reads as suspicious to a technical audience; one visible, quickly-diagnosed fix
  ("the pipeline event log told us exactly what broke, one edit, redeploy, done") is a
  *better* demo of the actual workflow (`bundle validate` → `deploy` → `run` →
  `list-pipeline-events` → fix → redeploy) than a flawless run would be. The one thing to
  avoid: spending stage time debugging something novel/unexpected. If something breaks in
  a way that isn't the known, already-diagnosed class of issue, **switch to the tagged
  reference branch/checkpoint** (`wanderbricks-reference-v1` from Part 1) and finish the
  walkthrough narrating against the known-good build rather than troubleshooting live.
- Have the reference branch pulled up in a second terminal tab/window before starting, not
  found under time pressure.

### Closing point (connect back to the DBUG audience)

- The audience is data engineers/platform folks who already know CDC/SCD2 is
  historically a hand-rolled, error-prone pattern — the closing point isn't "AI wrote
  code," it's **"the agent used the same skills, the same CLI, the same DABs workflow you
  would use — it didn't do anything you couldn't inspect, review, and diff."** Every step
  shown produced ordinary, reviewable artifacts: Python transformation files, YAML bundle
  resources, a dashboard JSON, a Genie space JSON — nothing opaque, nothing that bypasses
  normal code review.
- Tie back to Section 2 (Best Practices): curation (`skillOverrides`), manual vs.
  auto-trigger control, and scope discipline (project vs. global) are what make this
  workflow trustworthy enough to actually adopt on a real team, not just a cute demo.
- Point at the repo (or the tagged reference branch) as something they can clone and run
  themselves against their own `samples.wanderbricks` data today — no bespoke setup
  required beyond `databricks aitools install`.
