# Reviewer Identification Proof

```text
REVIEWER_ID: arena-6cf52b3e
AUDITED_SHA: 376a978aa58c8fc002f1c0f6cd1f4c31d80a42af
BASE: origin/main @ 1451ee9
REVIEW_ROUND: 1 (spec gate)
FINGERPRINT: pstack-spec-gate-6cf5
SESSION: persistent — same REVIEWER_ID on every future prompt in this tab
```

**VERDICT: NEEDS_REVISION**

Maps to `REJECT` at the internal spec gate (`skills/adversarial-review/SKILL.md:191` allows only `APPROVE`/`REJECT` for `spec-review`) until **B1–B4** are resolved. No re-architecture required: the harvest is correctly scoped, the target anchors all exist, and the repo invariants survive it. The blockers are dormancy holes and one unstated parser invariant, i.e. exactly the failure modes this spec claims to eliminate.

Scope respected: I changed only this file. No other repo file, branch, or peer review was touched.

---

## 0. Empirical baseline (audited, reproducible)

| Probe | Result |
|---|---|
| `git diff --stat origin/main..AUDITED_SHA` | `harvest-pstack-skills-a4ef1c/spec.md` +45, `review_prompt.md` +8 — 2 files, **zero code changed** |
| `pytest -q` | **430 passed, 3 skipped** (host venv + `google-api-python-client`, `google-auth`) |
| `ruff check .` | **All checks passed** |
| Prototype `skills/benchmark-checklist/SKILL.md` with spec §2 frontmatter, then `pytest scripts/tests/test_skill_references.py` | **20 passed** — frontmatter plan is invariant-safe (probe dir deleted, tree clean) |
| `validator.parse_suggestion_cards()` on unslop-shaped text | unfenced `### Suggestion #1 [Clarity] [Minor]` → `ValueError: Malformed suggestion header`; unterminated ` ``` ` → `ValueError: Unterminated code fence` |

Not verified (stated honestly): `python3 ~/.gemini/scripts/run_in_env.py` / `setup_review_env.py` — absent in this sandbox, so tests ran on a host venv with the same pinned `requirements.txt` result. `ruff` version differs from the builder's isolated env.

Verified anchor existence (all present, so §2's edit points are real):

* `AGENTS.md:91` `### Core Operating Behaviors`, `AGENTS.md:109` `## 4. Discoverable Global Skills`, `AGENTS.md:14` `## 1. Ponytail`
* `skills/spec-driven-development/SKILL.md:25` `### 2. Draft the Spec`
* `skills/adversarial-review/SKILL.md:47` `spec-review` Checklist; `:358` §5 Perform Adversarial Review; conditional-check pattern at `:363` (LaTeX) / `:367` (HPC)
* `skills/code-review-and-quality/SKILL.md:48` `### 5. Performance`
* `skills/ponytail/SKILL.md:30` root-cause/grep guidance
* `skills/prose-editor/SKILL.md:10` Command Triggers, `:26` Editing Tiers

---

## 1. Dormancy risk (focus 1)

### B1 — BLOCKING: the statechart gate has no auditable trigger, so it self-exempts to dormancy

Spec §2 asks for a conditional rule: "require a state diagram **whenever** the spec modifies async, concurrent, retry, or stateful lifecycle flows." Nothing defines those terms, and nothing forces the author to record that the conditional was evaluated. An agent writing an async spec can decide "this is a request handler, not a lifecycle flow" and skip silently; a reviewer at `adversarial-review/SKILL.md:47` then has no artifact to audit — it can only check a diagram that may never exist. That is the passive-skill failure mode this feature exists to remove, moved one level up (from "skill never invoked" to "gate never fires").

Required change (one line each, three places):

1. `skills/spec-driven-development/SKILL.md` §2 — mandate a machine-checkable declaration in every spec: `State transitions: <Mermaid stateDiagram-v2 | table | N/A — <reason>>`.
2. Define the trigger with concrete qualifiers, e.g. *background tasks, retry/backoff loops, connection pools, caches, job/stream lifecycles, cancellation and teardown ordering, any `await`/thread ordering that outlives one call*.
3. Tie-break rule: **ambiguity resolves toward inclusion** (if a reviewer could ask "what happens if it times out mid-way?", the diagram is required).
4. `skills/adversarial-review/SKILL.md:47` — reviewer check becomes "declaration present **and** plausible; `N/A` justified; illegal/timeout/error transitions covered". Reviewing the declaration, not the diagram, is what makes the gate non-dormant.

### B2 — BLOCKING: `--unslop` cannot fire for the one artifact it was justified by

§1.4 justifies unslop with "PR descriptions". `prose-editor` is user-invoked only (`SKILL.md:10-14`: `/edit-prose`, `--diff`, `/prose`); no lifecycle phase, and no `AGENTS.md` tripwire, calls it. A flag on a hand-invoked skill for an artifact the agent generates itself is dormant by construction: the agent writing the PR body will never type `--unslop` on itself.

Pick one and write it into the spec (decide, don't leave "or"):

* **(a) Cheapest:** add the unslop checklist reference to the existing external-prose surface the agent already runs — the Phase 3 report / PR body emission in `skills/make-feature/SKILL.md`, phrased as "before publishing external prose, apply `--unslop` rules".
* **(b)** Accept manual-only and delete "PR descriptions" from §1.4 so the claim matches the wiring.

Keeping the claim without either is the one thing not to do.

### B3 — benchmark-checklist wiring is sound; two residual leaks

The three layers are real and reachable, and `CRITICAL RULE:` frontmatter has precedent (`skills/ml-best-practices/SKILL.md:2-13`), so it is not a novel unproven pattern. Two leaks worth 2 lines:

* **Scope creep from trigger words.** 8 keywords including `latency`, `throughput`, `faster` already appear in unrelated repo prose (e.g. `skills/gcp-dataflow/resources/dataflow_metrics_core_job.md`). Without a scope clause the skill fires on documents that merely *mention* latency. Add: applies to **claims about this changeset's behavior**, not to prose discussing performance generally.
* **No exemption path for supplied evidence.** If the user hands over calibrated measurements (hardware, run count, limiter), the checklist should verify method + limits + tuning and skip re-running. Without that, the honest agent over-runs and the lazy one skips the skill. One line: "user-supplied measurements with stated methodology → verify limits/tuning/reproducibility, do not re-benchmark."

The `code-review-and-quality:48` gate is the weakest link (it only fires on `/review`, while the mandatory pipeline uses `adversarial-review` in Phase 3) but `AGENTS.md` + `adversarial-review` cover the real path. Non-blocking.

---

## 2. Repo invariants (focus 2)

| Invariant | Status |
|---|---|
| `GEMINI.md -> AGENTS.md` symlink | **PASS** — intact; already asserted at `scripts/tests/test_skill_references.py:601-611`. Editing `AGENTS.md` cannot break it. |
| `name` frontmatter grammar + dir/name match (`^[a-zA-Z0-9_-]+$`) | **PASS** — enforced by `test_skill_references.py:97`; prototype dir passed 20/20. |
| No `file://` links in `skills/` | **PASS** — enforced at `test_skill_references.py:106`. Use relative links (`../benchmark-checklist/SKILL.md`) if cross-referencing. |
| `prose-editor` required headings + enum sync | **PASS** — required-heading list (`skills/prose-editor/tests/test_prose_editor.py:50-63`) is additively preserved; unslop adds no `Category`/`Impact` enum values, so `test_enum_source_of_truth_sync` (`:65`) stays green. |

### B4 — BLOCKING (missing invariant): prose-editor's parser fails closed on unslop-shaped examples

`test_parse_real_skill_md_without_crash` (`skills/prose-editor/tests/test_prose_editor.py:211`) parses the skill's own `SKILL.md` through the real validator. Two empirically reproduced failure modes apply directly to the planned content:

* `### Suggestion #1 [Clarity] [Minor]` **outside** a fence → `ValueError: Malformed suggestion header` (`resources/validator.py:341` Guard 3 requires backticked enums).
* A before/after block written with an **unterminated** fence → `ValueError: Unterminated code fence`.

Spec §2 says only "preserve `validator.py` compatibility". That is not implementable guidance — state the mechanical constraint:

> Any example card header in the new unslop section MUST live inside a closed fenced block and use the exact backticked schema, and every fence MUST be closed; otherwise `test_parse_real_skill_md_without_crash` fails and the skill's own documentation becomes unparsable.

**I5 — brittlest text invariant, mitigate in advance.** `test_retained_reasoning_and_compaction_rules_exist` (`test_skill_references.py:178`) scans every tracked `.md` for `…/scratchpad.md` references and requires the exact literal `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md`. Spec §2's new `AGENTS.md` prose is safe only if it does not mention `scratchpad.md`, or mentions it canonically. One clause in the plan: "new `AGENTS.md` lines must not introduce `scratchpad.md` path variants."

---

## 3. YAGNI / Ponytail / caveman (focus 3)

### Y1 — the new test file is mostly duplicate coverage

`scripts/tests/test_pstack_harvest.py` is specified to verify frontmatter, `file://`, and the `GEMINI.md` symlink — all three are already enforced repo-wide (`test_skill_references.py:97`, `:106`, `:601-611`). Duplicating them creates two places to update and one more chance for a false failure, violating `AGENTS.md:18` ("Already in this codebase?").

The `disable-model-invocation: true` assertion is **vacuous today**: zero occurrences across all 42 `skills/*/SKILL.md`, and no loader contract in this repo honors that key. If dormancy from that key is a real concern, encode it structurally and globally — a two-line loop in `test_all_skills_have_correct_frontmatter_name` covering *every* skill — instead of a single-skill assertion.

Required: new test asserts **only novel** wiring (tripwire text present, description keyword set present, `@skill:` cross-links resolve), or the novel assertions fold into existing files. Keep prose assertions on the shortest stable anchor strings, not full sentences.

### Y2 — `RED-first` claim is only partly true

§4 says the new test "fails against unmodified `origin/main`". The duplicated assertions above already pass on `main`, so the RED gate is theater unless the spec names *which* assertions are RED. List them (tripwire sentence, description keywords, gate clauses) and state that every assertion maps to one risk, otherwise the test will be written to match the implementation instead of the requirement.

### Y3 — five practices, one feature

7 edited files + 1 new skill + 1 new test, against `AGENTS.md:28` ("Shortest working diff wins") and the thin-slice RED/GREEN cadence in `skills/make-feature/SKILL.md`. Split into three independently testable slices: **(1)** benchmark skill + gates, **(2)** conditional statechart gate, **(3)** prose `--unslop` + `AGENTS.md` rules. Then the weakest item can be dropped without unwinding the rest.

### Y4 — `Encode Lessons in Structure` is self-referential bloat

A 2-line always-on rule, added as prompt text, whose content is "stop adding prompt text", in a 212-line always-loaded `AGENTS.md`. `## 1. Ponytail` already carries "No unrequested abstractions" and "Can't be one line? Look again." Fold the lesson into that existing bullet (net-new concepts: 0) or drop it; do not add a second home with an unresolved "or" between `### Core Operating Behaviors` and `## 1. Ponytail` — a spec that offers the builder a choice is undecidable at review time.

### Y5 — "blast radius" already means two things here

`skills/codebase-audit/SKILL.md:112,135` = downstream artifact impact; `skills/git-signoff/SKILL.md:203` = size/LoC escalation tier. Adding a third meaning ("3-hop callers, serialization, feature flags") guarantees the word stops carrying signal. Either reuse the `codebase-audit` concept by name/link, or name the new check `Downstream Consumer Trace`.

### C1 — caveman conflict is real at the point of use, not in chat

The boundary ("never override `caveman` in chat") is correct but stated only in §3, far from where an agent actually applies it. `skills/prose-editor/SKILL.md:22` currently says *"Token Efficiency (Caveman & Ponytail): Rationales are concise…"* — an agent reading that skill first will apply caveman's compression **to the document**, exactly inverting unslop. Add one precedence line under `## Core Principles`: **unslop governs the edited document; caveman governs the agent's chat and rationales; they never apply to each other's surface.** No change to `skills/caveman/SKILL.md` is needed — that skill is chat-only and should stay untouched.

### C2 — "no over-compressed fragments" is the only hard contradiction

Caveman *requires* fragments ("Forecast time index out of bounds. Add guard."); unslop forbids them in external prose. The precedence line in C1 resolves it. Do not weaken either rule; do not let the unslop checklist be pasted into `AGENTS.md` (it is document-scoped, not agent-scoped).

### Y6 — single source of truth for the checklist

§2 tells the builder to restate the 7 verification questions inside `adversarial-review` and a verification gate inside `code-review-and-quality`. Prefer link-by-reference: `@skill:benchmark-checklist` (validated by `test_skill_references.py:74`), plus at most a 3-bullet digest. Cap the new `SKILL.md` at ~60 lines and put the 7 questions in one table — it is loaded in full on every invocation, and the "Report / inconclusive" rules are the part that actually changes behavior.

---

## 4. Spec-gate items (must be `[x]` before APPROVE)

- [ ] **B1** `spec.md` mandates `State transitions: <diagram | table | N/A — reason>`; qualifiers + ambiguity-resolves-to-inclusion documented; reviewer check audits the declaration, not just the diagram.
- [ ] **B2** `--unslop` activation path decided and written: either a Phase-3/PR-body trigger or removal of "PR descriptions" from §1.4.
- [ ] **B4** parser constraint stated verbatim (closed fences, backticked headers) and the plan names `test_parse_real_skill_md_without_crash` as the gate.
- [ ] **Y1/Y2** test scope trimmed to novel assertions; RED assertions enumerated.
- [ ] Section 2's "or" resolved for the new `AGENTS.md` rule; `scratchpad.md` clause added.

Non-blocking, cheap, recommended: B3 scope/exemption lines; Y3 slicing; Y5 naming; Y6 link-by-reference; the optional `README.md` registration (its skill list is curated — 21 entries vs 42 dirs — so omission is not drift).

---

## 5. Falsification notes (so this review is auditable)

* If the builder can show a loader contract in this repo that reads `disable-model-invocation`, Y1's "vacuous" claim falls and the assertion becomes structural value — cite the file and I withdraw that item.
* If `prose-editor` is invoked automatically anywhere in the lifecycle (grep shows it is not: only the `AGENTS.md:130` registration + its own tests), B2 collapses.
* All line numbers are from `AUDITED_SHA` = `376a978`; re-audit on the next commit and I will re-verify.

```text
VERDICT: NEEDS_REVISION
AUDITED_SHA: 376a978aa58c8fc002f1c0f6cd1f4c31d80a42af
```
