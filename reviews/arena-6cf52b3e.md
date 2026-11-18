# Reviewer Identification Proof

```text
REVIEWER_ID: arena-6cf52b3e
AUDITED_SHA: e2a5660960e28f6176cea2e5031024e778437dbc
BASE: origin/main @ 1451ee9
REVIEW_ROUND: 3 (plan gate — `plan.md` vs approved spec `218c002`)
REVIEW_FILE: reviews/arena-6cf52b3e.md
FINGERPRINT: pstack-spec-gate-6cf5
SESSION: persistent — same REVIEWER_ID across Rounds 1–3
```

**VERDICT: NEEDS_REVISION** (one blocking class, mechanical)

The plan is materially good: slices are decoupled, verify commands are executable, `N1`/`N2`/`N3` are closed with the exact wording I asked for, and the **Guard 1 catch is correct — it also proves my Round 1 `B4` advice was wrong**. The blocker is a single class: **two RED assertions demand literal tokens that the plan's own GREEN text never produces**, so those tests stay red after implementation. Fix the vocabulary contract and this plan approves on the next revision.

Round 2 and Round 1 bodies are preserved as archives below.

---

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
