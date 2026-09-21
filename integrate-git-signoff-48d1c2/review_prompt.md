### Emit External Review Prompt (Plan Gate)

```text
### Reviewer Identity & Session Continuity Directive
1. If you ALREADY established your REVIEWER_ID in an earlier turn of this session, YOU MUST REUSE IT. Do NOT generate a new ID.
2. If this is a fresh session, set your ID matching ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ (no '..' or '.lock'):
   export REVIEWER_ID="reviewer-$(head -c 3 /dev/urandom 2>/dev/null | xxd -p 2>/dev/null || echo $RANDOM)"
3. MANDATORY CHAT BANNER: In the very first lines of your chat response, you MUST print:
   ### 🪪 Reviewer Identification Proof
   - Reviewer ID: ${REVIEWER_ID}
   - Target SHA Audited: <sha>
   - Review File: reviews/${REVIEWER_ID}.md
   - Push Commit SHA: <your-push-sha or "pending — confirm post-push">

### Anti-Collision & Peer Isolation Invariants
1. FILE ISOLATION: You own ONLY reviews/${REVIEWER_ID}.md. Repository object-store reads (e.g. git show, git diff) of the audited branch and ephemeral review artifacts are permitted; WRITES to any file outside reviews/${REVIEWER_ID}.md are strictly forbidden. Never modify peer files in reviews/.
2. BRANCH ISOLATION: You are authorized to push ONLY to the specified review branch. Never push to main, gemini/integrate-git-signoff-48d1c2, or peer branches. Never force-push.
3. TARGETED STAGING: NEVER run git add . or git add -A. Run ONLY git add reviews/${REVIEWER_ID}.md.
4. ABORT ON FOREIGN CONFLICT: On conflict outside reviews/${REVIEWER_ID}.md, immediately run git rebase --abort. If caused by duplicate ID (add/add conflict on your own file), regenerate REVIEWER_ID and retry with a fresh file. If retries exhausted, fall back to chat markdown or scratch/external_reviews/<REVIEWER_ID>.md.
5. UNIVERSAL TAMPER TRIPWIRE: All files outside reviews/${REVIEWER_ID}.md and all branches outside your assigned review branch are strictly READ-ONLY / UNTOUCHABLE. Touching unauthorized files or branches triggers immediate session termination by the user and permanent disqualification.

### Inspection Target
git fetch origin main && BASE_SHA=$(git rev-parse FETCH_HEAD)
git fetch origin gemini/integrate-git-signoff-48d1c2 && git diff "${BASE_SHA}" FETCH_HEAD

### Review Focus (Plan Gate)
Audit the implementation plan in `integrate-git-signoff-48d1c2/plan.md`:
1. Task Slicing & Dependency Order: Are tasks atomic, touching ≤5 files each? Is the sequence correct (Subtree adoption -> Config/CI -> Documentation -> Tests)?
2. TDD Rigor: Does every slice define a failing RED test spec, GREEN implementation target, and exact verify command?
3. Execution Strategy: Is the strategy explicitly declared with single checkbox selection?
4. Full Test-Port Inventory: Are all required test files, helpers, fixtures, and contract checks accounted for?
```
