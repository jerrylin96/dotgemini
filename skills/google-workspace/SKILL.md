---
name: google-workspace
description: Manage Google Calendar events and Google Tasks. Allows listing, creating, and updating events and tasks.
---

# Google Workspace (Calendar & Tasks) Integration

Allows Antigravity CLI agents to interact with Google Calendar and Google Tasks APIs.

## Authentication Setup

This skill relies on Google Application Default Credentials (ADC) with the correct scopes enabled.

If the user encounters authentication errors, ask them to run:
```bash
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/calendar,https://www.googleapis.com/auth/tasks"
```

To verify authentication:
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py auth-check
```

---

## Agent Usage & Commands

All actions are executed by running the Python client:
`python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py`

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

#### Delete Task
Deletes a task.
```bash
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py tasks [--tasklist LIST_ID] delete --task-id "TASK_ID"
```
