---
name: session-sync
description: Synchronize active Antigravity CLI conversation sessions across machines using a shared Git remote.
---

# Session Synchronization

Use this skill when the user wants to sync, backup, push, or restore an Antigravity CLI conversation session, or continue a conversation on another computer.

## Key Rules

> [!IMPORTANT]
> - **Security/Permissions**: Always explain the git remote operations (`git push` / `git fetch` / `git stash` / `git reset`) in a separate turn and obtain explicit user consent before execution.
> - **Dirty State Handling**: If a pull operation detects uncommitted local changes, the script will return `{"status": "dirty", ...}`. You MUST stop, explain this to the user, and present the three choices: Abort, Stash, or Overwrite.
> - **Destructive branch alignment**: On pull, the script runs `git reset --hard <source-commit>` to align the destination branch to the pushed session's commit. This discards any **committed** local work on that branch that is ahead of the source commit — the dirty-state check above only guards **uncommitted** changes. Before pulling, warn the user if the destination branch may hold unpushed commits.

## Execution Workflows

### 1. Pushing the Current Session (Backup / Save)

1. Explain the action:
   - "I will package the current conversation transcript, artifacts, metadata, and any uncommitted workspace changes, and push them to a hidden Git ref (`refs/gemini-sessions/<session-id>`) on your remote repository."
2. Propose executing the push command:
   ```bash
   python3 ~/.gemini/skills/session-sync/scripts/sync_session.py push
   ```
3. After execution, the script will return JSON. Report success to the user and clearly display their **Conversation ID** (which they'll need on the destination computer).

---

### 2. Pulling and Restoring a Session (Restore / Continue)

1. Ask the user for the **Conversation ID** if they haven't provided it.
2. Explain the action:
   - "I will fetch the sync ref for conversation `<session-id>` from origin, align your local branch, apply the uncommitted changes patch, and restore the conversation log files in your CLI folder."
3. Propose executing the pull command:
   ```bash
   python3 ~/.gemini/skills/session-sync/scripts/sync_session.py pull <session-id>
   ```
4. **Interactive Dirty Workspace Flow**:
   - If the command returns `{"status": "dirty", ...}`:
     - Stop execution.
     - Present these options to the user:
       - **1. Abort**: Cancel the sync and keep current local changes.
       - **2. Stash**: Stash current local changes (`git stash -u`) and apply the incoming sync.
       - **3. Overwrite**: Discard current local changes (`git reset --hard` / `git clean -fd`) and apply the incoming sync.
     - Once the user selects their option, re-run the command with the correct flag:
       - For Stash: `python3 ~/.gemini/skills/session-sync/scripts/sync_session.py pull <session-id> --on-dirty stash`
       - For Overwrite: `python3 ~/.gemini/skills/session-sync/scripts/sync_session.py pull <session-id> --on-dirty overwrite`
5. Report the final success. The user can now restart the CLI in this session or proceed with the restored context.

---

### 3. Listing Synced Sessions (List / Show)

1. Propose executing the list command:
   ```bash
   python3 ~/.gemini/skills/session-sync/scripts/sync_session.py list
   ```
2. Present the JSON output formatted clearly to the user, displaying session IDs, creation timestamps (available only for local references), and local/remote status.

---

### 4. Clearing Synced Sessions (Delete / Prune)

1. Explain the action:
   - For a single session: "I will delete the Git refs for session `<session-id>` locally and on remote origin."
   - For all sessions: "I will locate all synced sessions locally and on remote origin, and delete their Git refs."
2. Propose executing the clear command:
   - Specific session:
     ```bash
     python3 ~/.gemini/skills/session-sync/scripts/sync_session.py clear <session-id>
     ```
   - All sessions:
     ```bash
     python3 ~/.gemini/skills/session-sync/scripts/sync_session.py clear --all
     ```
3. Report success and list the cleared session IDs.
