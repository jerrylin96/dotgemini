# Reviewer Identification Proof

```text
REVIEWER_ID: arena-6cf52b3e
AUDITED_SHA: 10e094563d8fff1ca3c483d2db61dbd614f37da7
BASE: origin/main @ 1451ee9
REVIEW_ROUND: 5 (GREEN code gate — Phase 3)
REVIEW_FILE: reviews/arena-6cf52b3e.md
FINGERPRINT: pstack-spec-gate-6cf5
SESSION: persistent — same REVIEWER_ID across Rounds 1–5
```

**VERDICT: APPROVE**

Implementation matches the approved spec (`218c002`) and plan (`7e4dda5`). I re-ran both commits rather than trusting the report: the pushed RED suite genuinely fails (7 failed, 0 errors) and the GREEN tree is 438 passed / ruff clean. Scope is honest — documentation and tests only, no runtime code. Five notes below are polish, not gates.

---

## A. Verification matrix (executed in throwaway worktrees)

| Check | Result |
|---|---|
| RED commit `538a477` — `pytest scripts/tests/test_pstack_harvest.py -q` | **7 failed in 0.07s, 0 errors** — clean RED, no collection failures |
| RED commit — full suite | **7 failed, 431 passed, 3 skipped** (431 = 430 baseline + Task 0's permanent guard, green by design) |
| RED commit contents | only `test_pstack_harvest.py` (+201), `test_skill_references.py` (+21), ephemeral files — no implementation smuggled in |
| GREEN commit `10e0945` — full suite | **438 passed, 3 skipped** |
| GREEN — `ruff check .` | **All checks passed** |
| Feature scope vs `origin/main` | 479 insertions; the only non-markdown files are the two test files |
| `GEMINI.md` | `git ls-tree` mode **120000** → `AGENTS.md`; symlink intact |
| `file://` links in `skills/` | none |
| `disable-model-invocation` | absent from all 43 skills; guard scans frontmatter only (verified in source) |
| Guard 1/2/3 dry-run on delivered `prose-editor/SKILL.md` | `parse_suggestion_cards()` → **0 cards, no exception**; no numeric `### Suggestion #<digits>` anywhere; fences closed |
| Section-boundary probe on all 8 `_section_between` calls in the new test file | all resolve to real end markers (one loose boundary, W3) |

## B. Focus 1 — zero-dormancy wiring & trigger precision

Every layer is present at a reachable anchor, and each gate is conditional in wording rather than blanket:

| Layer | Location at `10e0945` | Assessment |
|---|---|---|
| Imperative skill trigger | `skills/benchmark-checklist/SKILL.md:3` | `CRITICAL RULE:` + 6 trigger keywords + changeset scope + explicit non-trigger clause. Fires on *running* a benchmark, not only on reporting one. |
| Always-on tripwire | `AGENTS.md:93` (inside `Empirical Grounding`) | "Never report a speedup, latency/throughput claim, or benchmark comparison for a changeset without invoking `benchmark-checklist`" — imperative, scoped, correctly nested under the anti-hallucination rule it enforces. |
| Discovery registration | `AGENTS.md:135` | Registered in §4 with description; makes the skill loadable. |
| Code-review gate | `skills/code-review-and-quality/SKILL.md:53` | `@skill:benchmark-checklist` + limiter / tuned settings / ≥5 runs. |
| Review gate | `skills/adversarial-review/SKILL.md:363` | `Performance Claims Check (Conditional on perf/benchmark claims)`, `inconclusive` verdict vocabulary matches the skill. |
| State gate (author) | `skills/spec-driven-development/SKILL.md:27-29` | Declaration + 7 concrete triggers + tie-break ("ambiguity resolves toward inclusion"). |
| State gate (auditor) | `skills/adversarial-review/SKILL.md:47` | Audits presence, plausibility, non-empty `N/A` reason, and illegal/timeout/error coverage. Author and auditor halves both exist — the gap that made Round 1 `B1` blocking is genuinely closed. |
| Downstream Consumer Trace | `adversarial-review:362` + `skills/ponytail/SKILL.md:30` | Both carry "beyond `grep`", indirect consumers, execution proof / `unproven`; adversarial side is marked "Unconditional for code diffs". |
| Unslop wiring | `prose-editor:13,24,40-43`; `make-feature:257`; `adversarial-review:364` | Flag + tier + precedence in the skill; inline rule-application (not skill invocation) at both external-prose surfaces; `@skill:prose-editor` correctly absent. |

Dormancy spot-checks that could have failed and did not: the state gate is worded for ambiguity resolution rather than "if you feel like it"; the perf gate says `Conditional on perf/benchmark claims for the changeset` (so unrelated docs do not trip it); the tripwire names the skill and §4 provides the load path.

## C. Focus 2 — invariants, parser safety, quality

* `benchmark-checklist/SKILL.md` is 33 lines, not the planned 55–65 (W5) — but nothing is missing: changeset scope, ballpark rule, supplied-evidence path, pre-run hygiene (claim sentence, script audit, `uptime`/core count), all 7 questions with required checks, and a verdict rubric with `inconclusive`. Q3's Amdahl arithmetic (10% removed → ~11% ceiling) is correct. Compression is the right call.
* `prose-editor` edits are additive: one trigger line, one precedence principle, one tier block. All required headings and `Category`/`Impact` enums untouched, so `test_enum_source_of_truth_sync` and `test_parse_real_skill_md_without_crash` stay green (verified by execution, not inference).
* New tests are slice-decoupled exactly as claimed: `-k "benchmark"` selects the 3 Slice-1 tests, `-k "statechart or downstream"` the 2 Slice-2 tests, no leakage; `test_agents_md_encode_lessons_rule` is independent.
* The permanent guard is real: it fails closed on any `disable-model-invocation: true` in frontmatter and does not scan bodies (so a skill may quote the string in prose without false positives).

## D. Findings (non-blocking)

### W1 — ballpark policy disagrees across the three surfaces

`benchmark-checklist/SKILL.md:10` allows a single-run ballpark **only** "if user explicitly asks for a ballpark". Both review gates accept it unconditionally: `adversarial-review:363` "(or explicit single-run ballpark …)" and `code-review-and-quality:53` "(… or explicit single-run ballpark disclosure)". Net effect: a reviewer can approve a claim the skill forbids. One-word fix — say "user-requested single-run ballpark" in both gates, or drop the user-request condition from the skill. Pick one; do not leave the mismatch.

### W2 — tripwire names the skill but does not link it

`AGENTS.md:93` says ``invoking `benchmark-checklist` ``; every other skill mention in §3 resolves through a link or is registered in §4 (which it is, `:135`). Adding `[benchmark-checklist](skills/benchmark-checklist/SKILL.md)` at `:93` costs nothing and removes one hop for the agent.

### W3 — one test boundary is looser than it looks

`test_unslop_tier_precedence_and_wiring` slices `make-feature` from `Step 7c` to `5. **Phase 4` — which spans Step 7c *and* Step 8. The assertion would still pass if the prose-editor link drifted into Step 8. Anchor the end at `Step 8`. (All other seven boundaries resolve tightly; I probed each.) Same family, lower value: `"n/a" in draft_lower` in `test_statechart_gate_is_auditable` can match unrelated `/n/a/` text.

### W4 — the skill bans a mark it uses

`benchmark-checklist/SKILL.md:10` and `:22-28` use em dashes while `prose-editor --unslop` (the same feature) tells writers to avoid them in external prose. Harmless inside an internal skill, but a self-contradicting exemplar invites exactly the "rules are advisory" reading this feature fights. Reword to commas when convenient.

### W5 — line-count deviation (recorded, not contested)

Plan expected 55–65 lines for the skill; 33 delivered. Content-complete and denser, so this is Ponytail working as intended. Recorded only so the plan/implementation delta is explicit in the audit trail.

### W6 — README not updated (optional)

`README.md` §3 lists a curated subset (21 of 43 skills); `benchmark-checklist` is not added. Optional by design — the test-visible registration is `AGENTS.md:135`, which is present.

## E. Convergence statement

Spec `APPROVE` @ `218c002` · Plan `APPROVE` @ `7e4dda5` · Code `APPROVE` @ `10e0945`. No blocking findings; `W1` is the only one worth a commit, and it does not require re-review — if the builder lands it, I will confirm against `AUDITED_SHA` in one round.

Pre-merge checklist for the builder: purge `${FEATURE_SLUG}/` at Step 7b (spec, plan, review prompt, scorecard are still in-tree), re-run `run_in_env.py … pytest && ruff check .` inside the real environment runner (I used a host venv; `~/.gemini/scripts/` is absent in this sandbox), and hand off to `/git-signoff` — the merge itself stays human-owned.

```text
VERDICT: APPROVE
AUDITED_SHA: 10e094563d8fff1ca3c483d2db61dbd614f37da7
ROUND_4_ITEMS: P7 (indirect token -> ponytail-only assertion, accepted), P8 (canonical 4 tokens only, accepted)
NOTES: W1 ballpark policy mismatch (one-word fix), W2 tripwire link, W3 loose Step 7c boundary, W4 style self-contradiction, W5 line-count delta, W6 README optional
```

---

---

# Archive — Round 4 (audited `7e4dda5`, plan gate, APPROVE)

## A. Round 4 disposition

| Item | Status | Evidence at `7e4dda5` |
|---|---|---|
| **P1(a)** `benchmark` in frontmatter description | **CLOSED** | Planned description contains all six asserted tokens — probe: `benchmark ✓ latency ✓ throughput ✓ speedup ✓(⊂"speedups") profiling ✓ regression ✓(⊂"regressions")`; still starts `CRITICAL RULE:` and carries the changeset scope clause. |
| **P1(b)** canonical `--unslop` tokens | **CLOSED** | Task 4 now writes literal `AI vocabulary`, `Em dash`, `Abstract metaphor nouns`, `Over-compression`; Test 6 asserts the same four case-insensitively. Probe: 4/4 present in the planned block. |
| **P2** filtered-green declared | **CLOSED** | Execution Strategy states it; repeated in both slice verify headings; "full suite 100% GREEN at Task 4 before the Step 5 GREEN commit" — and **Step 5 exists** (`skills/make-feature/SKILL.md:178` "Step 5 (Stage & Commit GREEN Implementation)"). |
| **P3** text anchors | **CLOSED** | Every edit target is anchored by text (`5. **Perform Adversarial Review**`, `**Writing Quality** (Unconditional)`, `Step 7c`, `### Key Rules`, `### 2. Draft the Spec`, `**Bug fix = root cause, not symptom.**`); no drifting line numbers remain. |
| **P4** YAML quote handling | **CLOSED** | Test 1 explicitly strips quotes / folds block scalars per `test_skill_references.py` style. |
| **P5** duplicate guard | **CLOSED** | Task 1 preamble forbids duplicating Task 0's check; Test 1 no longer asserts it. |
| **P6** portability + label | **CLOSED** | `"${WORKTREE_PATH}"` quoted throughout; `test_prose_editor.py` relabelled "Regression Gate". |

Guard citation also corrected: `validator.py:301-307` now matches the file exactly (Guard 1 comment at `:301`).

## B. Empirical checks at `7e4dda5`

| Probe | Result |
|---|---|
| Code tree vs `218c002` | unchanged — the round-3 commit touches only `plan.md`, `review_prompt.md`, `reviewer_scorecard.md` |
| `pytest -q` / `ruff check .` | **430 passed, 3 skipped** / clean |
| Token oracle on the plan's own RED↔GREEN strings | 6/6 benchmark tokens, 4/4 unslop tokens present (see A) |
| **Parser dry-run**: planned `--unslop` bullet block inserted into a copy of `prose-editor/SKILL.md`, then `validator.parse_suggestion_cards()` | **PASS**, `cards = 0` — the 7-bullet block (30 terms, `"Not just X, but Y"`, `Fancy "is"`, parenthesised metaphor list) adds no card header and no fence, so `test_parse_real_skill_md_without_crash` stays green |
| Slice-filter oracle (re-checked) | `benchmark` → exactly 3 Slice-1 tests; `statechart or downstream` → exactly 2 Slice-2 tests |

## C. Build-time notes (no re-round needed)

### P7 — one word: `indirect` is asserted but not planned

Test 5 lists "indirect consumers" among the assertions for `adversarial-review` §5, but Task 3's adversarial-review bullet says only *"inspect beyond `grep` (library source/pinned versions, JSON/DB/wire formats, config/feature flags, teardown/microtask order, 3-hop callers)"* — probe: `"indirect" in bullet == False`. The word does appear in the `ponytail` addition. Two acceptable resolutions at authoring time: add the word to the adversarial-review bullet, or scope Test 5's tokens per file (`beyond grep`/`unproven` for adversarial-review; `indirect` for ponytail). Pick one when writing the test; the failure surfaces immediately in Task 4's verify.

### P8 — the plan's unslop vocabulary is wider than the approved spec's list

Spec §2 Slice 3 names ~13 tells; Task 4 enumerates ~30 (adds `Curly quotes`, `Boldface overuse`, `Title case headings`, `Decorative emojis`, `Excessive hedging`, `Generic conclusions`, `Mannered prose`, metaphor lexicon). This is faithful to upstream `pstack` `unslop` and inside the spirit of the approved clause, but it grows `prose-editor/SKILL.md` from 142 lines by ~10–12 and makes the spec the weaker contract. Either is fine — just do not let the two lists drift silently: if the implementation keeps the wider list, the test must assert the four canonical tokens only (as planned), not the extras.

## D. Convergence statement

Spec gate: `APPROVE` @ `218c002`. Plan gate: `APPROVE` @ `7e4dda5`. `P7`/`P8` are authoring decisions inside the approved envelope. I remain on the Retain List as `arena-6cf52b3e` for the RED-test gate (Step 4c) and the GREEN code gate (Phase 3).

```text
VERDICT: APPROVE
AUDITED_SHA: 7e4dda560715a982f80ba397bf3bbbc17ed02c62
ROUND_3_ITEMS: P1(a) P1(b) P2 P3 P4 P5 P6 -> [x] Resolved in 7e4dda5
NOTES: P7 (one-word `indirect` alignment), P8 (plan vocabulary wider than spec; assert canonical 4 only)
```

---
---

# Archive — Round 3 (audited `e2a5660`, plan gate, NEEDS_REVISION)

## A. What I verified at `e2a5660`

| Probe | Result |
|---|---|
| Code tree vs `218c002` | identical — the two new commits touch only `plan.md`, `review_prompt.md`, `reviewer_scorecard.md` (no skill/code file) |
| `pytest -q` | **430 passed, 3 skipped**; `ruff check .` → clean (re-run at this SHA) |
| Guard 1 location | `skills/prose-editor/resources/validator.py:301-307` (plan cites `294-306` — substance right, line numbers ~7 low) |
| Guard 1 behaviour, numeric header **inside** a closed fence | `ValueError: 1 suggestion header(s) found but all are inside fenced code blocks` |
| Non-numeric `### Suggestion #<ID>` **inside** a closed fence (repo's own template style) | **passes**, `cards=0` |
| Numeric backticked header **outside** fence, no fields | `ValueError: Missing required field 'Anchor'` |
| Unfenced non-backticked header | `ValueError: Malformed suggestion header` |
| Slice filter oracle (`-k` → test names) | `benchmark` → exactly the 3 Slice-1 tests; `statechart or downstream` → exactly the 2 Slice-2 tests. **No cross-slice leakage.** |

Anchors re-verified: `AGENTS.md:92` (`Empirical Grounding`), `AGENTS.md:109+` (§4 skills), `AGENTS.md:25` (`### Key Rules`), `spec-driven-development/SKILL.md:25`, `adversarial-review/SKILL.md:47,358,362`, `ponytail/SKILL.md:30`, `prose-editor/SKILL.md:10,22,26`, `make-feature/SKILL.md:255`.

## B. Retraction of my Round 1 `B4` advice

Round 1 said: *"Any example card header MUST live inside a closed fenced block."* That is **wrong for numeric headers** and would have caused the exact Guard 1 failure this round caught. Reproduced above: a fenced `### Suggestion #1 \`[Clarity]\` \`[Minor]\`` raises.

Correct rule, now empirically pinned:

* numeric `### Suggestion #<digits>` — fails **everywhere** (fenced → Guard 1; unfenced → Guard 3 or missing-field).
* non-numeric `### Suggestion #<ID>` inside a **closed** fence — passes (this is why the repo's own `## Suggestion Card Schema` block at `prose-editor/SKILL.md:46` is safe today).
* any unclosed fence — fails (Guard 2).

Task 4's blanket ban is therefore **safe but over-broad**; it is a fine choice for a prose pass that does not need card examples. Keep it, and note the `<ID>`-in-fence alternative so a later editor does not "improve" the section by adding a numeric example. My `B4` feedback is superseded by the builder's Guard 1 finding.

## C. `S1`/`N1`/`N2`/`N3` closure

| Item | Status | Evidence |
|---|---|---|
| **N1** `@skill:prose-editor` → relative link | **CLOSED** | Task 4 uses `[prose-editor](../prose-editor/SKILL.md)` + "apply `--unslop` rules inline" in both `make-feature` Step 7c and `adversarial-review` Writing Quality; the relative path is correct from both directories. |
| **N2** global guard labelled permanent | **CLOSED** | Task 0 titled "Permanent Structural Guard — GREEN Regression Guard", explicitly "not counted as a RED test". |
| **N3** no placeholder lock | **CLOSED** | Test 4 asserts `State transitions:`, trigger vocabulary, tie-break, non-empty `N/A` reason — not the `<…|…>` template. |
| **S1** per-slice green cadence | **PARTIAL → P2** | Slices are decoupled *by filter*, not by file: Task 1 writes all 7 tests, so Slice 1's `GREEN` commit still carries 4 failing tests in the tree. |

## D. Findings

### P1 — BLOCKING: two RED assertions can never go GREEN as written

**(a) `benchmark` keyword.** Test 1 requires the frontmatter `description` to include `benchmark`. Task 2's planned description — *"CRITICAL RULE: You MUST read and follow this skill whenever reporting or comparing performance numbers, speedups, latency, throughput, profiling, or perf regressions for a changeset (does not fire on unrelated docs merely mentioning perf terms)."* — contains no `benchmark`. Only the skill **name** does. If the test inspects frontmatter (as Test 1 says), it stays red after GREEN, and the "fix" is to weaken the test — the failure mode structural tests exist to prevent.

**(b) unslop token set.** Test 6 requires literal `AI vocabulary`, `Em dash`, `Abstract metaphor nouns`, `Over-compression`. Task 4's checklist text has `AI vocab`, `em-dash/…`, `abstract metaphor nouns`, `no over-compressed fragments`. Spec §2 has `AI vocabulary`, `em-dash`, `abstract metaphor nouns`, `no over-compressed fragments`. So the test matches the spec 2/4, the plan 1/4, and **neither** for `Em dash` / `Over-compression`.

Fix (once, then it is mechanical): declare the canonical token list in the spec (§2 Slice 3 is the natural home), have the test assert exactly those strings — case-insensitive substring on a normalized copy of `SKILL.md` so `em-dash` matches — and paste the same strings into Task 4 and Task 2's description. Do not let the test paraphrase the implementation.

### P2 — `S1` closure: say "filtered-green" out loud

Writing all 7 RED tests at Step 4d and verifying per slice with `-k` is coherent with the plan's stated strategy, but Slice 1's post-implementation audit will run the full suite and see 4 red tests. That is a guaranteed false-positive review round. Choose and state one:

* **split by slice** (`test_pstack_harvest_benchmark.py` / `_statechart.py` / `_unslop.py`) — each slice's commit is suite-green; or
* **keep one file** and add one sentence to the plan + both slice commit messages: *"intermediate slices are filtered-green by design; the full suite is green only at Task 4."*

### P3 — anchor by text, not line number

Three tasks edit the same neighbourhood and cite `adversarial-review/SKILL.md` lines 361/362 (§5 starts at `:358`; the `Writing Quality` bullet is `:362`). After Slice 1 inserts lines, Slice 3's `:362` points at something else. Anchor to `5. **Perform Adversarial Review**` and `**Writing Quality** (Unconditional)` instead.

### P4 — YAML quoting in Test 1

Task 2 writes `description: "CRITICAL RULE: …"` (double-quoted). A `value.startswith("CRITICAL RULE:")` assertion fails on the leading quote unless the test strips `"`/`'` — the existing helper already does this for `name` (`test_skill_references.py:52-54`). Reuse that pattern, or use a `description: |` block scalar like `skills/ml-best-practices/SKILL.md:3`.

### P5 — duplication nit

Test 1 also asserts the new skill omits `disable-model-invocation: true`, which Task 0 now guards repo-wide. Spec §3 says "zero test duplication" — drop it or note it as deliberate defence-in-depth.

### P6 — portability / label nit

Pre-flight and every verify command hardcode `/Users/jlin404/.gemini/tmp/worktrees/…`; use `${WORKTREE_PATH}` per `make-feature` convention so the plan survives a different machine. Task 4 also lists `skills/prose-editor/tests/test_prose_editor.py` under "RED Test Target" — it is a regression gate (green before and after), same mislabel family as `N2`.

## E. Convergence statement

Only **P1** blocks; **P2** needs one sentence; **P3–P6** are authoring notes. With P1's canonical vocabulary list in place, expect `APPROVE` on the next plan revision with no further spec work. Persisting as `arena-6cf52b3e` for the RED-test gate.

```text
VERDICT: NEEDS_REVISION
AUDITED_SHA: e2a5660960e28f6176cea2e5031024e778437dbc
ROUND_2_ITEMS: S1 -> PARTIAL (P2); N1 N2 N3 -> [x] Resolved in e2a5660
B4_ERRATUM: Round 1 "fence the example header" advice withdrawn — Guard 1 fails numeric fenced headers; builder's finding is correct
OPEN_BLOCKING: P1
```

---
---

# Archive — Round 2 (audited `218c002`, spec gate, APPROVE)

## A. Round 2 disposition

| Item | Status | Evidence at `218c002` |
|---|---|---|
| **B1** auditable statechart gate | **CLOSED** | spec self-declares `State transitions: N/A — …`; §2 mandates the same declaration with concrete triggers (background tasks, retry/backoff, pools, caches, job/stream lifecycles, cancellation/teardown, outliving `await`/thread order) + ambiguity-resolves-to-inclusion; `spec-review` audits the declaration *and* the `N/A` reason. Dormancy escape hatch removed. |
| **B2** `--unslop` activation | **CLOSED** | `make-feature` **Step 7c exists** at `skills/make-feature/SKILL.md:255` and already emits `review_report_<feature>.md` (`:257`) "for chat review and GitHub PR description/comments only" — an honest, existing surface, not an invented one. `adversarial-review` Writing Quality anchor exists at `:362`. |
| **B3** benchmark scope + supplied evidence | **CLOSED** | changeset-claim scope clause; user-supplied methodology (hardware, run count, limiter) path says verify limits/tuning/reproducibility, do not re-benchmark. |
| **B4** prose-editor parser constraint | **CLOSED** | constraint stated verbatim (closed fences, backticked header) and names `test_parse_real_skill_md_without_crash` as the gate. Matches my reproduced failure modes (`resources/validator.py:341` Guard 3). |
| **Y1** test duplication | **CLOSED** | §3 "Zero test duplication"; novel assertions only; `disable-model-invocation` promoted to a repo-wide guard. |
| **Y2** RED honesty | **PARTIAL → N2** | §4.2 enumerates RED assertions correctly; §4.1 global guard passes today (zero occurrences across 42 `skills/*/SKILL.md`), so it is a permanent structural guard, not RED. |
| **Y3** slicing | **CLOSED** | 3 thin slices, each independently testable. |
| **Y4** self-referential bloat | **CLOSED** | single bullet, placed in `AGENTS.md:25` `### Key Rules` (verified heading exists); the `## 1` vs `## 3` "or" is gone. |
| **Y5** naming collision | **CLOSED** | renamed `Downstream Consumer Trace`, collision with `codebase-audit:135` / `git-signoff:203` acknowledged. |
| **Y6** single source of truth | **CLOSED** | `@skill:benchmark-checklist` + 3-bullet digest, no restated 7-question list. |
| **C1/C2** caveman precedence | **CLOSED** | precedence line lands in `prose-editor` `## Core Principles` (near the existing "Caveman & Ponytail" token-efficiency principle at `:22`), which is exactly where the inversion risk lived. |
| **I5** scratchpad path drift | **CLOSED** | §2 forbids non-canonical `scratchpad.md` path variants in the `AGENTS.md` edit. |

Anchors re-verified at `218c002` (all present, so no edit target is fictional): `AGENTS.md:25,91,109`; `spec-driven-development/SKILL.md:25`; `adversarial-review/SKILL.md:47,358,362`; `code-review-and-quality/SKILL.md:48`; `ponytail/SKILL.md:30`; `prose-editor/SKILL.md:10,17,26`; `make-feature/SKILL.md:255,257`.

## B. Empirical baseline (Round 2)

| Probe | Result |
|---|---|
| `git diff --stat 376a978..218c002` | 3 files: `spec.md` ±81, `review_prompt.md` ±14, `reviewer_scorecard.md` +10 — **no code or skill file touched** |
| Working tree vs `218c002` (excluding `reviews/`) | identical — my tree is the audited content plus this review only |
| `pytest -q` | **430 passed, 3 skipped** (host venv, same pins as `requirements.txt`) |
| `ruff check .` | **All checks passed** |

Still not verified (unchanged from Round 1): `~/.gemini/scripts/run_in_env.py` is absent in this sandbox; tests ran on a host venv. Builder must re-run the wrapped command at Phase 2.

## C. Conditions for `plan.md` (not spec blockers)

### S1 — one test file across three slices breaks the per-slice GREEN cadence

§4.2 puts all three slices' assertions in a single `scripts/tests/test_pstack_harvest.py`, while §2 mandates 3 slices, and `AGENTS.md` Phase 2 (Heavy Mode) requires every slice commit to leave the suite green (`test(slice-N)` RED → `feat(slice-N)` GREEN). As written, Slice 1's commit carries failing tests for Slices 2–3, so no intermediate slice can be green.

Fix in `plan.md` (pick one, state it): one module per slice (`test_pstack_harvest_benchmark.py`, `_statechart.py`, `_unslop.py`), **or** one file appended slice-by-slice so each test lands with its implementation.

### N1 — `@skill:prose-editor` is an invocation sigil, not a doc link

In this repo `@skill:<name>` means *invoke that skill* (`skills/catchmeup/SKILL.md:95` "Delegate to @skill:explain-diff"; `skills/dataform-bigquery/SKILL.md:95,111` "Follow the protocol in @skill:data-autocleaning/…"; validated as "resolves to a valid, **loadable** skill" by `test_skill_references.py:74`). At Step 7c the intent is "apply the `--unslop` rules while drafting", not "run a full suggestion-card review over a PR body". Invoking `prose-editor` there produces the wrong artifact (advisory cards on prose the agent is about to publish).

Fix: keep `@skill:benchmark-checklist` (there the intent really is "run the skill"), but reference prose-editor by relative link `[prose-editor](../prose-editor/SKILL.md)` + "apply the `--unslop` rules". If the builder prefers the sigil, the spec must say the `--unslop` tier is applied *inline*, not that the skill is run to completion.

### N2 — label the global guard as permanent, not RED

§4 is titled "Enumerated RED Assertions" but §4.1 (`disable-model-invocation` absent) passes on `origin/main` today. Reword §4.1 as "permanent structural guard (GREEN from day one; prevents future regression)" so the RED gate stays honest and the Phase 2 reviewer does not chase a phantom failing test.

### N3 — don't lock the placeholder template

`test_statechart_gate_is_auditable` should assert the stable anchors — literal `State transitions:`, the trigger vocabulary, the tie-break sentence, and a non-empty `N/A` reason — not the whole `<Mermaid stateDiagram-v2 | transition table | N/A — <reason>>` placeholder string. Asserting the template makes any wording fix a test failure, which is the brittleness `Y2`/`Y6` were about.

Non-blocking polish: the spec's inline-code rendering of the example header (`### Suggestion #1 \`[Clarity]\` \`[Minor]\``) is awkward inside a backtick span; in `SKILL.md` put it in a closed fenced block (which B4 already requires) and keep the spec sentence plain.

## D. Convergence statement

All Round 1 blocking findings are resolved; no blocking finding remains. Fix `S1`/`N1` while drafting `plan.md`, `N2`/`N3` at test-authoring time. I am available for the Plan gate under the same `REVIEWER_ID`.

```text
VERDICT: APPROVE
AUDITED_SHA: 218c0020b595ec07561f629d78a661d16d6f3226
ROUND_1_ITEMS: B1 B2 B3 B4 Y1 Y2 Y3 Y4 Y5 Y6 C1 C2 I5 -> [x] Resolved in 218c002
OPEN: S1, N1 (plan-time), N2, N3 (test-precision)
```

---
---

# Archive — Round 1 (audited `376a978`)

Round-1 verdict was `NEEDS_REVISION`; body retained verbatim below for audit trail. Line numbers in this archive refer to `376a978`, which is superseded by `218c002` for the three ephemeral files only.

## Baseline (Round 1)

| Probe | Result |
|---|---|
| `git diff --stat origin/main..376a978` | `spec.md` +45, `review_prompt.md` +8 — 2 files, zero code |
| `pytest -q` | 430 passed, 3 skipped |
| `ruff check .` | All checks passed |
| Prototype `skills/benchmark-checklist/SKILL.md` + `pytest scripts/tests/test_skill_references.py` | 20 passed (probe dir deleted) |
| `validator.parse_suggestion_cards()` probes | unfenced `### Suggestion #1 [Clarity] [Minor]` → `Malformed suggestion header`; unterminated fence → `Unterminated code fence` |

## Round 1 blockers

* **B1** — statechart gate had no auditable trigger (self-exemption) → required machine-checkable `State transitions:` declaration, qualifiers, ambiguity tie-break, and reviewer audit of the declaration.
* **B2** — `--unslop` had no activation path for the PR-description goal (`prose-editor` is hand-invoked only).
* **B3** — benchmark triggers unscoped vs. repo prose mentioning `latency`/`throughput`; no exemption for user-supplied calibrated measurements.
* **B4** — spec did not state the prose-editor parser constraint whose violation breaks `test_parse_real_skill_md_without_crash`.

## Round 1 YAGNI / invariants / caveman

* **Y1** new test duplicated `GEMINI.md` symlink (`test_skill_references.py:601-611`), name grammar (`:97`), `file://` (`:106`); `disable-model-invocation` absent from all 42 skills → global guard instead.
* **Y2** "fails RED on origin/main" was unenumerated.
* **Y3** 5 practices / 7 files+ vs. `AGENTS.md:28` ("Shortest working diff wins").
* **Y4** `Encode Lessons in Structure` as new always-on prose was self-referential; an unresolved `## 1` vs `## 3` "or" made the spec undecidable.
* **Y5** "blast radius" already means size tier (`git-signoff:203`) and downstream artifacts (`codebase-audit:135`).
* **Y6** restating the 7 questions in two skills duplicated the source of truth.
* **C1/C2** `prose-editor:22` ties rationales to Caveman; unslop-vs-caveman precedence was stated only in §3, far from use; "no over-compressed fragments" is the only hard contradiction.
* **I5** tracked-md scan (`test_skill_references.py:178`) requires the canonical `scratchpad.md` path.

All accepted by the builder at `218c002` (see scorecard, Round 1 triage).
