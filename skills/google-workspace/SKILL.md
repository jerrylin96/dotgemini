---
name: google-workspace
description: Manage Google Calendar events and Google Tasks. Use when listing, creating, updating, or deleting calendar events or tasks.
---

# Google Workspace (Calendar & Tasks) Integration

Allows Antigravity CLI agents to interact with Google Calendar and Google Tasks APIs.

## Authentication Setup

This skill relies on Google Application Default Credentials (ADC) with the correct scopes enabled.

If the user encounters authentication errors, ask them to run:
```bash
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/calendar,https://www.googleapis.com/auth/tasks"
```

---

## Execution & Environment Setup

To avoid polluting the base Python environment on a desktop, execute this skill's scripts within an isolated virtual environment containing `google-api-python-client` and `google-auth`.

### Option A: Run inside Workspace Dynamic Virtual Environment (Recommended for Agent/CLI Usage)
Antigravity CLI provides a built-in virtual environment runner that resolves dependencies from `requirements.txt` into a dynamic environment under `~/.gemini/tmp/`:
1. Ensure the workspace environment is resolved:
   ```bash
   python3 ~/.gemini/scripts/setup_review_env.py ~/.gemini
   ```
2. Execute any workspace integration command using `run_in_env.py`:
   ```bash
   python3 ~/.gemini/scripts/run_in_env.py ~/.gemini python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py auth-check
   ```

### Option B: Standalone Manual Setup
If executing commands manually in a standalone `uv` environment:
1. Create and activate a virtual environment:
   ```bash
   uv venv ~/.gemini/tmp/workspace_skill_env
   source ~/.gemini/tmp/workspace_skill_env/bin/activate
   ```
2. Install dependencies:
   ```bash
   uv pip install -r ~/.gemini/requirements.txt
   ```
3. Run the scripts directly:
   ```bash
   python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py auth-check
   ```

---

## Agent Usage & Commands

> [!IMPORTANT]
> **Safety Rule**: You MUST explicitly confirm with the user before performing any delete operations or bulk changes to calendar events or tasks.

All actions are executed by running the Python client within the workspace environment (e.g. prefixing with the dynamic environment runner `python3 ~/.gemini/scripts/run_in_env.py ~/.gemini python3` as shown below).

### 1. Google Calendar

#### List Events
Lists events starting from now (or a specified duration).
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py calendar list [--days N]
```

#### Create Event
Creates a new event on the primary calendar.
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py calendar create --title "Meeting Title" --start "2026-07-16T15:00:00Z" --end "2026-07-16T16:00:00Z" [--description "Description"]
```
*Note: Start and end times must include timezone offset (e.g. `2026-07-16T15:00:00Z` or `2026-07-16T15:00:00-04:00`).*

#### Update Event
Updates properties of an existing event.
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py calendar update --event-id "EVENT_ID" [--title "New Title"] [--start "YYYY-MM-DDTHH:MM:SSZ"] [--end "YYYY-MM-DDTHH:MM:SSZ"] [--description "New Desc"]
```

#### Delete Event
Deletes an event.
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py calendar delete --event-id "EVENT_ID"
```

---

### 2. Google Tasks

*Note: All task commands support an optional `--tasklist LIST_ID` argument (defaults to `@default`).*

#### List Tasks
Lists tasks from the default (or specified) task list.
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py tasks [--tasklist LIST_ID] list [--completed]
```

#### Create Task
Creates a new task.
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py tasks [--tasklist LIST_ID] create --title "Task Title" [--notes "Additional details"] [--due "2026-07-16"]
```
*Note: Due dates should be in YYYY-MM-DD format.*

#### Update Task
Updates properties or marks a task as completed/incomplete.
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py tasks [--tasklist LIST_ID] update --task-id "TASK_ID" [--title "New Title"] [--notes "New Notes"] [--due "New Due"] [--status "completed|needsAction"]
```
*Note: Due dates should be in YYYY-MM-DD format. Pass an empty string (`--due ""`) to clear the due date.*

#### Delete Task
Deletes a task.
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py tasks [--tasklist LIST_ID] delete --task-id "TASK_ID"
```

---

### 3. Timeline Planner (Goals to Timeline)

A specialized tool to decompose goals into scheduled timelines, resolving calendar conflicts by finding free blocks within working hours (Option B).

#### Step 1: Initialize Goals
Create a JSON configuration file under `artifacts/goals.json`. Example structure:
```json
{
  "tasklist_title": "Project Alpha",
  "timezone": "America/New_York",
  "start_date": "2026-07-18",
  "days_limit": 14,
  "working_hours": {
    "start": "09:00",
    "end": "17:00"
  },
  "tasks": [
    {
      "title": "Set up project structure",
      "notes": "Verify run scripts and output files.",
      "subtasks": [
        {
          "title": "Setup venv and dependencies",
          "duration_hours": 1.0
        },
        {
          "title": "Configure git and tooling config",
          "duration_hours": 1.0
        }
      ]
    },
    {
      "title": "Implement API endpoints",
      "duration_hours": 4,
      "notes": "Build tasklist and calendar integration routes."
    }
  ]
}
```

> [!NOTE]
> **Subtask Constraints:**
> - **Nesting Depth**: Google Tasks only supports at most one level of task nesting. Subtasks cannot contain nested grandchild tasks.
> - **Duration Ignore**: If a task defines a `subtasks` list, any `duration_hours` defined at the parent task level will be ignored. The calendar blocks are scheduled exclusively for the subtasks.

#### Step 2: Generate Proposed Timeline
Generates `artifacts/proposed_timeline.md` by identifying free slots on the primary calendar:
```bash
python3 ~/.gemini/skills/google-workspace/scripts/timeline_planner.py plan --goals-file artifacts/goals.json --proposed-file artifacts/proposed_timeline.md
```

#### Step 3: Review and Edit
The user reviews and edits `artifacts/proposed_timeline.md` (e.g. adjusting descriptions, due dates, or times).

> [!WARNING]
> **Indentation is Load-bearing:**
> The parser determines task hierarchies using indentation levels (tabs or spaces):
> - Parent Tasks: no indentation (indent < 2).
> - Subtasks: indented by at least 2 characters (spaces or tabs).
> - Subtask properties (Due, Notes): indented by at least 4 characters (spaces or tabs).
> Improper indentation will cause properties/subtasks to misattach or parse incorrectly.

#### Step 4: Apply Timeline
Provisions the Google TaskList, Google Tasks, and Google Calendar focus blocks:
```bash
python3 ~/.gemini/skills/google-workspace/scripts/timeline_planner.py apply --proposed-file artifacts/proposed_timeline.md --state-file artifacts/timeline_state.json
```

#### Step 5: Track Status
Checks task status from Google Tasks and automatically updates the markdown checklist:
```bash
python3 ~/.gemini/skills/google-workspace/scripts/timeline_planner.py status --proposed-file artifacts/proposed_timeline.md --state-file artifacts/timeline_state.json
```

