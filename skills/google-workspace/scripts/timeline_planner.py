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
import subprocess
from zoneinfo import ZoneInfo
from functools import lru_cache
from googleapiclient.errors import HttpError

# Add current directory to path to allow importing workspace_client
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from workspace_client import (
    get_credentials,
    build_calendar_service,
    build_tasks_service,
    fetch_tasklists,
    create_google_doc,
    share_google_doc,
    append_text_to_google_doc,
)


class Interval:
    """Represents a time interval for scheduling."""

    def __init__(self, start, end):
        self.start = start
        self.end = end

    def overlaps(self, other):
        return self.start < other.end and other.start < self.end


def parse_iso_datetime(dt_str):
    """Parses ISO-8601 datetime strings, enforcing timezone offsets."""
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(dt_str)
    except ValueError as e:
        raise ValueError(f"Invalid ISO-8601 format: {e}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(
            "Timezone offset/timezone indicator is required (e.g. -04:00 or Z). Naive datetimes are not allowed."
        )
    return dt


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
    """Parses proposed_timeline.md. Evaluates section presence and malformed entries."""
    lines = markdown_content.splitlines()
    tasklist_name = "My Goal Timeline"
    timezone_name = "UTC"
    tasks = []
    events = []
    errors = []

    current_parent_idx = None
    current_subtask_idx = None
    current_event = None
    mode = None

    seen_sections = set()

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("# Proposed Timeline"):
            continue
        elif stripped.startswith("## Metadata"):
            seen_sections.add("metadata")
            mode = "metadata"
            continue
        elif stripped.startswith("## Proposed Google Tasks"):
            seen_sections.add("tasks")
            mode = "tasks"
            continue
        elif stripped.startswith("## Proposed Calendar Events"):
            seen_sections.add("events")
            mode = "events"
            continue
        elif stripped.startswith("## Unscheduled Tasks"):
            mode = "unscheduled"
            continue
        elif stripped.startswith("## "):
            mode = None
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
            elif stripped.startswith("- **Target Start Date**:") or stripped.startswith(
                "- **Timeline State**:"
            ):
                pass
            else:
                errors.append(f"Line {idx}: Unrecognized metadata entry '{stripped}'.")
        elif mode == "tasks":
            # Match task header: "- [ ] **Task Title** <!-- task_id: ID -->"
            task_header_match = re.match(
                r"-\s+\[\s*([xX]?\s*)\]\s+\*\*(.*?)\*\*(?:\s*<!--\s*task_id:\s*(\S+)\s*-->)?$",
                stripped,
            )
            if task_header_match:
                new_task = {
                    "title": task_header_match.group(2).strip(),
                    "due": "",
                    "notes": "",
                    "id": task_header_match.group(3) or "",
                    "completed": bool(task_header_match.group(1).strip()),
                    "line_number": idx,
                    "is_parent": False,
                    "parent_idx": None,
                }
                
                # Check hierarchy based on indentation
                line_expanded = line.expandtabs(4)
                indent = len(line_expanded) - len(line_expanded.lstrip())
                if indent < 2:
                    # It's a parent / standalone task
                    new_task["is_parent"] = True
                    tasks.append(new_task)
                    current_parent_idx = len(tasks) - 1
                    current_subtask_idx = None
                else:
                    # It's a subtask
                    if current_parent_idx is None:
                        errors.append(f"Line {idx}: Subtask found without a parent task.")
                        continue
                    new_task["is_parent"] = False
                    new_task["parent_idx"] = current_parent_idx
                    tasks.append(new_task)
                    current_subtask_idx = len(tasks) - 1
            elif current_parent_idx is not None:
                # Property line
                is_due = stripped.startswith("- **Due**:") or stripped.startswith("- **due**:")
                is_notes = stripped.startswith("- **Notes**:") or stripped.startswith("- **notes**:")
                
                if is_due or is_notes:
                    val = stripped.split(":", 1)[1].strip()
                    line_expanded = line.expandtabs(4)
                    indent = len(line_expanded) - len(line_expanded.lstrip())
                    # Level 2 properties (indent >= 4) belong to subtask
                    if current_subtask_idx is not None and indent >= 4:
                        target_task = tasks[current_subtask_idx]
                    else:
                        target_task = tasks[current_parent_idx]
                        
                    if is_due:
                        target_task["due"] = val
                    else:
                        target_task["notes"] = val
                else:
                    errors.append(
                        f"Line {idx}: Unrecognized task property line '{stripped}'."
                    )
            else:
                errors.append(
                    f"Line {idx}: Malformed task entry. Expected task header: '- [ ] **Title**'. Got: '{stripped}'."
                )
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
                    "line_number": idx,
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
                else:
                    errors.append(
                        f"Line {idx}: Unrecognized event property line '{stripped}' under event '{current_event['summary']}'."
                    )
            else:
                errors.append(
                    f"Line {idx}: Malformed event entry. Expected event header: '- **Event**: Title'. Got: '{stripped}'."
                )

    if current_event:
        events.append(current_event)

    # Validate section presence
    if "metadata" not in seen_sections:
        errors.append("Missing required markdown section: '## Metadata'")
    if "tasks" not in seen_sections:
        errors.append("Missing required markdown section: '## Proposed Google Tasks'")
    if "events" not in seen_sections:
        errors.append(
            "Missing required markdown section: '## Proposed Calendar Events'"
        )

    return {
        "tasklist_name": tasklist_name,
        "timezone": timezone_name,
        "tasks": tasks,
        "events": events,
        "errors": errors,
    }


def preflight_validate_timeline(plan_data):
    """Validates the complete parsed Markdown plan before calling Google APIs."""
    errors = list(plan_data.get("errors", []))

    # Reject empty plans
    if not plan_data.get("tasks") and not plan_data.get("events"):
        errors.append(
            "Validation error: Proposed timeline is empty. Plan must contain at least one task or event."
        )

    # 1. Validate Metadata
    tasklist_name = plan_data.get("tasklist_name", "").strip()
    if not tasklist_name:
        errors.append("Metadata error: Task List Name cannot be empty.")

    timezone_name = plan_data.get("timezone", "UTC").strip()
    try:
        ZoneInfo(timezone_name)
    except Exception:
        errors.append(f"Metadata error: Invalid timezone '{timezone_name}'.")

    tasks_list = plan_data.get("tasks", [])
    parent_indices = {t.get("parent_idx") for t in tasks_list if t.get("parent_idx") is not None}

    # 2. Validate Tasks
    for i, task in enumerate(tasks_list):
        title = task.get("title", "").strip()
        if not title:
            errors.append(f"Task error at index {i}: Title cannot be empty.")

        due = task.get("due", "").strip()
        if not due:
            if i not in parent_indices:
                errors.append(f"Task '{title}' error: Due date cannot be empty.")
        else:
            try:
                datetime.datetime.strptime(due, "%Y-%m-%d")
            except ValueError:
                errors.append(
                    f"Task '{title}' error: Due date '{due}' must be in YYYY-MM-DD format."
                )

    # 3. Validate Events
    for i, event in enumerate(plan_data.get("events", [])):
        summary = event.get("summary", "").strip()
        if not summary:
            errors.append(f"Event error at index {i}: Summary cannot be empty.")

        start_str = event.get("start", "").strip()
        end_str = event.get("end", "").strip()

        if not start_str:
            errors.append(f"Event '{summary}' error: Start time is missing.")
        if not end_str:
            errors.append(f"Event '{summary}' error: End time is missing.")

        start_dt = None
        end_dt = None

        if start_str:
            try:
                start_dt = parse_iso_datetime(start_str)
            except ValueError as e:
                errors.append(
                    f"Event '{summary}' error: Start time '{start_str}' is invalid: {e}"
                )

        if end_str:
            try:
                end_dt = parse_iso_datetime(end_str)
            except ValueError as e:
                errors.append(
                    f"Event '{summary}' error: End time '{end_str}' is invalid: {e}"
                )

        if start_dt and end_dt:
            if end_dt <= start_dt:
                errors.append(
                    f"Event '{summary}' error: End time '{end_str}' must be strictly after start time '{start_str}'."
                )

    return errors


def atomic_write_file(file_path, content, is_json=False):
    """Writes content atomically to file_path using a temporary file and fsync."""
    parent_dir = os.path.dirname(os.path.abspath(file_path))
    try:
        os.makedirs(parent_dir, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Failed to create directory '{parent_dir}': {e}")

    temp_path = file_path + ".tmp"
    try:
        with open(temp_path, "w") as f:
            if is_json:
                json.dump(content, f, indent=2)
            else:
                if isinstance(content, list):
                    f.writelines(content)
                else:
                    f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, file_path)
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise RuntimeError(f"Atomic file write failed for '{file_path}': {e}")


def update_markdown_file_with_id(file_path, match_type, item_index, resource_id):
    """Rewrites the markdown file, appending the resource ID to the target item."""
    with open(file_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    current_idx = 0
    in_section = False

    for line in lines:
        stripped = line.strip()
        if match_type == "task":
            if stripped.startswith("## Proposed Google Tasks"):
                in_section = True
            elif stripped.startswith("## "):
                in_section = False

            if in_section:
                match = re.match(
                    r"(-\s+\[\s*[xX]?\s*\]\s+\*\*(.*?)\*\*)(?:\s*<!--\s*task_id:\s*(\S+)\s*-->)?$",
                    stripped,
                )
                if match:
                    if current_idx == item_index:
                        line = line.rstrip("\n")
                        line = re.sub(r"\s*<!--\s*task_id:\s*\S+\s*-->", "", line)
                        line = line + f" <!-- task_id: {resource_id} -->\n"
                    current_idx += 1
        elif match_type == "event":
            if stripped.startswith("## Proposed Calendar Events"):
                in_section = True
            elif stripped.startswith("## "):
                in_section = False

            if in_section:
                match = re.match(
                    r"(-\s+\*\*Event\*\*:\s*(.*?))(?:\s*<!--\s*event_id:\s*(\S+)\s*-->)?$",
                    stripped,
                )
                if match:
                    if current_idx == item_index:
                        line = line.rstrip("\n")
                        line = re.sub(r"\s*<!--\s*event_id:\s*\S+\s*-->", "", line)
                        line = line + f" <!-- event_id: {resource_id} -->\n"
                    current_idx += 1

        new_lines.append(line)

    # Perform atomic write to prevent truncation or data loss
    atomic_write_file(file_path, new_lines)


def update_markdown_state(file_path, new_state):
    """Updates the Timeline State metadata line in the markdown file atomically."""
    with open(file_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- **Timeline State**:") or stripped.startswith(
            "- \\*\\*Timeline State\\*\\*:"
        ):
            line = f"- **Timeline State**: {new_state}\n"
        new_lines.append(line)

    atomic_write_file(file_path, new_lines)


def update_json_state_file(state_file_path, tasklist_id, task_id=None, event_id=None):
    """Incrementally updates the JSON state file with the new IDs atomically."""
    state = {"tasklist_id": tasklist_id, "task_ids": [], "event_ids": []}
    if os.path.exists(state_file_path):
        try:
            with open(state_file_path, "r") as f:
                state = json.load(f)
        except Exception:
            pass

    if task_id and task_id not in state["task_ids"]:
        state["task_ids"].append(task_id)
    if event_id and event_id not in state["event_ids"]:
        state["event_ids"].append(event_id)

    atomic_write_file(state_file_path, state, is_json=True)


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
            
        subtasks_cfg = t.get("subtasks", [])
        has_subtasks = False
        if "subtasks" in t:
            if not isinstance(subtasks_cfg, list):
                print(f"Error: Task '{title}' has a 'subtasks' field that is not a list.", file=sys.stderr)
                sys.exit(1)
            if subtasks_cfg:
                has_subtasks = True

        if has_subtasks:
            if "duration_hours" in t:
                print(
                    f"Warning: Task '{title}' contains both 'subtasks' and 'duration_hours'. "
                    "The parent task's duration_hours will be ignored.",
                    file=sys.stderr,
                )

            # Validate subtasks
            for j, sub in enumerate(subtasks_cfg):
                if not isinstance(sub, dict):
                    print(f"Error: Subtask at index {j} under task '{title}' is not an object.", file=sys.stderr)
                    sys.exit(1)
                
                sub_title = sub.get("title", "").strip()
                if not sub_title:
                    print(f"Error: Subtask at index {j} under task '{title}' is missing a title.", file=sys.stderr)
                    sys.exit(1)

                if "subtasks" in sub:
                    print(
                        f"Error: Subtask '{sub_title}' under task '{title}' contains nested subtasks. "
                        "Google Tasks supports at most one level of task nesting.",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                sub_duration = sub.get("duration_hours", 1.0)
                try:
                    sub_duration = float(sub_duration)
                    if sub_duration <= 0:
                        raise ValueError
                except (ValueError, TypeError):
                    print(
                        f"Error: Subtask '{sub_title}' under task '{title}' must have a positive duration_hours.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        else:
            # Validate standalone task duration
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

    # 2. Resolve start date & planning horizon (clamped to today if past start_date is supplied)
    start_date_str = data.get("start_date")
    now_local = datetime.datetime.now(tz)
    today = now_local.date()
    if start_date_str:
        try:
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            print("Error: start_date must be in YYYY-MM-DD format.", file=sys.stderr)
            sys.exit(1)
        if start_date < today:
            print(
                f"Warning: start_date {start_date} is in the past. Clamping to today: {today}"
            )
            start_date = today
    else:
        start_date = today

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
        # Skip free/reminder events
        if item.get("transparency") == "transparent":
            continue

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

            # Intersect with the planning horizon range to avoid large out-of-bounds loops
            horizon_start = start_date
            horizon_end = start_date + datetime.timedelta(days=days_limit)

            intersect_start = max(start_date_val, horizon_start)
            intersect_end = min(end_date_val, horizon_end)

            curr_date = intersect_start
            while curr_date < intersect_end:
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
        subtasks_cfg = task_info.get("subtasks", [])
        if subtasks_cfg:
            # It's a parent task
            parent_task_entry = {
                "title": task_info["title"],
                "notes": task_info.get("notes", ""),
                "subtasks": []
            }
            # Schedule each subtask
            for sub_info in subtasks_cfg:
                duration_hours = float(sub_info.get("duration_hours", 1.0))
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
                    
                    if check_date == now_local.date():
                        working_start = max(working_start, now_local)
                        
                    slot = find_free_slot(
                        working_start, working_end, calendar_intervals, duration_td
                    )
                    if slot:
                        slot_start, slot_end = slot
                        parent_task_entry["subtasks"].append(
                            {
                                "title": sub_info["title"],
                                "due": check_date.strftime("%Y-%m-%d"),
                                "notes": sub_info.get("notes", ""),
                            }
                        )
                        proposed_events.append(
                            {
                                "summary": f"Focus: {sub_info['title']}",
                                "start": slot_start.isoformat(),
                                "end": slot_end.isoformat(),
                                "description": sub_info.get("notes", ""),
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
                            "title": f"{task_info['title']} -> {sub_info['title']}",
                            "duration_hours": duration_hours,
                            "notes": sub_info.get("notes", ""),
                        }
                    )
            # Add parent task to proposed_tasks if any of its subtasks were scheduled
            if parent_task_entry["subtasks"]:
                proposed_tasks.append(parent_task_entry)
        else:
            # Standalone task
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

    # Write Proposed Markdown (using atomic write)
    markdown_content = (
        f"# Proposed Timeline: {tasklist_name}\n\n"
        "## Metadata\n"
        f"- **Task List Name**: {tasklist_name}\n"
        f"- **Timezone**: {timezone_name}\n"
        f"- **Target Start Date**: {start_date.strftime('%Y-%m-%d')}\n"
        "- **Timeline State**: pending_approval\n\n"
        "## Proposed Google Tasks\n"
    )
    for task in proposed_tasks:
        if "subtasks" in task:
            markdown_content += f"- [ ] **{task['title']}**\n"
            if task.get("notes"):
                markdown_content += f"  - **Notes**: {task['notes']}\n"
            for sub in task["subtasks"]:
                markdown_content += f"  - [ ] **{sub['title']}**\n"
                markdown_content += f"    - **Due**: {sub['due']}\n"
                if sub.get("notes"):
                    markdown_content += f"    - **Notes**: {sub['notes']}\n"
        else:
            markdown_content += f"- [ ] **{task['title']}**\n"
            markdown_content += f"  - **Due**: {task['due']}\n"
            if task.get("notes"):
                markdown_content += f"  - **Notes**: {task['notes']}\n"

    markdown_content += "\n## Proposed Calendar Events\n"
    for event in proposed_events:
        markdown_content += f"- **Event**: {event['summary']}\n"
        markdown_content += f"  - **Start**: {event['start']}\n"
        markdown_content += f"  - **End**: {event['end']}\n"
        markdown_content += f"  - **Description**: {event['description']}\n"

    if unscheduled_tasks:
        markdown_content += "\n## Unscheduled Tasks\n"
        markdown_content += "*The following tasks could not be scheduled within the days limit due to calendar conflicts:*\n"
        for ut in unscheduled_tasks:
            markdown_content += f"- **{ut['title']}** ({ut['duration_hours']}h)\n"
            if ut["notes"]:
                markdown_content += f"  - **Notes**: {ut['notes']}\n"

    atomic_write_file(args.proposed_file, markdown_content)
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
        lines = f.readlines()

    # Parse and preflight validate
    plan_data = parse_proposed_timeline("".join(lines))
    validation_errors = preflight_validate_timeline(plan_data)
    if validation_errors:
        print(
            "Preflight Validation Failed! Correct issues before applying:",
            file=sys.stderr,
        )
        for error in validation_errors:
            print(f"- {error}", file=sys.stderr)
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

    # Setup timezones & API connection
    timezone_name = plan_data["timezone"]
    tz = ZoneInfo(timezone_name)

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

    # 2. Iterate and create Tasks/Events, writing back incrementally after each creation
    current_task_idx = 0
    current_event_idx = 0
    creation_errors = 0

    in_tasks = False
    in_events = False

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("## Proposed Google Tasks"):
            in_tasks = True
            in_events = False
            continue
        elif stripped.startswith("## Proposed Calendar Events"):
            in_tasks = False
            in_events = True
            continue
        elif stripped.startswith("## "):
            in_tasks = False
            in_events = False
            continue

        if in_tasks:
            match = re.match(
                r"-\s+\[\s*[xX]?\s*\]\s+\*\*(.*?)\*\*(?:\s*<!--\s*task_id:\s*(\S+)\s*-->)?$",
                stripped,
            )
            if match:
                task = plan_data["tasks"][current_task_idx]
                task_idx_to_update = current_task_idx
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
                        parent_id = None
                        if not task.get("is_parent") and task.get("parent_idx") is not None:
                            parent_idx = task["parent_idx"]
                            parent_task = plan_data["tasks"][parent_idx]
                            parent_id = parent_task.get("id")
                            if not parent_id:
                                print(
                                    f"Error: Parent task '{parent_task['title']}' has no Google Task ID (probably failed creation). "
                                    f"Skipping subtask '{task['title']}' to prevent creating it as a top-level task.",
                                    file=sys.stderr,
                                )
                                creation_errors += 1
                                continue

                        kwargs = {
                            "tasklist": tasklist_id,
                            "body": task_body
                        }
                        if parent_id:
                            kwargs["parent"] = parent_id

                        created_task = (
                            tasks_service.tasks()
                            .insert(**kwargs)
                            .execute()
                        )
                        task_id = created_task["id"]
                        task["id"] = task_id  # Update in memory for subtasks lookup
                    except Exception as e:
                        print(
                            f"Error creating task '{task['title']}': {e}",
                            file=sys.stderr,
                        )
                        creation_errors += 1
                        continue

                    # Attempt to persist state atomically (critical recovery path)
                    try:
                        update_markdown_file_with_id(
                            args.proposed_file, "task", task_idx_to_update, task_id
                        )
                        update_json_state_file(
                            args.state_file, tasklist_id, task_id=task_id
                        )
                    except Exception as e:
                        print(
                            f"CRITICAL STATE PERSISTENCE FAILURE after task '{task['title']}' creation: {e}",
                            file=sys.stderr,
                        )
                        print(
                            f"The task was successfully created with ID '{task_id}' on Google Tasks,",
                            file=sys.stderr,
                        )
                        print(
                            "but the local ID mapping could not be saved. Manual reconciliation is needed.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

        elif in_events:
            match = re.match(
                r"-\s+\*\*Event\*\*:\s*(.*?)(?:\s*<!--\s*event_id:\s*(\S+)\s*-->)?$",
                stripped,
            )
            if match:
                event = plan_data["events"][current_event_idx]
                event_idx_to_update = current_event_idx
                current_event_idx += 1

                if not event["id"]:
                    print(f"Creating Calendar Event: {event['summary']}")
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
                    except Exception as e:
                        print(
                            f"Error creating event '{event['summary']}': {e}",
                            file=sys.stderr,
                        )
                        creation_errors += 1
                        continue

                    # Attempt to persist state atomically (critical recovery path)
                    try:
                        update_markdown_file_with_id(
                            args.proposed_file, "event", event_idx_to_update, event_id
                        )
                        update_json_state_file(
                            args.state_file, tasklist_id, event_id=event_id
                        )
                    except Exception as e:
                        print(
                            f"CRITICAL STATE PERSISTENCE FAILURE after event '{event['summary']}' creation: {e}",
                            file=sys.stderr,
                        )
                        print(
                            f"The event was successfully created with ID '{event_id}' on Google Calendar,",
                            file=sys.stderr,
                        )
                        print(
                            "but the local ID mapping could not be saved. Manual reconciliation is needed.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

    # 3. Update timeline state in markdown based on partial vs. complete successes
    if creation_errors > 0:
        print(
            f"Apply finished with {creation_errors} failure(s). Marked state as partially_applied.",
            file=sys.stderr,
        )
        update_markdown_state(args.proposed_file, "partially_applied")
        sys.exit(1)
    else:
        update_markdown_state(args.proposed_file, "applied")
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
                r"-\s+\[\s*[xX]?\s*\]\s+\*\*(.*?)\*\*(?:\s*<!--\s*task_id:\s*(\S+)\s*-->)?$",
                stripped,
            )
            if match:
                task = plan_data["tasks"][current_task_idx]
                current_task_idx += 1

                if task["id"] and task["id"] in completed_statuses:
                    is_completed = completed_statuses[task["id"]]
                    status_char = "x" if is_completed else " "
                    indent = line[: line.find("-")]
                    comment_str = (
                        f" <!-- task_id: {task['id']} -->" if task["id"] else ""
                    )
                    line = (
                        f"{indent}- [{status_char}] **{task['title']}**{comment_str}\n"
                    )

        new_lines.append(line)

    atomic_write_file(args.proposed_file, new_lines)
    print(f"Status sync completed. Updated checklist in {args.proposed_file}")


@lru_cache(maxsize=16)
def get_project_info(cwd):
    try:
        git_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=cwd, stderr=subprocess.DEVNULL
        ).decode().strip()
        git_root = os.path.abspath(git_root)
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_root = os.path.abspath(cwd)
        
    base = os.path.basename(git_root)
    if not base:
        base = "root"
    return git_root, base


def resolve_artifact_path(path):
    """Resolves artifact paths to an Obsidian Vault if configured."""
    if not path:
        return path
    
    git_root, project_name = get_project_info(os.path.realpath(os.getcwd()))
    local_artifacts_dir = os.path.join(git_root, "artifacts")
    incoming_abs = path
    if not os.path.isabs(incoming_abs):
        incoming_abs = os.path.join(os.getcwd(), incoming_abs)
    abs_incoming = os.path.realpath(incoming_abs)
    is_artifact = False
    if abs_incoming == local_artifacts_dir:
        is_artifact = True
    elif abs_incoming.startswith(local_artifacts_dir + os.sep):
        is_artifact = True
        
    if not is_artifact:
        return path

    vault_path = os.environ.get("ANTIGRAVITY_OBSIDIAN_VAULT")

    if vault_path is None:
        settings_path = os.path.expanduser("~/.gemini/antigravity-cli/settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    if "obsidian_vault_path" in settings:
                        vault_path = settings["obsidian_vault_path"]
            except (json.JSONDecodeError, OSError) as e:
                sys.stderr.write(
                    f"Warning: Could not read obsidian_vault_path from settings.json: {e} - falling back.\n"
                )

    # Respect explicit opt-out
    if vault_path == "" or vault_path is False:
        return path

    if vault_path is not None and not isinstance(vault_path, str):
        return path

    if vault_path is not None:
        vault_path = os.path.expanduser(vault_path)

    if not vault_path:
        for fallback in ["~/Desktop/antigravity_vault", "~/Documents/antigravity_vault"]:
            expanded = os.path.expanduser(fallback)
            if os.path.isdir(expanded):
                vault_path = expanded
                break

    if not vault_path:
        return path

    # Blocker 1: Validate vault path starts with user's HOME directory
    real_vault = os.path.realpath(vault_path)
    real_home = os.path.realpath(os.path.expanduser("~"))
    try:
        if os.path.commonpath([real_home, real_vault]) != real_home:
            sys.stderr.write(
                f"Warning: Obsidian Vault path '{vault_path}' is outside user's HOME directory. "
                "Falling back to local workspace artifacts.\n"
            )
            return path
    except ValueError as e:
        sys.stderr.write(
            f"Warning: Safety check failed for vault path '{vault_path}': {e}. "
            "Falling back to local workspace artifacts.\n"
        )
        return path

    # Resolve project-based path
    relative_part = os.path.relpath(abs_incoming, local_artifacts_dir)
    resolved = os.path.join(vault_path, "Projects", project_name, relative_part)
    
    # If the resolved vault file does not exist, but the original local path does exist,
    # fall back to the local path to prevent crashes on existing files.
    if not os.path.exists(resolved) and os.path.exists(abs_incoming):
        return abs_incoming
        
    return resolved


def handle_publish_doc(args):
    """Publishes timeline markdown (and optional postmortems) to Google Docs and shares with stakeholders."""
    if not getattr(args, "proposed_file", None) or not args.proposed_file.strip():
        print("Error: --proposed-file must not be empty.", file=sys.stderr)
        sys.exit(1)

    file_path = resolve_artifact_path(args.proposed_file)
    if not os.path.exists(file_path):
        print(f"Error: Proposed timeline file not found at {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    creds = get_credentials()

    try:
        if args.doc_id:
            doc_id = args.doc_id
            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            append_text = f"\n\n--- Revision / Postmortem Update ({timestamp}) ---\n\n{content}"
            append_text_to_google_doc(creds, doc_id, append_text)
            print(f"Appended timeline update to existing Google Doc ID: {doc_id}")
        else:
            title = args.title or "Project Timeline & Execution Plan"
            doc_id, doc_url = create_google_doc(creds, title)
            append_text_to_google_doc(creds, doc_id, content)
            print(f"Published Timeline to new Google Doc ID: {doc_id}")

        if args.share:
            emails = [e.strip() for e in args.share.split(",") if e.strip()]
            shared = share_google_doc(creds, doc_id, emails, role=args.role)
            print(f"Shared document with {len(shared)} stakeholder(s) as {args.role}.")

        print(f"Google Doc URL: {doc_url}")
    except HttpError as e:
        if e.resp.status == 403 and args.doc_id:
            print(f"Error publishing to Google Doc: Access forbidden (403). Note: under 'drive.file' scope, --doc-id must be a document created by this tool. Details: {e}", file=sys.stderr)
        else:
            print(f"Error publishing to Google Doc: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error publishing to Google Doc: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Google Workspace Timeline Planner & Publisher."
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

    # publish-doc subcommand
    publish_parser = subparsers.add_parser(
        "publish-doc", help="Publish timeline and postmortems to a shared Google Doc."
    )
    publish_parser.add_argument(
        "--proposed-file",
        default="artifacts/proposed_timeline.md",
        help="Path to proposed markdown timeline.",
    )
    publish_parser.add_argument(
        "--doc-id",
        help="Existing Google Doc ID to append revision/postmortem update.",
    )
    publish_parser.add_argument(
        "--title",
        default="Project Timeline & Execution Plan",
        help="Title of the new Google Doc (defaults to 'Project Timeline & Execution Plan').",
    )
    publish_parser.add_argument(
        "--share",
        help="Comma-separated emails to share the Google Doc with (e.g. boss@co.com,team@co.com).",
    )
    publish_parser.add_argument(
        "--role",
        choices=["reader", "commenter", "writer"],
        default="reader",
        help="Stakeholder permission role (default: reader).",
    )
    publish_parser.set_defaults(func=handle_publish_doc)

    args = parser.parse_args()
    
    # Resolve artifacts paths dynamically to support Obsidian Vault
    # First, make relative artifact paths absolute relative to getcwd().
    # This prevents directory-shifting inconsistency when changing cwd.
    for attr in ["goals_file", "proposed_file", "state_file"]:
        if getattr(args, attr, None) is not None:
            val = getattr(args, attr)
            if not os.path.isabs(val):
                val = os.path.abspath(val)
            if attr == "proposed_file":
                val = resolve_artifact_path(val)
            setattr(args, attr, val)

    args.func(args)


if __name__ == "__main__":
    main()
