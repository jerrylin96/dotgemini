# Independent outsider review — posture, merge gates, and complexity debt

> One-time external analysis of `agent/port-principled-dev`, recorded durably so
> future sessions inherit its context. This document is informational only: it
> changes no code, requests no unbounded work, and must not be used to reopen a
> hardening loop.
>
> **Analysis basis:** implementation boundary `7962ff504f36aa7e3edd18007384f28a57620969`;
> status document read at branch tip `08ac64d` (`docs: persist development
> status and roadmap`). Method: full-branch commit archaeology (all commits
> ahead of `main`, `bb4b540995ecef65f2be2752c001b5345850fa38`), diff review of
> the post-14:00 hardening tail, and repeated local test runs in a clean
> POSIX environment without a `goose` binary.

## Verdict

The branch is healthy and its hardening phase **converged legitimately**:
findings decreased monotonically in severity, no bug class was ever fixed
twice, the test suite stayed green at every observed checkpoint (80 → 87 → 93
→ 98 → 112 passing in `principled-dev/tests`), and per-commit diff size
shrank steadily. The items below are posture, cleanup, and exactly **one**
genuine pre-merge/pre-extraction gate — not evidence that the tail was waste.
Sections marked *Affirmed* exist to prevent future sessions from misreading
this critique as license to undo completed work.

## P1 — Gate before merge or extraction: goose-dependent packaging tests

`pytest.ini` was correctly expanded with `testpaths = ... principled-dev/tests`,
which closed the real "suite invisible to CI" gap. Consequence that was **not**
recorded: two integration tests in `tests/test_packaging.py`
(`test_plugin_installs_and_namespaces_skills`,
`test_recipes_validate_and_match_primary_skills`) hard-assert
`shutil.which("goose")` and exercise the real `goose` binary.

- CI (`.github/workflows/ci.yml`) triggers on push/PR to `main` and does not
  install goose. On merge or on this branch's PR, those two tests will fail
  red even though nothing is broken.
- The recorded evidence (`default pytest: 235 passed`) was produced in an
  environment **with** goose installed. In a clean environment the same run
  shows exactly these 2 failures. Restating evidence without its environment
  is fragile: always record environmental prerequisites next to counts.
- Risk to the next session: the runbook in `development-status.md` says
  "run default pytest" without noting the goose prerequisite. On a
  goose-less machine, the two failures will look like a regression and could
  trigger an unnecessary "fix" loop.

**Resolution (either is acceptable, first is cheaper):**

1. Mark both tests
   `@pytest.mark.skipif(shutil.which("goose") is None, reason="requires goose CLI")`, or
2. Add a goose install step to `ci.yml`.

Add one line to the status doc's runbook: *"2 packaging tests require a
`goose` binary on PATH; absent it they skip (or, pre-fix, fail) —
not a regression."*

## P2 — Deployment posture: the enforcement boundary is outside this repo

`known-limitations.md` is correct everywhere it says hooks are advisory,
fail-open, narrow-coverage, and "never describe this as a sandbox." Treat
that framing as permanently load-bearing. The consequence that has **not**
been recorded as a plan: for any deployment where the gates must *hold*
rather than *advise*, enforcement must live at formal boundaries the agent
does not control — the git server, credentials, kernel, or network — not in
shell-command parsing. Text parsing of hostile free-form commands is
completable in principle for accidents and uncompletable in principle for
adversaries; the tail correctly stopped adding parser cases at `14acb83`
(wildcard refspecs, redundant forms) and must not resume.

Recommended **deployment hardening profile** (all external to this repo;
zero lines required here — record as optional guidance, not as code tasks):

- **Branch ruleset on the integration branch** (GitHub rulesets/branch
  protection): require PR, require human approval (CODEOWNERS), block force
  pushes and deletions, require status checks. Enforced server-side; no
  command spelling, wrapper, or alternate client bypasses it.
- **Scoped credentials:** the agent's token/account should lack write
  permission to the canonical integration branch — e.g., write access to a
  fork only. Capability withdrawal beats command scanning.
- **Containment:** run goose with the primary checkout mounted read-only
  and only the worktree root writable (the fixed roots under
  `${XDG_CACHE_HOME}/principled-dev/worktrees` make this two mount rules),
  or under a dedicated UID with equivalent ownership. Kernel-enforced;
  parsing-free.
- **Egress:** proxy/allowlist network egress for the agent environment so
  non-`git` transports (`gh api`, `curl`, custom clients) cannot reach
  integration endpoints.
- **Merge-gate consumption of the existing machinery:** a required CI
  status check that recomputes the review digest from the pushed SHA/tree,
  requires the human signoff attestation, and requires non-agent CODEOWNERS
  approval. This is what turns the (genuinely good) digest/ls-remote/CAS
  machinery built on this branch from local bookkeeping into enforcement,
  and makes it tamper-proof against edits to local state.

## P3 — Complexity debt from the hardening tail

The post-14:00 tail added +1,624/−143 lines across 18 files:
`state.py` 260 → 424 lines, `StateStore` methods 10 → 19,
`lifecycle.py` 175 → 299. This is latent complexity debt, concentrated in
one module plus the publish/signoff path — not damage. Specific latent
risks, in descending priority:

1. **Broad `except Exception` conversions in `lifecycle.py`** (review-digest
   computation; remote-verification; state persistence): any future
   programmer error in those blocks is reported to operators as a benign
   phase-specific "partial publication" message, masking bugs. Narrow the
   exception types or re-raise unexpected ones separately. (The two
   pre-existing broad catches in `path_policy.py` are intentional,
   documented fail-open behavior — leave them.)
2. **Import-time `os.register_at_fork` plus module-level mutable sets**:
   importing `principled_dev.state` mutates process-global behavior.
   Acceptable for a standalone CLI; a trap if the package is ever embedded
   in-process. Move registration behind explicit initialization if
   embedding is ever on the table.
3. **Regex redaction of free-text `cause` strings** can garble unrelated
   messages (any text resembling `?token=`/`user@` in a URL). Safer shape:
   sanitize structured fields (`remote`, `branch`, `observed_sha`) as now;
   sanitize `cause` only when it actually contains URL-shaped content.
4. **Fail-fast reentrancy detector** raises on any nested state access.
   Correct for deadlock prevention, but it is a behavioral trap for future
   contributors whose legitimate flow happens to nest. Record it in
   known-limitations so it is discovered by reading, not by stack trace.
5. **Fork-safety machinery largely guards scenarios exercised by its own
   test suite.** Keep it — removal now costs more than it saves — but do
   not extend it further without a concrete deployment need.

One structural lesson to record for future design decisions: the entire
back half of the tail (concurrency serialization through fork-safety
follow-ups) is the blast radius of a single choice — hand-rolled JSON +
`flock` + CAS tokens. SQLite in WAL mode would have supplied atomicity,
durability, and cross-process serialization from a battle-tested library,
deleting most of those commits. **Acquire guarantees before implementing
them.** If a pre-extraction simplification pass is ever scheduled,
evaluating SQLite for the state store is the highest-leverage candidate —
judge it only by whether it removes substantial code while keeping every
tested guarantee green.

Also note the recursion pattern the tail exhibited, because it is
machine-detectable and worth a tripwire rule for future sessions:
**lock → reentrancy guard → fork-safety of lock → raw-fork child-safety of
fork-safety** — each defensive layer spawned edge cases that existed only
because of the layer itself. Tripwire rules for agents working in this
repo going forward:

- If three consecutive commits each fix code introduced by the previous
  commit in the same session, halt and report instead of continuing.
- If any module grows more than ~50% in a non-feature phase, require
  justification against acquiring the capability from an existing library
  before proceeding.
- Findings below the blocking severity floor go to `known-limitations.md`
  or backlog, never to immediate fixes (the bounded-review policy in
  `development-status.md` already encodes this; keep it).

## Process observations for future work (recorded, not blocking)

- **Commit message specificity.** The afternoon's messages (`fix(review): …`
  repeated) made genuinely distinct fixes indistinguishable from a churn
  loop to any outside reader. Name the closed hole class in each message.
- **Severity accounting in review history.** `development-status.md`
  correctly states "no known finding remains open"; what justifies trusting
  that statement is that findings decreased monotonically in severity over
  the session (authorization bypasses → races → error-reporting taxonomy).
  Preserve that fact where open-finding claims are made.
- **Evidence environmental dependence.** Restate prerequisites with every
  recorded test count (see P1).
- **YAGNI enforcement gap.** `AGENTS.md` line 26 ("No unrequested
  abstractions … speculative hooks") was violated by the tail while being
  quoted by it. Instructions alone did not constrain the instruction
  follower; budgets and tripwires (above, and the bounded-review policy)
  are the workable controls.
- **Deprecation gate confirmation.** Gate 4 of the release roadmap
  contemplates deprecating `dotgemini`. It is correctly human-gated; flag
  for explicit human confirmation before that gate is ever entered, since
  coexistence (dotgemini for Gemini/Antigravity, standalone package for
  goose) is a legitimate permanent end state.

## Affirmed — do not litigate or undo

- Closing parser hardening at `14acb83` was the right call; the blocked-form
  list is an accident-prevention list and is done.
- The concurrency work (flock + reload-under-lock + CAS token + atomic
  approval/token checks) fixed a real lost-update class; keep it.
- Structured partial-push reporting (`phase`/`observed_sha`/`cause`) is
  correct operator-facing design; keep the taxonomy.
- The bounded final-review policy and next-session runbook in
  `development-status.md` match what this analysis would have prescribed.
- `known-limitations.md` and `capability-parity.md` are unusually honest
  documents; their "advisory, not enforcement" framing is a feature and
  should remain verbatim in effect.

## Backlog checklist (checkable; nothing here expands scope)

- [x] P1: `skipif` on the two goose-binary packaging tests **or** goose
      install step in `ci.yml` — resolved with `skipif`; goose-less default
      pytest reports 233 passed and 2 skipped.
- [x] P1: runbook line in `development-status.md` documenting the goose
      prerequisite for the default pytest count.
- [ ] P2: record the deployment hardening profile as optional guidance
      (installation docs), explicitly marked external to this repo.
- [ ] P3.1: narrow the three `except Exception` sites in `lifecycle.py`.
- [ ] P3.4: document the reentrancy fail-fast behavior in
      `known-limitations.md`.
- [ ] P3: (optional, pre-extraction) deletion-oriented simplification
      pass; evaluate SQLite/WAL for the state store against the strict
      criterion "removes code, keeps all tested guarantees."
- [ ] Process: commit-message specificity norm; severity-trend sentence in
      review histories; environmental prerequisites beside evidence counts;
      human confirmation recorded before the deprecation gate.

*End of analysis. This document asks for no further review passes on
implementation code.*
