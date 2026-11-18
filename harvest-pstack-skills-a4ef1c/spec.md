# Feature Spec: Harvest Essential `pstack` Skills with Zero-Dormancy Wiring

* **State transitions:** `N/A — markdown rules, skill definitions, and static pytest assertions only; no async, concurrent, retry, or stateful runtime flows.`

## 1. Objectives
Harvest the 5 highest-signal practices from `cursor/plugins` `pstack/skills` into `dotgemini` while eliminating dormancy (passive skills/gates that never fire) and avoiding skill bloat:
1. **`benchmark-checklist`**: Add a standalone performance-verification skill with 3-layer trigger wiring (`AGENTS.md` tripwire, `SKILL.md` imperative trigger description, and `@skill:benchmark-checklist` review gates).
2. **`statechart` (lightweight)**: Enforce an auditable conditional `State transitions:` declaration in every spec (Mermaid `stateDiagram-v2` or transition table for async, concurrent, retry, or lifecycle flows) inside `spec-driven-development` and `adversarial-review` (`spec-review`)—without Java/TLC/`mise`/`statechart.ts` dependencies.
3. **`Downstream Consumer Trace` (from `pstack` `blast-radius`)**: Close the small-diff `grep` blind spot by requiring downstream consumer tracing beyond `grep` and execution-backed safety proof inside `adversarial-review` and `ponytail`. (Named `Downstream Consumer Trace` to avoid colliding with `blast radius` in `codebase-audit` and `git-signoff`.)
4. **`unslop`**: Add an anti-AI-tell editing tier (`--unslop`) inside `prose-editor` for external docs, papers, and PR descriptions, wired to `make-feature` Step 7c and `adversarial-review` Writing Quality, with explicit precedence separating external prose from `caveman` chat style.
5. **`Encode Lessons in Structure`**: Fold a 1-bullet structural-encoding heuristic into `AGENTS.md` `## 1. Ponytail` → `### Key Rules` to curb prompt/rule bloat from recurring corrections.

## 2. Scope & Target Files
All edits occur inside the isolated worktree (`gemini/harvest-pstack-skills-a4ef1c`), organized into 3 thin slices:

### Slice 1: `benchmark-checklist` + 3-Layer Trigger Wiring
* `skills/benchmark-checklist/SKILL.md` (new, compact ~60 lines):
  * Frontmatter: `name: benchmark-checklist`, imperative `description` (`CRITICAL RULE: You MUST read and follow this skill whenever reporting or comparing performance numbers, speedups, latency, throughput, profiling, or perf regressions for a changeset...`). MUST NOT include `disable-model-invocation: true`.
  * Scope & exemption: applies to **claims about this changeset's behavior** (not general prose merely mentioning `latency` or `throughput`). If user supplies calibrated measurements with stated methodology (hardware, run count, limiter), verify limits/tuning/reproducibility instead of re-benchmarking.
  * Content: Ballpark vs. full benchmark rule, pre-run setup (claim sentence, measurement script check, `uptime` / core count), compact 7-question table (`Why not double?`, `Was it tuned?`, `Did it break limits?`, `Did it error?`, `Does it reproduce?`, `Does it matter?`, `Did it even happen?`), and `Report` / `inconclusive` verdict rules.
* `AGENTS.md` (edit `AGENTS.md` directly; preserve `GEMINI.md -> AGENTS.md` symlink; do NOT introduce any non-canonical `scratchpad.md` path variants):
  * Under `## 3. Slash Commands & Lifecycle Discipline` → `### Core Operating Behaviors` (`Empirical Grounding`): add 1-line tripwire forbidding reporting any speedup, latency/throughput claim, or benchmark comparison for a changeset without invoking `benchmark-checklist`.
  * Under `## 4. Discoverable Global Skills`: register `[benchmark-checklist/SKILL.md](skills/benchmark-checklist/SKILL.md)`.
* `skills/adversarial-review/SKILL.md` (§5 Perform Adversarial Review) & `skills/code-review-and-quality/SKILL.md` (`### 5. Performance`):
  * Link single source of truth via `@skill:benchmark-checklist` + concise 3-bullet digest (limiter named, tuned prod settings, ≥5 alternating runs or explicit ballpark disclosure); reject uncalibrated perf claims.

### Slice 2: Auditable `statechart` Gate + `Downstream Consumer Trace`
* `skills/spec-driven-development/SKILL.md` (`### 2. Draft the Spec`):
  * Mandate a machine-checkable declaration in every spec: `State transitions: <Mermaid stateDiagram-v2 | transition table | N/A — <reason>>`.
  * Define concrete triggers: *background tasks, retry/backoff loops, connection pools, caches, job/stream lifecycles, cancellation/teardown ordering, or any `await`/thread ordering that outlives one call*.
  * Tie-break rule: **ambiguity resolves toward inclusion** (if a reviewer could ask "what happens if it times out or cancels mid-way?", the diagram/table is required).
* `skills/adversarial-review/SKILL.md`:
  * In `spec-review` Checklist: audit that the `State transitions:` declaration is present and plausible, any `N/A` reason is justified, and illegal/timeout/error transitions are covered before `APPROVE`.
  * In §5 Perform Adversarial Review (`Worktree Code Review Path`): add `Downstream Consumer Trace` check—look beyond `grep` (library source/pinned versions, serialization/wire formats, config/feature flags, teardown/microtask order, 3-hop callers); identify the single safety fact and prove it via real execution (or mark `unproven`).
* `skills/ponytail/SKILL.md`:
  * Under root-cause bug fix guidance: reinforce `Downstream Consumer Trace` (trace indirect config/serialization/dynamic-dispatch consumers and prove safety via execution rather than `grep` alone).

### Slice 3: `--unslop` Prose Pass + `AGENTS.md` Structural Rule
* `skills/prose-editor/SKILL.md`:
  * Under `## Core Principles`: add explicit precedence line: **`--unslop` governs the edited external document/PR text; `caveman` governs agent chat and rationales; neither applies to the other's surface.**
  * Under `## Command Triggers` and `## Editing Tiers`: add `--unslop` mode incorporating `unslop` rules (AI vocabulary, superficial `-ing` clauses, vague attributions, "Not just X, but Y", rule-of-three, synonym cycling, false ranges, em-dash/mid-sentence colon/inline-header tells, abstract metaphor nouns, mechanism-over-feeling, active voice, plain words, and no over-compressed fragments in external prose/PRs).
  * **Parser Constraint (Verbatim):** Any example card header in the new `--unslop` section MUST live inside a closed fenced block and use the exact backticked schema (`### Suggestion #1 \`[Clarity]\` \`[Minor]\``), and every fence MUST be closed; otherwise `test_parse_real_skill_md_without_crash` (`skills/prose-editor/tests/test_prose_editor.py`) fails. Preserve all existing required headings and enum values.
* `skills/make-feature/SKILL.md` (Step 7c) & `skills/adversarial-review/SKILL.md` (§5 `Writing Quality`):
  * Wire `--unslop` via `@skill:prose-editor`: apply `--unslop` rules when drafting external-facing PR descriptions/comments or `review_report_<feature>.md` summaries, keeping chat terse.
* `AGENTS.md` (`## 1. Ponytail` → `### Key Rules` only):
  * Add 1 concise bullet: **Encode lessons in structure:** when the same correction recurs 2+ times, encode the constraint in a linter, type, runtime assertion, or test instead of adding more prompt text.

## 3. Boundaries & Non-Goals
* **No skill sprawl:** Do NOT create standalone skills for `Downstream Consumer Trace` (`blast-radius`), `statechart`, `unslop`, or `Encode Lessons in Structure`.
* **No heavy external toolchain:** Do NOT port `scripts/statechart.ts`, Java, TLC, `mise`, or Pele renderer.
* **No `file://` links in `skills/`:** Must satisfy `scripts/tests/test_skill_references.py`.
* **Preserve `caveman` chat style:** `--unslop` applies only to external prose/docs/PRs, never overriding `caveman` in chat.
* **Preserve `GEMINI.md` symlink:** Never replace `GEMINI.md` with a regular file; edit `AGENTS.md`.
* **Zero test duplication:** Do NOT duplicate existing `name`, `file://`, or `GEMINI.md` symlink assertions already covered in `scripts/tests/test_skill_references.py`.

## 4. Testing Strategy (Enumerated RED Assertions)
1. `scripts/tests/test_skill_references.py`:
   * Extend `test_all_skills_have_correct_frontmatter_name` (or add `test_no_skill_disables_model_invocation` in the same file) to assert NO `skills/*/SKILL.md` frontmatter contains `disable-model-invocation: true` (structural global guard).
2. `scripts/tests/test_pstack_harvest.py` (novel assertions only; every assertion fails RED on unmodified `origin/main` and maps to one wiring risk):
   * `test_benchmark_checklist_frontmatter_and_rules`: asserts `CRITICAL RULE:` + changeset-claim scope + trigger keywords (`benchmark`, `latency`, `throughput`, `speedup`) in `skills/benchmark-checklist/SKILL.md` frontmatter, all 7 checklist questions, `inconclusive` verdict rule, and user-supplied-methodology path.
   * `test_agents_md_tripwires`: asserts `benchmark-checklist` empirical grounding tripwire, `Discoverable Global Skills` registration, and `Encode lessons in structure` rule in `AGENTS.md` `## 1. Ponytail` → `### Key Rules`.
   * `test_statechart_gate_is_auditable`: asserts `State transitions:` declaration format, concrete lifecycle/async triggers, and ambiguity-resolves-to-inclusion rule in `skills/spec-driven-development/SKILL.md`, plus `State transitions:` audit check in `skills/adversarial-review/SKILL.md` `spec-review` Checklist.
   * `test_downstream_consumer_trace_and_perf_gates`: asserts `Downstream Consumer Trace` (beyond `grep` + execution proof/`unproven`) in `skills/adversarial-review/SKILL.md` and `skills/ponytail/SKILL.md`, plus `@skill:benchmark-checklist` cross-reference in `skills/adversarial-review/SKILL.md` and `skills/code-review-and-quality/SKILL.md`.
   * `test_unslop_tier_precedence_and_wiring`: asserts `--unslop` trigger/tier, `unslop` vs. `caveman` precedence line in `skills/prose-editor/SKILL.md`, and `@skill:prose-editor` / `--unslop` external-prose pointer in `skills/make-feature/SKILL.md` Step 7c and `skills/adversarial-review/SKILL.md`.
3. Regression gates:
   * `python3 ~/.gemini/scripts/run_in_env.py <worktree_path> pytest` (including `test_parse_real_skill_md_without_crash`, `test_skill_references.py`, `test_primary_docs.py`, `test_repo_configuration.py`, and all existing tests) + `ruff check .`.
