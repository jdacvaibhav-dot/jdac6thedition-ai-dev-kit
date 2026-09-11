# Demo Prompts

Presenter crib sheet — the prompts to give the coding agent, in order, for the
live Wanderbricks build.

---

### 1. Install & Configure (~2 min)

Run this yourself in the terminal:

```
databricks aitools install --scope project
```

Then open `.claude/settings.json` (or the plugin's `skillOverrides`) and narrate curating
it to `user-invocable-only` so only project-relevant skills auto-trigger. Mention
`databricks aitools install --skills-only --scope project` as the raw-skills alternative.

### 2. Plan and build the whole thing

Lean on the planning skills instead of a single do-everything prompt.

> Build a solution on the `samples.wanderbricks` schema in my Databricks environment
> that solves the following, and use your writing-plans skill to write a plan for it
> before touching any code:
>
> 1. A Spark Declarative Pipeline that tracks the full history of each booking's
>    status over time.
> 2. Packaging it as a proper Databricks Asset Bundle with `dev` and `prod` targets.
>    `dev` should deploy to my own workspace user namespace. `prod` should run as the
>    `databricks_user_group_job_sp` service principal and refuse to deploy unless the
>    current branch is `main`.
> 3. Granting read access on the resulting schema to a group called
>    `wanderbricks-viewers` such that they can actually query the gold table, with 
>    nothing outside the schema affected.
> 4. An AI/BI dashboard on the gold table with two charts: revenue by destination
>    (current bookings only), and booking status over time.
> 5. A Genie agent over the gold table so someone on the business side could ask
>    natural-language questions about bookings and destinations without writing SQL.

Once the plan is written, hand it off:

> Execute this plan using subagent-driven-development, referencing Databricks skills as needed.

Let the agent genuinely discover the shape of `booking_updates` (diff feed vs. full-row
snapshot) and the right destination-name column on its own while it plans — don't hint
at the answer. The "refuse to deploy unless on `main`" clause is what should land as
the `git: branch: main` guard under `prod`.

### 3. Deploy and run dev

> Deploy the bundle to `dev` and run the pipeline. Show me the events if anything fails,
> and don't stop until it's green.

Then, deliberately, from this branch (not `main`):

> Now try to validate/deploy the `prod` target.

Let the branch-guard failure happen live — call it out as real, not staged. Once `dev`
is green, point at the dashboard's status-over-time chart: "if we'd only kept the
latest status, this would be a flat line." Ask the Genie agent a real question live,
e.g. "which destination had the most bookings last month?"

---