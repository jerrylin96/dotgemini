# Implementation Plan: Harvest Essential `pstack` Skills with Zero-Dormancy Wiring

* **State transitions:** `N/A — static markdown skills/rules and pytest assertions only; no async, concurrent, retry, or stateful runtime flows.`
* **Execution Strategy:** Standard `/make-feature` Phase 2 TDD (single RED test suite commit/push at Step 4d covering all 3 implementation slices, followed by sequential Slice 1 → Slice 2 → Slice 3 GREEN implementation at Step 4e and full regression + `ruff` verification).

---

## Pre-Flight: Worktree Test Environment
* **Verify Command (env init):**
  ```bash
  python3 ~/.gemini/scripts/setup_review_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_harvest-pstack-skills-a4ef1c
  ```

---

## Task 0 (Permanent Structural Guard — GREEN Regression Guard)
* **Target File:** `scripts/tests/test_skill_references.py` (near `test_all_skills_have_correct_frontmatter_name`, line 97)
* **Classification (`N2`):** Permanent structural regression guard (passes GREEN on `origin/main` today; prevents future skills from copying `disable-model-invocation: true`). Not counted as a RED test.
* **Implementation:** Add `test_no_skill_disables_model_invocation()` scanning `skills/*/SKILL.md` frontmatter blocks and failing if `disable-model-invocation: true` appears.
* **Verify Command:**
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_harvest-pstack-skills-a4ef1c pytest scripts/tests/test_skill_references.py -q
  ```

---

## Task 1 (RED Test Suite — `scripts/tests/test_pstack_harvest.py`)
Write `scripts/tests/test_pstack_harvest.py` containing ONLY novel, slice-decoupled wiring assertions (no duplication of `name`, `file://`, or `GEMINI.md` symlink tests already in `test_skill_references.py`). All 7 tests MUST fail cleanly (RED) against unmodified `218c002`:
1. `test_benchmark_checklist_frontmatter_and_rules` (Slice 1):
   * Asserts `skills/benchmark-checklist/SKILL.md` exists, frontmatter `description` starts with `CRITICAL RULE:`, scopes to claims about the changeset's behavior, includes trigger keywords (`benchmark`, `latency`, `throughput`, `speedup`, `profiling`, `regression`), and omits `disable-model-invocation: true`.
   * Asserts body contains all 7 verification questions (`Why not double?`, `Was it tuned?`, `Did it break limits?`, `Did it error?`, `Does it reproduce?`, `Does it matter?`, `Did it even happen?`), `inconclusive` verdict rule, and user-supplied-methodology verification path.
2. `test_agents_md_benchmark_wiring` (Slice 1):
   * Asserts `AGENTS.md` contains the `benchmark-checklist` tripwire under `Empirical Grounding` (scoped to changeset claims) and `[benchmark-checklist/SKILL.md](skills/benchmark-checklist/SKILL.md)` under `## 4. Discoverable Global Skills`.
3. `test_benchmark_review_gates` (Slice 1):
   * Asserts `@skill:benchmark-checklist` cross-reference + compact digest in `skills/adversarial-review/SKILL.md` §5 and `skills/code-review-and-quality/SKILL.md` `### 5. Performance`.
4. `test_statechart_gate_is_auditable` (Slice 2):
   * Asserts stable anchors in `skills/spec-driven-development/SKILL.md` (`State transitions:`, lifecycle/async trigger vocabulary such as `retry`, `background`, `cancellation`, `teardown`, ambiguity-resolves-to-inclusion rule, and non-empty `N/A` reason requirement) without locking the full placeholder template (`N3`).
   * Asserts `skills/adversarial-review/SKILL.md` `spec-review` Checklist audits `State transitions:` declaration plausibility, `N/A` justification, and illegal/timeout/error transitions.
5. `test_downstream_consumer_trace_gates` (Slice 2):
   * Asserts `Downstream Consumer Trace` (beyond `grep`, indirect consumers, execution proof / `unproven`) in `skills/adversarial-review/SKILL.md` §5 and `skills/ponytail/SKILL.md`.
6. `test_unslop_tier_precedence_and_wiring` (Slice 3):
   * Asserts `--unslop` in `skills/prose-editor/SKILL.md` (`## Command Triggers` + `## Editing Tiers`), key AI-tell categories (`AI vocabulary`, `Em dash`, `Abstract metaphor nouns`, `Over-compression`), and explicit precedence separating `--unslop` (external docs/PRs) from `caveman` (agent chat/rationales).
   * Asserts `skills/make-feature/SKILL.md` Step 7c and `skills/adversarial-review/SKILL.md` §5 `Writing Quality` reference `[prose-editor](../prose-editor/SKILL.md)` and apply `--unslop` rules inline (`N1`)—not `@skill:prose-editor`.
7. `test_agents_md_encode_lessons_rule` (Slice 3):
   * Asserts `Encode lessons in structure` bullet inside `AGENTS.md` `## 1. Ponytail` → `### Key Rules` (between `### Key Rules` and `## 2. Caveman`).
* **Verify Command (RED gate):**
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_harvest-pstack-skills-a4ef1c pytest scripts/tests/test_pstack_harvest.py -q
  ```
  *(Expected: 7 failed, 0 errors/collection failures.)*

---

## Task 2 (Slice 1 GREEN — `benchmark-checklist` + 3-Layer Trigger Wiring)
* **RED Test Target:** `test_benchmark_checklist_frontmatter_and_rules`, `test_agents_md_benchmark_wiring`, `test_benchmark_review_gates`.
* **GREEN Implementation Targets:**
  1. Create `skills/benchmark-checklist/SKILL.md` (~55–65 lines):
     * Frontmatter: `name: benchmark-checklist`, `description: "CRITICAL RULE: You MUST read and follow this skill whenever reporting or comparing performance numbers, speedups, latency, throughput, profiling, or perf regressions for a changeset (does not fire on unrelated docs merely mentioning perf terms)."` (no `disable-model-invocation`).
     * Sections: Scope & Ballpark/Supplied-Evidence rules (user-supplied calibrated measurements with hardware, run count, limiter → verify limits/tuning/reproducibility, skip re-running), Pre-run hygiene (`uptime`, core count, measurement script check), 7-question compact markdown table, `Report` / `inconclusive` verdict rules.
  2. Edit `AGENTS.md`:
     * Under `### Core Operating Behaviors` → `Empirical Grounding` (`AGENTS.md:92`), add 1-line tripwire: never report a speedup, latency/throughput number, or perf comparison for a changeset without invoking `benchmark-checklist`. (Do NOT introduce non-canonical `scratchpad.md` paths — `I5`.)
     * Under `## 4. Discoverable Global Skills` (`AGENTS.md:113+`), register `[benchmark-checklist/SKILL.md](skills/benchmark-checklist/SKILL.md)`.
  3. Edit `skills/code-review-and-quality/SKILL.md` (`### 5. Performance`, line 48) & `skills/adversarial-review/SKILL.md` (§5 Perform Adversarial Review, line 361):
     * Reference `@skill:benchmark-checklist` as single source of truth + concise 3-bullet digest (limiter named, tuned production settings, ≥5 alternating runs or explicit single-run ballpark disclosure).
* **Verify Command:**
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_harvest-pstack-skills-a4ef1c pytest scripts/tests/test_pstack_harvest.py -k "benchmark" -q && \
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_harvest-pstack-skills-a4ef1c pytest scripts/tests/test_skill_references.py -q
  ```

---

## Task 3 (Slice 2 GREEN — Auditable `statechart` Gate + `Downstream Consumer Trace`)
* **RED Test Target:** `test_statechart_gate_is_auditable`, `test_downstream_consumer_trace_gates`.
* **GREEN Implementation Targets:**
  1. Edit `skills/spec-driven-development/SKILL.md` (`### 2. Draft the Spec`, line 25):
     * Mandate `State transitions:` declaration in every spec (`Mermaid stateDiagram-v2`, transition table, or `N/A — <reason>`).
     * List concrete triggers (`background tasks`, `retry/backoff loops`, `connection pools`, `caches`, `job/stream lifecycles`, `cancellation/teardown ordering`, `await`/thread ordering outliving one call) and tie-break rule (*ambiguity resolves toward inclusion*).
  2. Edit `skills/adversarial-review/SKILL.md`:
     * `spec-review` Checklist (line 47): audit `State transitions:` declaration presence/plausibility, non-empty `N/A` justification, and coverage of illegal/timeout/error transitions before `APPROVE`.
     * §5 Perform Adversarial Review (line 361): add `Downstream Consumer Trace` (Unconditional for code diffs)—inspect beyond `grep` (library source/pinned versions, JSON/DB/wire formats, config/feature flags, teardown/microtask order, 3-hop callers); identify the single safety fact and prove via real execution or mark `unproven`.
  3. Edit `skills/ponytail/SKILL.md` (line 30):
     * Under `**Bug fix = root cause, not symptom.**`: add 2 lines reinforcing `Downstream Consumer Trace` (check indirect config/serialization/dynamic-dispatch consumers beyond `grep` and prove safety by running code).
* **Verify Command:**
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_harvest-pstack-skills-a4ef1c pytest scripts/tests/test_pstack_harvest.py -k "statechart or downstream" -q
  ```

---

## Task 4 (Slice 3 GREEN — `--unslop` Prose Pass + `Encode Lessons in Structure`)
* **RED Test Target:** `test_unslop_tier_precedence_and_wiring`, `test_agents_md_encode_lessons_rule`, plus `skills/prose-editor/tests/test_prose_editor.py`.
* **GREEN Implementation Targets:**
  1. Edit `skills/prose-editor/SKILL.md`:
     * `## Command Triggers` (line 10): add `/edit-prose --unslop [file_path]` / `--unslop` flag.
     * `## Core Principles` (line 22): add explicit precedence rule—*`--unslop` governs the edited external document/PR text; `caveman` governs agent chat and rationales; neither applies to the other's surface.*
     * `## Editing Tiers` (line 26): add `--unslop` tier (composable with `--line-edit` or standalone) containing the compact `unslop` checklist (superficial `-ing` phrases, vague attributions, AI vocab, fancy "is", "Not just X, but Y", rule of three, synonym cycling, false ranges, em-dash/mid-sentence colon/inline-header tells, boldface/title-case/emoji/curly-quote tells, chatbot/sycophantic/filler/generic-conclusion tells, abstract metaphor nouns, mechanism-over-feeling, active voice, strong verbs, plain words, no over-compressed fragments in external prose).
     * **Parser Safety (`B4` / `Guard 1`):** Do **NOT** place any concrete numeric `### Suggestion #<digits> ...` example card header anywhere in `skills/prose-editor/SKILL.md` (neither unfenced nor inside a fenced block): `skills/prose-editor/resources/validator.py:294-306` (`Guard 1`) raises `ValueError` when numeric card headers exist only inside code fences (`test_parse_real_skill_md_without_crash`). Keep `--unslop` as bulleted pattern rules (matching `--proofread`/`--line-edit`/`--developmental`), ensure any example code fences close cleanly (`Guard 2`), and preserve all required headings and `Category`/`Impact` enums.
  2. Edit `skills/make-feature/SKILL.md` (Step 7c, line 255) & `skills/adversarial-review/SKILL.md` (§5 `Writing Quality`, line 362):
     * Reference `[prose-editor](../prose-editor/SKILL.md)` by relative link (`N1`) and instruct applying `--unslop` rules inline when drafting `review_report_<feature>.md` / GitHub PR descriptions and external docs (keeping chat responses terse per `caveman`).
  3. Edit `AGENTS.md` (`## 1. Ponytail` → `### Key Rules`, line 25):
     * Add 1 bullet: **Encode lessons in structure:** when the same correction recurs 2+ times, encode the constraint in a linter, type, runtime assertion, or test instead of adding more prompt text.
* **Verify Command (Full Suite & Linter):**
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_harvest-pstack-skills-a4ef1c pytest && \
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_harvest-pstack-skills-a4ef1c ruff check .
  ```
