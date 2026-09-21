### Emit External Review Prompt (Spec Gate)

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

### Review Focus (Spec Gate)
Audit the feature specification in `integrate-git-signoff-48d1c2/spec.md`:
1. Completeness: Does the spec accurately cover all affected paths (deleting `signoff_mcp/`, updating `pyproject.toml`, `pytest.ini`, `scripts/sync_signoff_subtree.sh`, `AGENTS.md`, and test suites)?
2. Invariants: Are GSA v1.0 protocol guarantees and worktree circuit breakers preserved?
3. Ponytail Ladder: Are we avoiding unnecessary abstractions while ensuring clean migration?
```
