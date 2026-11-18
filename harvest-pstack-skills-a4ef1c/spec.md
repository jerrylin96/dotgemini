# Feature Spec: Harvest Essential `pstack` Skills with Zero-Dormancy Wiring

## 1. Objectives
Harvest the 5 highest-signal practices from `cursor/plugins` `pstack/skills` into `dotgemini` while eliminating dormancy (passive skills that never trigger) and avoiding skill bloat:
1. **`benchmark-checklist`**: Add a standalone performance-verification skill with 3-layer automatic trigger wiring (`AGENTS.md` always-on tripwire, `SKILL.md` imperative trigger description, and code-review gates).
2. **`statechart` (lightweight)**: Enforce a conditional pre-code state-transition check (Mermaid `stateDiagram-v2` or transition table) for async, concurrent, retry, or lifecycle specs inside existing spec/review gates—without Java/TLC/`mise`/`statechart.ts` dependencies.
3. **`blast-radius`**: Close the small-diff `grep` blind spot by requiring downstream consumer tracing (beyond `grep`) and execution-backed safety proof inside `adversarial-review` and `ponytail`.
4. **`unslop`**: Add an anti-AI-tell editing pass (`--unslop`) inside `prose-editor` for external docs, papers, and PR descriptions without altering `caveman` chat style.
5. **`encode-lessons-in-structure`**: Add a 2-line structural-encoding heuristic to `AGENTS.md` to prevent prompt/rule bloat from recurring corrections.

## 2. Scope & Target Files
All edits occur inside the isolated worktree (`gemini/harvest-pstack-skills-a4ef1c`):
* `skills/benchmark-checklist/SKILL.md` (new):
  * Frontmatter: `name: benchmark-checklist`, imperative `description` (`CRITICAL RULE: You MUST read and follow this skill whenever...` with triggers: `benchmark`, `latency`, `throughput`, `speedup`, `profiling`, `faster`, `perf regression`, `A/B timing`). MUST NOT include `disable-model-invocation: true`.
  * Content: Ballpark vs. full benchmark rule, pre-run setup (claim, script inspection, `uptime` / core count), all 7 verification questions (`Why not double?`, `Was it tuned?`, `Did it break limits?`, `Did it error?`, `Does it reproduce?`, `Does it matter?`, `Did it even happen?`), and strict `Report` / `inconclusive` verdict rules.
* `AGENTS.md` (edit directly; preserve `GEMINI.md -> AGENTS.md` symlink):
  * Under `## 3. Slash Commands & Lifecycle Discipline` → `### Core Operating Behaviors` (`Empirical Grounding`): add 1-line tripwire forbidding reporting any speedup, latency/throughput claim, or benchmark comparison without invoking `benchmark-checklist`.
  * Under `### Core Operating Behaviors` (or `## 1. Ponytail`): add 2-line `Encode Lessons in Structure` rule (when same correction recurs 2+ times, encode constraint in a linter, type, runtime assertion, or test instead of adding more prompt text).
  * Under `## 4. Discoverable Global Skills`: register `[benchmark-checklist/SKILL.md](skills/benchmark-checklist/SKILL.md)`.
* `skills/spec-driven-development/SKILL.md`:
  * Under `### 2. Draft the Spec`: add conditional rule requiring a Mermaid `stateDiagram-v2` or state-transition table covering illegal, timeout, and error transitions whenever the spec modifies async, concurrent, retry, or stateful lifecycle flows.
* `skills/adversarial-review/SKILL.md`:
  * In `spec-review` Checklist: enforce the conditional state-transition completeness check on async/concurrent/retry/stateful specs before `APPROVE`.
  * In `Worktree Code Review Path` / `Execution Steps` (§5 Perform Adversarial Review):
    * Add `Blast-Radius Check (Small & Medium Diffs)`: look beyond `grep` (library source/pinned versions, serialization/wire formats, config/feature flags, teardown/microtask ordering, 3-hop callers); identify the single safety fact and verify via execution (test/script) or mark `unproven`.
    * Add `Performance Claims Check`: reject uncalibrated speedup/latency/throughput claims lacking `benchmark-checklist` evidence (limiter, tuned prod settings, ≥5 alternating runs or explicit single-run ballpark disclosure).
* `skills/code-review-and-quality/SKILL.md`:
  * Under `### 5. Performance`: add `benchmark-checklist` verification gate for any claimed optimization or benchmark delta.
* `skills/ponytail/SKILL.md`:
  * Under root-cause bug fix guidance: reinforce checking indirect downstream consumers (config, serialization, dynamic dispatch) and verifying via execution rather than `grep` alone.
* `skills/prose-editor/SKILL.md`:
  * Under `## Command Triggers` and `## Editing Tiers`: add `--unslop` mode / checklist incorporating `unslop` rules (AI vocabulary, superficial `-ing` clauses, vague attributions, "Not just X, but Y", rule-of-three, synonym cycling, false ranges, em-dash/mid-sentence colon/inline-header tells, abstract metaphor nouns, mechanism-over-feeling, active voice, plain words, and no over-compressed fragments in external prose/PRs). Preserve all existing required headings, suggestion card schema, and `validator.py` compatibility.
* `scripts/tests/test_pstack_harvest.py` (new):
  * Automated verification of frontmatter, trigger wiring, no `disable-model-invocation: true`, no `file://` links, `GEMINI.md` symlink integrity, and `prose-editor` schema/heading compatibility.

## 3. Boundaries & Non-Goals
* **No skill sprawl:** Do NOT create standalone skills for `blast-radius`, `statechart`, `unslop`, or `principle-encode-lessons-in-structure`.
* **No heavy external toolchain:** Do NOT port `scripts/statechart.ts`, Java, TLC, `mise`, or Pele renderer.
* **No `file://` links in `skills/`:** Must satisfy `scripts/tests/test_skill_references.py`.
* **Preserve `caveman` chat style:** `--unslop` applies only when editing external prose/docs/PRs via `prose-editor`, never overriding `caveman` in chat.
* **Preserve `GEMINI.md` symlink:** Never replace `GEMINI.md` with a regular file; edit `AGENTS.md`.

## 4. Testing Strategy
* Run `python3 ~/.gemini/scripts/setup_review_env.py <worktree_path>` (if env not yet initialized) and `python3 ~/.gemini/scripts/run_in_env.py <worktree_path> pytest` + `ruff check .`.
* RED tests in `scripts/tests/test_pstack_harvest.py` fail against unmodified `origin/main` before implementation, then pass 100% post-implementation alongside the existing test suite (`test_skill_references.py`, `test_primary_docs.py`, `test_prose_editor.py`, `test_repo_configuration.py`, etc.).
