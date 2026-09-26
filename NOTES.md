# AVE Pipeline Experimental Setup — Progress Notes

This file tracks execution progress against the procedure defined in
Chapter Three (3.5 Procedure) of the dissertation. It exists so progress
is legible from the repo alone, independent of any chat history.

## Overall Roadmap

### Step 0 — Environment & Pre-Flight Checks
Confirm the testbed is ready before any trial runs.

- [x] 0.1 — OpenSandbox container setup (Docker runtime, forked repo,
      Gemini CLI running inside sandbox) — COMPLETED on 2026-08-09
- [ ] 0.2 — Gemini CLI + backend model configuration finalized
      (model pinned: gemini-3.5-flash — done as part of 0.1 work, formal
      0.2 confirmation still pending)
- [ ] 0.3 — UnifiedSkillParser + reused SKILLJECT components load the
      real skill pool without errors
- [ ] 0.4 — Selection-observation harness built and validated (logs
      which skill is invoked per task, tested on trivial case first)
      NOTE: GEMINI_CLI_TRUST_WORKSPACE bypass belongs here, not in 0.1 —
      see "Deferred" section below
- [ ] 0.5 — Task set finalized and labeled (related/adjacent/unrelated
      per target skill), frozen as versioned file (e.g. tasks_v1.json)
- [ ] 0.6 — Config manifest written (model version, container image hash,
      skill pool version, task set version, harness version) — values
      confirmed so far listed below

### Step 1 — Baseline Measurement (per target skill)
Run each skill's original description against full task set + decoys.
Not started.

### Step 2 — Initial Adversarial Generation
Attack Agent produces first rewritten description per target skill.
Not started.

### Step 3 — Trial Execution with Rewritten Description
Not started.

### Step 4 — Outcome Evaluation (SSR per category per iteration)
Not started.

### Step 5 — Refinement Loop (repeat Steps 3–5 until stopping rule met)
Stopping rule: [NOT YET DECIDED — must be fixed before Step 2 begins,
and must match what Chapter Three states]

### Step 6 — Repeat Steps 1–5 Across All Target Skills
Not started.

### Step 7 — Data Consolidation Checkpoint
Not started.

---

## Step 0.1 Detail — OpenSandbox Environment Setup

- [x] Forked OpenSandbox to personal GitHub, cloned locally, tagged
      starting commit as `baseline-v1`
- [x] Fixed Docker permissions (added user to docker group)
- [x] Confirmed OpenSandbox server starts cleanly with Docker runtime
      (OPENSANDBOX_INSECURE_SERVER=YES for local-only insecure mode —
      fine for localhost, revisit if server is ever exposed beyond
      localhost)
- [x] Ran examples/gemini-cli/ vanilla example successfully inside sandbox
- [x] Chose backend model: gemini-3.5-flash (Stable, agentic/coding-tuned,
      not Preview — avoids mid-study model drift risk)
- [x] Pinned @google/gemini-cli to exact version 0.54.4 in main.py
      (was floating on @latest)
      commit: "Pin @google/gemini-cli to 0.54.4 for experimental
      reproducibility"
- [x] Configured egress restrictions: deny-by-default NetworkPolicy,
      allow-list = registry.npmjs.org, *.npmjs.org,
      generativelanguage.googleapis.com
      Enforcement mode confirmed as dns+nft (firewall-level, not just DNS
      filtering — DNS-only filtering is bypassable via hardcoded-IP
      connections)
      Verified both directions: npm install + Gemini API succeed; curl to
      example.com fails (exit code 6)
      commit: "Add deny-by-default egress policy, allowing only npm
      registry and Gemini API"
- [x] Verify Sandbox.create() produces genuinely independent, stateless
      containers per call (no pooling/reuse) — verified via sequential 5-run
      marker file test script on 2026-08-09
- [x] Confirm clean teardown — no orphaned containers/volumes after
      destroy, checked via `docker ps -a` on 2026-08-09 (all test containers
      cleanly removed)
- [ ] Decide: pre-bake Gemini CLI into a custom sandbox image instead of
      installing live via npm at trial runtime? (currently installs live
      each run — fine for proof-of-concept, worth revisiting for
      trial-volume efficiency later, not urgent now)

---

## Step 0.2 Detail — Gemini CLI & Model Configuration

- [x] Generated new API key from GCP project "MSc-work", linked to active billing account, and confirmed paid tier access (header trace verified standard service tier) on 2026-08-21.
- [x] Confirmed configuration precedence order: CLI flags > env vars > system/project/user/system-defaults settings files > defaults. Our setup uses only env vars (GEMINI_MODEL, GEMINI_API_KEY), no settings files exist in the base container image, and we pass no CLI flags in our run invocations. Env vars are confirmed to govern trial behavior with no risk of silent override.
- [x] Temperature/sampling decision: kept at API default (temperature=1.0, topP=0.95), NOT pinned to 0
  - Rationale: SSR is a rate metric; deterministic selection (temp=0) would not reflect realistic agent behavior and would misrepresent what SSR measures
  - Repeats per condition: 10, to produce a statistically meaningful rate per condition
  - Flag: this decision must be explicitly stated in Chapter Three's methodology (temperature setting + repeats-per-condition + rationale) — not yet written there as of this note

---

## Deferred Decisions

### GEMINI_CLI_TRUST_WORKSPACE
Not yet applied to main.py or any harness code. Required only when
running Gemini CLI non-interactively as part of the actual experimental
trial harness (Step 0.4 — selection-observation harness), not for this
proof-of-concept stage (0.1).

When applied, this must be a standalone, deliberately justified commit —
not bundled with unrelated changes. Justification: trials run inside
ephemeral, network-egress-restricted OpenSandbox containers, so the
"trusted directory" check protects against a threat model (a developer's
real machine) that doesn't apply here.

Note: this variable has been proposed and rejected twice already during
0.1 setup (once via env dict, once via inline shell export) as part of
unrelated changes — watch for it resurfacing again in future diffs.

### Refinement loop stopping rule (Step 5)
Not yet fixed. Must decide: max iteration count, SSR plateau threshold,
or SSR target reached — and this must match what Chapter Three's
methodology states, not be decided ad hoc mid-experiment.

---

## Config Manifest Values Confirmed So Far (for Step 0.6)
GEMINI_MODEL=gemini-3.5-flash
gemini-cli version=0.54.4
SANDBOX_IMAGE=opensandbox/code-interpreter:v1.1.0
egress mode=dns+nft
task set version=[not yet frozen]
skill pool version=[not yet frozen]
harness version=[not yet built]
