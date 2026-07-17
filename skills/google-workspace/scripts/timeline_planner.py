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


def fetch_tasklists(tasks_service):
    """Fetches all Google Task Lists with pagination support."""
    tasklists = []
    page_token = None
    while True:
        result = tasks_service.tasklists().list(pageToken=page_token).execute()
        tasklists.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return tasklists


def parse_proposed_timeline(markdown_content):
    """Parses human-readable proposed_timeline.md into structured dict."""
    lines = markdown_content.splitlines()
    tasklist_name = "My Goal Timeline"
    timezone_name = "UTC"
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
        elif stripped.startswith("## Unscheduled Tasks"):
            mode = "unscheduled"
            continue

        if mode == "metadata":
            if stripped.startswith("- **Task List Name**:") or stripped.startswith(
                "- **Tasklist Name**:"
            ):
                tasklist_name = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- **Timezone**:") or stripped.startswith(
                "- **timezone**:"
            ):
                timezone_name = stripped.split(":", 1)[1].strip()
        elif mode == "tasks":
            # Match task header: "- [ ] **Task Title** <!-- task_id: ID -->"
            task_header_match = re.match(
                r"-\s+\[\s*([xX]?\s*)\]\s+\*\*(.*?)\*\*(?:\s*<!--\s*task_id:\s*(\S+)\s*-->)?$",
                stripped,
            )
            if task_header_match:
                if current_task:
                    tasks.append(current_task)
                current_task = {
                    "title": task_header_match.group(2).strip(),
                    "due": "",
                    "notes": "",
                    "id": task_header_match.group(3) or "",
                    "completed": bool(task_header_match.group(1).strip()),
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
            event_header_match = re.match(
                r"-\s+\*\*Event\*\*:\s*(.*?)(?:\s*<!--\s*event_id:\s*(\S+)\s*-->)?$",
                stripped,
            )
            if event_header_match:
                if current_event:
                    events.append(current_event)
                current_event = {
                    "summary": event_header_match.group(1).strip(),
                    "start": "",
                    "end": "",
                    "description": "",
                    "id": event_header_match.group(2) or "",
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

    return {
        "tasklist_name": tasklist_name,
        "timezone": timezone_name,
        "tasks": tasks,
        "events": events,
    }


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

    # 1. Validation of goals input
    tasklist_name = data.get("tasklist_title", "New Goal Timeline").strip()
    if not tasklist_name:
        print("Error: tasklist_title cannot be empty.", file=sys.stderr)
        sys.exit(1)

    timezone_name = data.get("timezone", "UTC").strip()
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        print(f"Error: Invalid timezone '{timezone_name}'", file=sys.stderr)
        sys.exit(1)

    days_limit = data.get("days_limit", 14)
    try:
        days_limit = int(days_limit)
        if days_limit <= 0:
            raise ValueError
    except (ValueError, TypeError):
        print("Error: days_limit must be a positive integer.", file=sys.stderr)
        sys.exit(1)

    working_hours_cfg = data.get("working_hours", {})
    try:
        working_start_time = datetime.time.fromisoformat(
            working_hours_cfg.get("start", "09:00")
        )
        working_end_time = datetime.time.fromisoformat(
            working_hours_cfg.get("end", "17:00")
        )
    except ValueError as e:
        print(f"Error: Invalid working_hours format: {e}", file=sys.stderr)
        sys.exit(1)

    if working_start_time >= working_end_time:
        print(
            "Error: working_hours start time must be strictly before end time.",
            file=sys.stderr,
        )
        sys.exit(1)

    tasks_cfg = data.get("tasks", [])
    if not tasks_cfg:
        print("Error: tasks list cannot be empty.", file=sys.stderr)
        sys.exit(1)

    for i, t in enumerate(tasks_cfg):
        title = t.get("title", "").strip()
        if not title:
            print(f"Error: Task at index {i} is missing a title.", file=sys.stderr)
            sys.exit(1)
        duration = t.get("duration_hours", 1.0)
        try:
            duration = float(duration)
            if duration <= 0:
                raise ValueError
        except (ValueError, TypeError):
            print(
                f"Error: Task '{title}' must have a positive duration_hours.",
                file=sys.stderr,
            )
            sys.exit(1)

    # 2. Resolve start date & planning horizon
    start_date_str = data.get("start_date")
    now_local = datetime.datetime.now(tz)
    if start_date_str:
        try:
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            print("Error: start_date must be in YYYY-MM-DD format.", file=sys.stderr)
            sys.exit(1)
    else:
        start_date = now_local.date()

    # 3. Fetch Calendar Busy Times
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
            # All-day event range
            start_date_val = datetime.datetime.strptime(
                start_data["date"], "%Y-%m-%d"
            ).date()
            end_date_val = datetime.datetime.strptime(
                end_data["date"], "%Y-%m-%d"
            ).date()
            # Expand busy times across multi-day range [start.date, end.date)
            curr_date = start_date_val
            while curr_date < end_date_val:
                ev_start = datetime.datetime.combine(
                    curr_date, working_start_time, tzinfo=tz
                )
                ev_end = datetime.datetime.combine(
                    curr_date, working_end_time, tzinfo=tz
                )
                calendar_intervals.append(Interval(ev_start, ev_end))
                curr_date += datetime.timedelta(days=1)
        elif "dateTime" in start_data:
            ev_start = parse_iso_datetime(start_data["dateTime"]).astimezone(tz)
            ev_end = parse_iso_datetime(end_data["dateTime"]).astimezone(tz)
            calendar_intervals.append(Interval(ev_start, ev_end))

    # Decompose and Schedule Tasks
    proposed_tasks = []
    proposed_events = []
    unscheduled_tasks = []

    current_schedule_date = start_date

    for task_info in tasks_cfg:
        duration_hours = float(task_info.get("duration_hours", 1.0))
        duration_td = datetime.timedelta(hours=duration_hours)

        scheduled = False
        attempts = 0
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

            # Avoid scheduling in the past if start_date is today
            if check_date == now_local.date():
                working_start = max(working_start, now_local)

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
                calendar_intervals.append(Interval(slot_start, slot_end))
                current_schedule_date = check_date
                scheduled = True
            else:
                attempts += 1

        if not scheduled:
            unscheduled_tasks.append(
                {
                    "title": task_info["title"],
                    "duration_hours": duration_hours,
                    "notes": task_info.get("notes", ""),
                }
            )

    # Write Proposed Markdown
    os.makedirs(os.path.dirname(os.path.abspath(args.proposed_file)), exist_ok=True)
    with open(args.proposed_file, "w") as f:
        f.write(f"# Proposed Timeline: {tasklist_name}\n\n")
        f.write("## Metadata\n")
        f.write(f"- **Task List Name**: {tasklist_name}\n")
        f.write(f"- **Timezone**: {timezone_name}\n")
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

        if unscheduled_tasks:
            f.write("\n## Unscheduled Tasks\n")
            f.write(
                "*The following tasks could not be scheduled within the days limit due to calendar conflicts:*\n"
            )
            for ut in unscheduled_tasks:
                f.write(f"- **{ut['title']}** ({ut['duration_hours']}h)\n")
                if ut["notes"]:
                    f.write(f"  - **Notes**: {ut['notes']}\n")

    print(f"Proposed timeline draft successfully written to {args.proposed_file}")


def handle_apply(args):
    """Parses proposed_timeline.md and provisions Workspace tasks/events."""
    if not os.path.exists(args.proposed_file):
        print(
            f"Error: Proposed timeline file not found at {args.proposed_file}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Explicit Safety Confirmation
    if not args.confirm:
        print(
            "WARNING: This will provision Google Tasks and Calendar events to your account."
        )
        confirm = input("Are you sure you want to proceed? (y/N): ")
        if confirm.lower() not in ("y", "yes"):
            print("Abort.")
            sys.exit(0)

    with open(args.proposed_file, "r") as f:
        lines = f.readlines()

    plan_data = parse_proposed_timeline("".join(lines))

    # Validation: working range end after start, start/end date timezone offsets
    timezone_name = plan_data["timezone"]
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        print(
            f"Error: Invalid timezone '{timezone_name}' in markdown metadata.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Offset extraction for Google Tasks due dates (non-UTC offset shifts)
    now_local = datetime.datetime.now(tz)
    tz_offset_str = now_local.strftime("%z")
    if tz_offset_str and len(tz_offset_str) == 5:
        tz_offset_str = tz_offset_str[:3] + ":" + tz_offset_str[3:]
    else:
        tz_offset_str = "Z"

    creds = get_credentials()
    tasks_service = build_tasks_service(creds)
    cal_service = build_calendar_service(creds)

    # 1. Resolve/Create Google TaskList (with pagination)
    tasklist_name = plan_data["tasklist_name"]
    existing_lists = fetch_tasklists(tasks_service)

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

    # 2. Iterate and create Tasks/Events in place in the markdown (Idempotent & Edit-Resilient)
    new_lines = []
    current_task_idx = 0
    current_event_idx = 0

    in_tasks = False
    in_events = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue

        if stripped.startswith("## Proposed Google Tasks"):
            in_tasks = True
            in_events = False
            new_lines.append(line)
            continue
        elif stripped.startswith("## Proposed Calendar Events"):
            in_tasks = False
            in_events = True
            new_lines.append(line)
            continue
        elif stripped.startswith("## "):
            in_tasks = False
            in_events = False
            new_lines.append(line)
            continue

        if in_tasks:
            match = re.match(
                r"(-\s+\[\s*[xX]?\s*\]\s+\*\*(.*?)\*\*)(?:\s*<!--\s*task_id:\s*(\S+)\s*-->)?",
                stripped,
            )
            if match:
                task = plan_data["tasks"][current_task_idx]
                current_task_idx += 1

                if not task["id"]:
                    print(f"Creating Google Task: {task['title']}")
                    task_body = {"title": task["title"]}
                    if task.get("notes"):
                        task_body["notes"] = task["notes"]
                    if task.get("due"):
                        # Fix due timezone shift: Use 12:00:00 local time
                        task_body["due"] = f"{task['due']}T12:00:00{tz_offset_str}"

                    try:
                        created_task = (
                            tasks_service.tasks()
                            .insert(tasklist=tasklist_id, body=task_body)
                            .execute()
                        )
                        task_id = created_task["id"]
                        line = line.rstrip("\n") + f" <!-- task_id: {task_id} -->\n"
                    except Exception as e:
                        print(
                            f"Error creating task '{task['title']}': {e}",
                            file=sys.stderr,
                        )
            new_lines.append(line)

        elif in_events:
            match = re.match(
                r"(-\s+\*\*Event\*\*:\s*(.*?))(?:\s*<!--\s*event_id:\s*(\S+)\s*-->)?",
                stripped,
            )
            if match:
                event = plan_data["events"][current_event_idx]
                current_event_idx += 1

                if not event["id"]:
                    print(f"Creating Calendar Event: {event['summary']}")
                    # Validate timestamps have timezone offset
                    try:
                        parse_iso_datetime(event["start"])
                        parse_iso_datetime(event["end"])
                    except ValueError as e:
                        print(
                            f"Error: Invalid event time format for '{event['summary']}': {e}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    event_body = {
                        "summary": event["summary"],
                        "start": {"dateTime": event["start"]},
                        "end": {"dateTime": event["end"]},
                    }
                    if event.get("description"):
                        event_body["description"] = event["description"]

                    try:
                        created_event = (
                            cal_service.events()
                            .insert(calendarId="primary", body=event_body)
                            .execute()
                        )
                        event_id = created_event["id"]
                        line = line.rstrip("\n") + f" <!-- event_id: {event_id} -->\n"
                    except Exception as e:
                        print(
                            f"Error creating event '{event['summary']}': {e}",
                            file=sys.stderr,
                        )
            new_lines.append(line)
        else:
            # Metadata or state lines
            if stripped.startswith("- **Timeline State**:") or stripped.startswith(
                "- \\*\\*Timeline State\\*\\*:"
            ):
                line = "- **Timeline State**: applied\n"
            new_lines.append(line)

    # Save modified proposed_timeline.md back
    with open(args.proposed_file, "w") as f:
        f.writelines(new_lines)

    # Collect created IDs for backwards compatible JSON state file
    updated_plan_data = parse_proposed_timeline("".join(new_lines))
    state = {
        "tasklist_id": tasklist_id,
        "task_ids": [t["id"] for t in updated_plan_data["tasks"] if t["id"]],
        "event_ids": [e["id"] for e in updated_plan_data["events"] if e["id"]],
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.state_file)), exist_ok=True)
    with open(args.state_file, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Timeline successfully applied! State saved to {args.state_file}")


def handle_status(args):
    """Syncs task progress from Google Tasks and updates markdown checklist."""
    if not os.path.exists(args.proposed_file):
        print(
            f"Error: Proposed timeline file not found at {args.proposed_file}",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(args.proposed_file, "r") as f:
        lines = f.readlines()

    plan_data = parse_proposed_timeline("".join(lines))
    tasklist_name = plan_data["tasklist_name"]

    tasklist_id = None
    if os.path.exists(args.state_file):
        try:
            with open(args.state_file, "r") as f:
                state = json.load(f)
                tasklist_id = state.get("tasklist_id")
        except Exception:
            pass

    creds = get_credentials()
    tasks_service = build_tasks_service(creds)

    if not tasklist_id:
        tasklists = fetch_tasklists(tasks_service)
        for item in tasklists:
            if item["title"] == tasklist_name:
                tasklist_id = item["id"]
                break

    if not tasklist_id:
        print(
            f"Error: Could not find Task List '{tasklist_name}' on Google Tasks.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Fetch status for all task IDs found in the markdown
    completed_statuses = {}
    for task in plan_data["tasks"]:
        if task["id"]:
            try:
                t = (
                    tasks_service.tasks()
                    .get(tasklist=tasklist_id, task=task["id"])
                    .execute()
                )
                completed_statuses[task["id"]] = t["status"] == "completed"
            except Exception as e:
                print(
                    f"Warning: Could not fetch status for task ID {task['id']}: {e}",
                    file=sys.stderr,
                )

    # Re-write the lines with correct checkbox state
    new_lines = []
    current_task_idx = 0
    in_tasks = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Proposed Google Tasks"):
            in_tasks = True
        elif stripped.startswith("## "):
            in_tasks = False

        if in_tasks:
            match = re.match(
                r"(-\s+\[\s*)([xX]?\s*)(\]\s+\*\*(.*?)\*\*(?:\s*<!--\s*task_id:\s*(\S+)\s*-->)?)",
                line,
            )
            if match:
                prefix = match.group(1)
                suffix = match.group(3)
                task = plan_data["tasks"][current_task_idx]
                current_task_idx += 1

                if task["id"] and task["id"] in completed_statuses:
                    is_completed = completed_statuses[task["id"]]
                    status_char = "x" if is_completed else " "
                    line = f"{prefix}{status_char}{suffix}\n"

        new_lines.append(line)

    with open(args.proposed_file, "w") as f:
        f.writelines(new_lines)

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
    apply_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm execution without interactive prompt.",
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
