# Development status and roadmap

> Living handoff for maintainers and future agent sessions. Update this file at every clean checkpoint that changes status, evidence, review scope, or next action. Git and this document are durable state; chat history and local TODOs are not.

## Snapshot

Status as of 2026-07-27:

- **Repository:** `jerrylin96/dotgemini` (remote reports canonical location `https://github.com/jerrylin96/dotgemini.git`)
- **Base branch:** `main`
- **Base SHA:** `bb4b540995ecef65f2be2752c001b5345850fa38`
- **Feature branch:** `agent/port-principled-dev`
- **Latest implementation SHA:** `7962ff504f36aa7e3edd18007384f28a57620969`
- **Latest implementation tree:** `72849fa3862060c5b2267efee1a11b2da02ea944`
- **Durable feature worktree:** discover with `git worktree list`; current branch is `agent/port-principled-dev`
- **Publication:** feature branch is pushed; no PR or standalone repository has been created
- **Release posture:** alpha candidate; automated implementation is mature enough for bounded final review and disposable dogfood

The status-document commit that contains this file will supersede the SHA above as branch tip. It is documentation-only. Final exact-SHA review must target the new tip while treating `7962ff5` as the implementation boundary.

## What exists

The `principled-dev/` subtree is a self-contained, model-neutral goose port containing:

- eleven Agent Skills;
- recipe entry points for `make-feature`, `adversarial-review`, `explain-diff`, and `signoff`;
- an Open Plugin manifest and `PreToolUse` policy hook;
- persistent, digest-bound specification, plan, build, review, publication, and signoff state;
- attached durable feature worktrees and detached disposable review worktrees;
- branch, commit, range, PR, and MR resolution to immutable SHAs;
- independent review records with blocking severity contracts;
- exact-approved-SHA publication with remote verification and structured partial-success reporting;
- report-only signoff bound to approved review, persisted publication, local Git state, and live remote state;
- resumable CLI operations, installation guidance, capability parity, and known limitations;
- unit, integration, concurrency, packaging, policy, and local bare-remote end-to-end tests.

See:

- [Capability parity](capability-parity.md)
- [Known limitations](known-limitations.md)
- [Global installation](installation.md)
- [Project-local installation](project-local.md)

## Evidence at implementation boundary

Evidence recorded for `7962ff504f36aa7e3edd18007384f28a57620969` in an environment with the `goose` CLI on `PATH`:

```text
default pytest: 235 passed
Ruff: All checks passed
Goose recipe validation: 4 valid
feature worktree: clean
remote feature branch: exact SHA match
```

Two packaging integration tests require the `goose` CLI. They run when it is available and skip with reason `requires goose CLI` when it is absent; a skip in a goose-less environment is not a regression.

Earlier isolated packaging validation also proved:

- Open Plugin installation from a local Git source succeeds;
- all eleven namespaced skills are discovered;
- hooks and helper scripts survive installation;
- a separate recipe library discovers all four recipes;
- the subtree can be exported into a clean standalone Git repository.

Do not reinterpret historical evidence as validation of a later implementation change. Documentation-only changes may reuse implementation evidence after checking that no runtime/test files changed, but final review remains bound to exact branch tip.

## Review history and current exit gate

Review was intentionally adversarial and found material issues in early iterations, including:

- shell-policy overclaims and direct refspec gaps;
- signoff acceptance of unapproved or stale review/publication state;
- CLI signoff checking the wrong checkout;
- stale artifact and publication metadata;
- concurrent state lost-update and race windows;
- hidden remote partial-success outcomes;
- plugin tests omitted from default CI collection;
- reentrant/forked lock handling;
- credential-bearing remote leakage.

Each finding was reproduced, fixed with tests, validated, committed, and pushed. Later rounds increasingly focused on rare failure modes rather than ordinary supported workflows. The last reviewed implementation predecessor was `70338f8`; `7962ff5` contains only the raw-`os.fork()` child-context cleanup fix and its regression test. No known finding remains open, but `7962ff5` has not received a fresh independent `APPROVE` verdict.

### Bounded final-review policy

The next session must run **one** final independent review against the exact new branch tip.

- Review implementation delta `70338f8..7962ff5` and confirm this document is accurate.
- Maximum reviewer budget: 20 turns.
- No nested delegation.
- Read-only detached worktree.
- Run default pytest, Ruff, and recipe validation.
- Only `CRITICAL` or `IMPORTANT` defects affecting realistic supported workflows block.
- Record exotic residuals as known limitations unless they threaten data integrity, credential safety, destructive operations, or lifecycle gate correctness.
- If no material blocker exists, return `APPROVE` and stop.
- Do not automatically begin another fix/re-review loop. Present any blocking finding to the human and request a decision.

This stopping rule prevents review from becoming an unbounded search for increasingly theoretical edge cases.

## Remaining release gates

### 1. Final exact-SHA review

Create a fresh detached worktree at current remote feature tip and apply the bounded policy above. Record base, commit, tree, validation output, unverified checks, and verdict.

### 2. Disposable Goose dogfood

Requires separate human approval. In a disposable repository, exercise:

1. `/make-feature` from a real goose session;
2. separate human specification and plan approvals;
3. attached feature-worktree creation without primary-checkout mutation;
4. behavioral RED/GREEN implementation;
5. detached independent review, one deliberate finding, builder repair, and fresh approval;
6. `/explain-diff` interactive navigation;
7. exact-SHA push to a local or disposable remote;
8. human review acknowledgement and `/signoff`;
9. simulated human merge and safe cleanup.

Treat model behavior, slash-command registration, live hook invocation, subagent availability, and resume ergonomics as dogfood questions. Automated tests cannot prove them.

### 3. Standalone extraction

Requires dogfood success and separate approval.

- Extract only `principled-dev/` into a blank repository with a clean, comprehensible history.
- Run default tests, Ruff, recipe validation, isolated plugin installation, skill discovery, and local end-to-end lifecycle from extracted repository.
- Choose final repository name and release/version policy.
- Publish after human review.

### 4. Deprecation decision

Do not deprecate `dotgemini` until the standalone goose package has been used successfully in real work. Deprecation is a separate human decision and should retain migration and rollback instructions.

## Operating lessons

### Durable checkpoints are mandatory

Agent work was interrupted by network loss, computer sleep/lock, tool transport failures, and session boundaries. Recovery succeeded because work lived in an isolated Git worktree and clean checkpoints were pushed.

For future work:

- never rely on chat history as sole state;
- update this file at milestone boundaries;
- commit after each coherent, validated slice;
- push after each clean milestone that should survive machine/session loss;
- record exact local/remote SHA, validation evidence, open findings, and next action;
- keep primary checkout untouched;
- avoid leaving valuable work only in uncommitted files or disposable review worktrees.

Routine pushing applies only to feature branches. It never authorizes agent-created PRs or integration-branch mutation.

### Review needs a budget and exit criteria

Early review rounds found important correctness and safety defects. Continued rounds eventually produced diminishing returns and quota pressure. Future workflows should set before review:

- supported platforms and realistic threat/failure model;
- blocking severity definitions;
- maximum review/fix cycles;
- reviewer turn/token budget;
- a stopping rule;
- human approval requirement for expanding scope.

Recommended default:

```text
Per implementation slice:
  up to 2 efficient-model review/fix loops

Integrated feature:
  1 strong-model final review

Block only:
  CRITICAL/IMPORTANT findings affecting supported realistic workflows
  or any issue threatening data integrity, credentials, destructive safety,
  or lifecycle-gate correctness

Beyond budget:
  record as known limitation/backlog and ask human before continuing
```

### Exact-SHA review and documentation checkpoints

Review verdicts bind to exact commits. Every fix or documentation commit creates a new tip. Avoid claiming an old verdict covers a new SHA. For documentation-only checkpoints, final review may focus on code delta since last implementation review plus documentation accuracy, but must still name the exact reviewed tip.

### Partial external success must be explicit

Network and state operations are not one transaction. When remote push succeeds but local state persistence fails, report structured partial success with remote alias, branch, intended/observed SHA, phase, and sanitized cause. Recovery requires fresh reconciliation, not blind retry.

## Multi-model orchestration roadmap

This roadmap is future work, not part of current implementation.

### Phase A: strong planner/orchestrator

Reserve strongest model for:

- requirement clarification and assumption surfacing;
- specification and measurable acceptance criteria;
- architecture, risk model, and task partitioning;
- dependency and file-ownership graph;
- reviewer scope and exit criteria;
- final integration and release-gate validation.

Strong model should avoid routine edits when a cheaper model can execute a bounded slice safely.

### Phase B: efficient implementation workers

Assign small, non-overlapping slices to cheaper/faster models in separate worktrees or strict file partitions. Each worker returns:

- exact files changed;
- observed RED and GREEN evidence;
- focused validation output;
- commit SHA;
- assumptions, shortcuts, and unresolved risks.

Workers must not coordinate through shared uncommitted files.

### Phase C: efficient first-pass reviewers

Use a different efficient model to review each slice before integration:

- exact commit/range only;
- focused acceptance criteria and regression tests;
- material correctness, security, and destructive-operation findings;
- maximum two review/fix cycles;
- no self-repair by reviewer.

### Phase D: strong final reviewer

Strongest model performs one cross-slice review after integration:

- approved specification and plan coverage;
- cross-component interactions;
- exact-SHA and state-transition correctness;
- end-to-end evidence;
- remaining material risk;
- final `APPROVE`, `REQUEST_CHANGES`, or `BLOCKED` verdict.

It should not restart an unbounded edge-case search after budget exhaustion.

### Phase E: human ownership

Human reviews evidence and diff, accepts risks through signoff, creates PR, and merges. Agent never treats model agreement as human authorization.

### Orchestration controls to add later

- model routing policy by phase, risk, and cost;
- per-worker worktree/file ownership;
- max turns, tokens, elapsed time, and retries;
- machine-readable task and review manifests;
- milestone checkpoint commit/push automation;
- interruption recovery from repository state;
- heartbeat/progress records for parallel workers;
- stale-agent detection and cancellation;
- conflict reconciliation by orchestrator;
- cost and review-depth telemetry;
- escalation from efficient to strong model only on ambiguity, failed validation, or material risk.

## Parallel-session coordination

Until orchestration support exists:

- one writing agent per branch/worktree;
- never run concurrent writers in the same worktree;
- partition files explicitly before parallel work;
- reviewers use detached read-only worktrees;
- every session reads this file and verifies Git state before acting;
- update status and push before handing work to another session;
- if observed Git state differs from this file, stop and reconcile rather than guessing.

## Next-session runbook

Use this as the canonical kickoff; no chat transcript is required.

```text
Continue principled-dev goose port from Git state.

Repository primary checkout:
  Resolve with `git worktree list` as the checkout attached to `main`.
  It must remain on main and unmodified.

Durable feature worktree:
  Resolve with `git worktree list` as the checkout attached to the feature branch.

Feature branch:
  agent/port-principled-dev

Authoritative status:
  principled-dev/docs/development-status.md at current remote branch tip

First actions:
1. Read principled-dev/docs/development-status.md.
2. Verify primary checkout is clean/on main.
3. Verify feature worktree is clean and local HEAD equals
   origin/agent/port-principled-dev.
4. Record exact current commit/tree. Do not assume historical SHA in document is
   still branch tip after documentation updates.
5. Create a fresh detached review worktree at current exact tip.

Run one bounded final review:
- base bb4b540995ecef65f2be2752c001b5345850fa38;
- implementation boundary 7962ff504f36aa7e3edd18007384f28a57620969;
- inspect 70338f8..7962ff5 for latest code fix and later docs for accuracy;
- max 20 reviewer turns, read-only, no nested delegation;
- run default pytest and Ruff; two packaging tests require `goose` on `PATH` and skip when it is absent;
- run four recipe validations when `goose` is available, otherwise record them as unverified;
- only material supported-workflow CRITICAL/IMPORTANT findings block;
- exotic residuals become known limitations;
- if no material blocker, APPROVE and stop;
- if REQUEST_CHANGES, report to human and ask before another fix loop.

After APPROVE:
- present report and exact SHA;
- request separate approval for one disposable real-goose dogfood run;
- do not install globally, create PR, merge, extract standalone repository,
  deprecate dotgemini, or mutate main without explicit approval.
```

## Maintenance checklist

At every future milestone, update:

- branch, base, latest exact commit and tree;
- implementation boundary if runtime code changed;
- local/remote freshness;
- validation counts and commands;
- review verdict and reviewed SHA;
- known open findings and owner;
- current active phase and next action;
- worktree/session ownership for parallel work;
- publication, dogfood, extraction, and deprecation status.
