#!/usr/bin/env python3
"""Google Workspace Timeline Planner.

Decomposes and schedules tasks onto Google Tasks and Google Calendar.
"""

import argparse
import datetime
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

# Add current directory to path to allow importing workspace_client
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from workspace_client import (
    get_credentials,
    build_calendar_service,
    build_tasks_service,
)


class Interval:
    """Represents a time interval for scheduling."""

    def __init__(self, start, end):
        self.start = start
        self.end = end

    def overlaps(self, other):
        return self.start < other.end and other.start < self.end


def parse_iso_datetime(dt_str):
    """Parses ISO-8601 datetime strings with timezone offsets/Z."""
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(dt_str)


def find_free_slot(working_start, working_end, busy_intervals, duration_td):
    """Finds the first free slot of duration_td within working hours."""
    # Crop busy intervals to working hours and sort them
    cropped_busy = []
    for interval in busy_intervals:
        start = max(interval.start, working_start)
        end = min(interval.end, working_end)
        if start < end:
            cropped_busy.append(Interval(start, end))

    sorted_busy = sorted(cropped_busy, key=lambda x: x.start)

    # Merge overlapping or adjacent busy intervals
    merged_busy = []
    for interval in sorted_busy:
        if not merged_busy:
            merged_busy.append(Interval(interval.start, interval.end))
        else:
            last = merged_busy[-1]
            if interval.start <= last.end:
                last.end = max(last.end, interval.end)
            else:
                merged_busy.append(Interval(interval.start, interval.end))

    # Check gap before first busy interval
    current_time = working_start
    for interval in merged_busy:
        if interval.start - current_time >= duration_td:
            return current_time, current_time + duration_td
        current_time = max(current_time, interval.end)

    # Check gap after last busy interval
    if working_end - current_time >= duration_td:
        return current_time, current_time + duration_td

    return None


def fetch_calendar_events(calendar_service, time_min_iso, time_max_iso):
    """Fetches all primary calendar events between time_min and time_max."""
    events = []
    page_token = None
    while True:
        result = (
            calendar_service.events()
            .list(
                calendarId="primary",
                timeMin=time_min_iso,
                timeMax=time_max_iso,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            )
            .execute()
        )
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return events


def parse_proposed_timeline(markdown_content):
    """Parses human-readable proposed_timeline.md into structured dict."""
    lines = markdown_content.splitlines()
    tasklist_name = "My Goal Timeline"
    tasks = []
    events = []

    current_task = None
    current_event = None
    mode = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("# Proposed Timeline"):
            continue
        elif stripped.startswith("## Metadata"):
            mode = "metadata"
            continue
        elif stripped.startswith("## Proposed Google Tasks"):
            mode = "tasks"
            continue
        elif stripped.startswith("## Proposed Calendar Events"):
            mode = "events"
            continue

        if mode == "metadata":
            if stripped.startswith("- **Task List Name**:") or stripped.startswith(
                "- **Tasklist Name**:"
            ):
                tasklist_name = stripped.split(":", 1)[1].strip()
        elif mode == "tasks":
            # Match "- [ ] **Task Title**" or "- [x] **Task Title**"
            task_header_match = re.match(
                r"-\s+\[\s*[xX]?\s*\]\s+\*\*(.*?)\*\*", stripped
            )
            if task_header_match:
                if current_task:
                    tasks.append(current_task)
                current_task = {
                    "title": task_header_match.group(1).strip(),
                    "due": "",
                    "notes": "",
                }
            elif current_task:
                if stripped.startswith("- **Due**:") or stripped.startswith(
                    "- **due**:"
                ):
                    current_task["due"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("- **Notes**:") or stripped.startswith(
                    "- **notes**:"
                ):
                    current_task["notes"] = stripped.split(":", 1)[1].strip()
        elif mode == "events":
            event_header_match = re.match(r"-\s+\*\*Event\*\*:\s*(.*)", stripped)
            if event_header_match:
                if current_event:
                    events.append(current_event)
                current_event = {
                    "summary": event_header_match.group(1).strip(),
                    "start": "",
                    "end": "",
                    "description": "",
                }
            elif current_event:
                if stripped.startswith("- **Start**:") or stripped.startswith(
                    "- **start**:"
                ):
                    current_event["start"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("- **End**:") or stripped.startswith(
                    "- **end**:"
                ):
                    current_event["end"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("- **Description**:") or stripped.startswith(
                    "- **description**:"
                ):
                    current_event["description"] = stripped.split(":", 1)[1].strip()

    if current_task:
        tasks.append(current_task)
    if current_event:
        events.append(current_event)

    return {"tasklist_name": tasklist_name, "tasks": tasks, "events": events}


def handle_plan(args):
    """Computes free calendar slots and drafts proposed_timeline.md."""
    if not os.path.exists(args.goals_file):
        print(f"Error: Goals file not found at {args.goals_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.goals_file, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON goals file: {e}", file=sys.stderr)
            sys.exit(1)

    tasklist_name = data.get("tasklist_title", "New Goal Timeline")
    timezone_name = data.get("timezone", "UTC")
    tz = ZoneInfo(timezone_name)

    start_date_str = data.get("start_date")
    if start_date_str:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    else:
        start_date = datetime.datetime.now(tz).date()

    days_limit = int(data.get("days_limit", 14))
    working_start_time = datetime.time.fromisoformat(
        data.get("working_hours", {}).get("start", "09:00")
    )
    working_end_time = datetime.time.fromisoformat(
        data.get("working_hours", {}).get("end", "17:00")
    )

    # Fetch Calendar Busy Times
    creds = get_credentials()
    cal_service = build_calendar_service(creds)

    start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=tz)
    end_dt = start_dt + datetime.timedelta(days=days_limit)

    raw_events = fetch_calendar_events(
        cal_service, start_dt.isoformat(), end_dt.isoformat()
    )

    # Map raw events to Interval objects
    calendar_intervals = []
    for item in raw_events:
        start_data = item.get("start", {})
        end_data = item.get("end", {})

        if "date" in start_data:
            # All-day event
            ev_date = datetime.datetime.strptime(start_data["date"], "%Y-%m-%d").date()
            # Blocks entire working hours of that day
            ev_start = datetime.datetime.combine(ev_date, working_start_time, tzinfo=tz)
            ev_end = datetime.datetime.combine(ev_date, working_end_time, tzinfo=tz)
            calendar_intervals.append(Interval(ev_start, ev_end))
        elif "dateTime" in start_data:
            ev_start = parse_iso_datetime(start_data["dateTime"]).astimezone(tz)
            ev_end = parse_iso_datetime(end_data["dateTime"]).astimezone(tz)
            calendar_intervals.append(Interval(ev_start, ev_end))

    # Decompose and Schedule Tasks
    proposed_tasks = []
    proposed_events = []

    current_schedule_date = start_date

    for task_info in data.get("tasks", []):
        duration_hours = float(task_info.get("duration_hours", 1.0))
        duration_td = datetime.timedelta(hours=duration_hours)

        scheduled = False
        attempts = 0
        # Try to find a slot within the next days_limit days
        while not scheduled and attempts < days_limit:
            check_date = current_schedule_date + datetime.timedelta(days=attempts)
            if check_date >= (start_date + datetime.timedelta(days=days_limit)):
                break

            working_start = datetime.datetime.combine(
                check_date, working_start_time, tzinfo=tz
            )
            working_end = datetime.datetime.combine(
                check_date, working_end_time, tzinfo=tz
            )

            slot = find_free_slot(
                working_start, working_end, calendar_intervals, duration_td
            )
            if slot:
                slot_start, slot_end = slot
                proposed_tasks.append(
                    {
                        "title": task_info["title"],
                        "due": check_date.strftime("%Y-%m-%d"),
                        "notes": task_info.get("notes", ""),
                    }
                )
                proposed_events.append(
                    {
                        "summary": f"Focus: {task_info['title']}",
                        "start": slot_start.isoformat(),
                        "end": slot_end.isoformat(),
                        "description": task_info.get("notes", ""),
                    }
                )
                # Add slot to busy intervals so nothing else schedules there
                calendar_intervals.append(Interval(slot_start, slot_end))
                # Advance current_schedule_date to check_date for subsequent tasks
                current_schedule_date = check_date
                scheduled = True
            else:
                attempts += 1

        if not scheduled:
            print(
                f"Warning: Could not schedule task '{task_info['title']}' within days limit.",
                file=sys.stderr,
            )

    # Write Proposed Markdown
    os.makedirs(os.path.dirname(os.path.abspath(args.proposed_file)), exist_ok=True)
    with open(args.proposed_file, "w") as f:
        f.write(f"# Proposed Timeline: {tasklist_name}\n\n")
        f.write("## Metadata\n")
        f.write(f"- **Task List Name**: {tasklist_name}\n")
        f.write(f"- **Target Start Date**: {start_date.strftime('%Y-%m-%d')}\n")
        f.write("- **Timeline State**: pending_approval\n\n")

        f.write("## Proposed Google Tasks\n")
        for task in proposed_tasks:
            f.write(f"- [ ] **{task['title']}**\n")
            f.write(f"  - **Due**: {task['due']}\n")
            f.write(f"  - **Notes**: {task['notes']}\n")

        f.write("\n## Proposed Calendar Events\n")
        for event in proposed_events:
            f.write(f"- **Event**: {event['summary']}\n")
            f.write(f"  - **Start**: {event['start']}\n")
            f.write(f"  - **End**: {event['end']}\n")
            f.write(f"  - **Description**: {event['description']}\n")

    print(f"Proposed timeline draft successfully written to {args.proposed_file}")


def handle_apply(args):
    """Parses proposed_timeline.md and provisions Workspace tasks/events."""
    if not os.path.exists(args.proposed_file):
        print(
            f"Error: Proposed timeline file not found at {args.proposed_file}",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(args.proposed_file, "r") as f:
        markdown_content = f.read()

    plan_data = parse_proposed_timeline(markdown_content)

    creds = get_credentials()
    tasks_service = build_tasks_service(creds)
    cal_service = build_calendar_service(creds)

    # 1. Resolve/Create Google TaskList
    tasklist_name = plan_data["tasklist_name"]
    tasklists_result = tasks_service.tasklists().list().execute()
    existing_lists = tasklists_result.get("items", [])

    tasklist_id = None
    for item in existing_lists:
        if item["title"] == tasklist_name:
            tasklist_id = item["id"]
            break

    if not tasklist_id:
        print(f"Creating new task list: {tasklist_name}")
        new_list = (
            tasks_service.tasklists().insert(body={"title": tasklist_name}).execute()
        )
        tasklist_id = new_list["id"]
    else:
        print(f"Using existing task list: {tasklist_name} (ID: {tasklist_id})")

    # 2. Create Tasks
    created_task_ids = []
    for task in plan_data["tasks"]:
        print(f"Creating Task: {task['title']}")
        task_body = {"title": task["title"]}
        if task.get("notes"):
            task_body["notes"] = task["notes"]
        if task.get("due"):
            task_body["due"] = f"{task['due']}T00:00:00Z"

        created_task = (
            tasks_service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()
        )
        created_task_ids.append(created_task["id"])

    # 3. Create Calendar Events
    created_event_ids = []
    for event in plan_data["events"]:
        print(f"Creating Calendar Event: {event['summary']}")
        event_body = {
            "summary": event["summary"],
            "start": {"dateTime": event["start"]},
            "end": {"dateTime": event["end"]},
        }
        if event.get("description"):
            event_body["description"] = event["description"]

        created_event = (
            cal_service.events().insert(calendarId="primary", body=event_body).execute()
        )
        created_event_ids.append(created_event["id"])

    # Save mapping state
    state = {
        "tasklist_id": tasklist_id,
        "task_ids": created_task_ids,
        "event_ids": created_event_ids,
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.state_file)), exist_ok=True)
    with open(args.state_file, "w") as f:
        json.dump(state, f, indent=2)

    # Update state inside proposed_timeline.md
    updated_md = re.sub(
        r"- \*\*Timeline State\*\*:\s*\S+",
        "- **Timeline State**: applied",
        markdown_content,
    )
    with open(args.proposed_file, "w") as f:
        f.write(updated_md)

    print(f"Timeline successfully applied! State saved to {args.state_file}")


def handle_status(args):
    """Syncs task progress from Google Tasks and updates markdown checklist."""
    if not os.path.exists(args.state_file):
        print(f"Error: State file not found at {args.state_file}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.proposed_file):
        print(
            f"Error: Proposed timeline file not found at {args.proposed_file}",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(args.state_file, "r") as f:
        state = json.load(f)

    tasklist_id = state.get("tasklist_id")
    task_ids = state.get("task_ids", [])

    creds = get_credentials()
    tasks_service = build_tasks_service(creds)

    # Fetch tasks
    completed_statuses = {}
    for task_id in task_ids:
        try:
            task = (
                tasks_service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
            )
            completed_statuses[task["title"]] = task["status"] == "completed"
        except Exception as e:
            print(
                f"Warning: Could not fetch status for task {task_id}: {e}",
                file=sys.stderr,
            )

    # Update markdown file checklist
    with open(args.proposed_file, "r") as f:
        content = f.read()

    lines = content.splitlines()
    updated_lines = []
    in_tasks_section = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Proposed Google Tasks"):
            in_tasks_section = True
        elif stripped.startswith("## "):
            in_tasks_section = False

        if in_tasks_section:
            # Match "- [ ] **Task Title**" or "- [x] **Task Title**"
            match = re.match(r"(-\s+\[\s*)([xX]?\s*)(\]\s+\*\*(.*?)\*\*)", line)
            if match:
                prefix = match.group(1)
                suffix = match.group(3)
                title = match.group(4).strip()
                is_completed = completed_statuses.get(title, False)
                status_char = "x" if is_completed else " "
                line = f"{prefix}{status_char}{suffix}"

        updated_lines.append(line)

    with open(args.proposed_file, "w") as f:
        f.write("\n".join(updated_lines) + "\n")

    print(f"Status sync completed. Updated checklist in {args.proposed_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Google Workspace Timeline Planner CLI."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # plan subcommand
    plan_parser = subparsers.add_parser(
        "plan", help="Generate timeline draft from high-level goals."
    )
    plan_parser.add_argument(
        "--goals-file",
        default="artifacts/goals.json",
        help="Path to input goals JSON file.",
    )
    plan_parser.add_argument(
        "--proposed-file",
        default="artifacts/proposed_timeline.md",
        help="Path to output markdown timeline.",
    )
    plan_parser.set_defaults(func=handle_plan)

    # apply subcommand
    apply_parser = subparsers.add_parser(
        "apply", help="Provision calendar events and tasks from the proposed timeline."
    )
    apply_parser.add_argument(
        "--proposed-file",
        default="artifacts/proposed_timeline.md",
        help="Path to proposed markdown timeline.",
    )
    apply_parser.add_argument(
        "--state-file",
        default="artifacts/timeline_state.json",
        help="Path to write local ID tracking state.",
    )
    apply_parser.set_defaults(func=handle_apply)

    # status subcommand
    status_parser = subparsers.add_parser(
        "status", help="Sync checklist state from Google Tasks."
    )
    status_parser.add_argument(
        "--proposed-file",
        default="artifacts/proposed_timeline.md",
        help="Path to proposed markdown timeline.",
    )
    status_parser.add_argument(
        "--state-file",
        default="artifacts/timeline_state.json",
        help="Path to local ID tracking state.",
    )
    status_parser.set_defaults(func=handle_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
