#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Google Workspace Integration Client for Calendar and Tasks."""

import argparse
import datetime
import sys

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]


def get_credentials():
    """Obtains credentials with correct scopes."""
    try:
        credentials, _ = google.auth.default(scopes=SCOPES)
        return credentials
    except DefaultCredentialsError:
        print(
            "Error: Application Default Credentials (ADC) not found.\n"
            "Please run the following command to authenticate:\n\n"
            'gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/calendar,https://www.googleapis.com/auth/tasks"\n',
            file=sys.stderr,
        )
        sys.exit(1)


def build_calendar_service(credentials):
    """Builds the Calendar API service."""
    return build("calendar", "v3", credentials=credentials)


def build_tasks_service(credentials):
    """Builds the Tasks API service."""
    return build("tasks", "v1", credentials=credentials)


def handle_auth_check(args):
    """Checks authentication status and scope validity."""
    creds = get_credentials()
    try:
        # Build services and make lightweight read calls to verify actual credentials/scopes
        cal_service = build_calendar_service(creds)
        cal_service.events().list(calendarId="primary", maxResults=1).execute()

        tasks_service = build_tasks_service(creds)
        tasks_service.tasks().list(tasklist="@default", maxResults=1).execute()

        print("Success: Authenticated successfully with Google Workspace APIs.")
    except Exception as e:
        print(f"Auth check failed: {e}", file=sys.stderr)
        sys.exit(1)


def handle_calendar_list(args):
    """Lists calendar events."""
    creds = get_credentials()
    service = build_calendar_service(creds)

    now = datetime.datetime.now(datetime.timezone.utc)
    time_min = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    time_max = (now + datetime.timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        events = []
        page_token = None
        while True:
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    pageToken=page_token,
                )
                .execute()
            )
            events.extend(events_result.get("items", []))
            page_token = events_result.get("nextPageToken")
            if not page_token:
                break

        if not events:
            print("No upcoming events found.")
            return

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(
                f"[{start}] ID: {event['id']} | Title: {event.get('summary', '(No Title)')}"
            )
    except HttpError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_calendar_create(args):
    """Creates a calendar event."""
    creds = get_credentials()
    service = build_calendar_service(creds)

    event_body = {
        "summary": args.title,
        "start": {"dateTime": args.start},
        "end": {"dateTime": args.end},
    }
    if args.description:
        event_body["description"] = args.description

    try:
        event = service.events().insert(calendarId="primary", body=event_body).execute()
        print(f"Created Event ID: {event.get('id')}")
    except HttpError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_calendar_update(args):
    """Updates a calendar event."""
    creds = get_credentials()
    service = build_calendar_service(creds)

    try:
        # Fetch existing event to preserve unmodified fields
        event = (
            service.events().get(calendarId="primary", eventId=args.event_id).execute()
        )

        if args.title:
            event["summary"] = args.title
        if args.start:
            event.setdefault("start", {}).pop("date", None)
            event["start"]["dateTime"] = args.start
        if args.end:
            event.setdefault("end", {}).pop("date", None)
            event["end"]["dateTime"] = args.end
        if args.description is not None:
            event["description"] = args.description

        updated_event = (
            service.events()
            .update(calendarId="primary", eventId=args.event_id, body=event)
            .execute()
        )
        print(f"Updated Event ID: {updated_event.get('id')}")
    except HttpError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_calendar_delete(args):
    """Deletes a calendar event."""
    creds = get_credentials()
    service = build_calendar_service(creds)

    try:
        service.events().delete(calendarId="primary", eventId=args.event_id).execute()
        print(f"Deleted Event ID: {args.event_id}")
    except HttpError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_tasks_list(args):
    """Lists tasks from the task list."""
    creds = get_credentials()
    service = build_tasks_service(creds)

    try:
        tasks = []
        page_token = None
        while True:
            tasks_result = (
                service.tasks()
                .list(
                    tasklist=args.tasklist,
                    showCompleted=args.completed,
                    pageToken=page_token,
                )
                .execute()
            )
            tasks.extend(tasks_result.get("items", []))
            page_token = tasks_result.get("nextPageToken")
            if not page_token:
                break

        if not tasks:
            print("No tasks found.")
            return

        for task in tasks:
            status = "[x]" if task.get("status") == "completed" else "[ ]"
            due = f" (Due: {task['due'].split('T')[0]})" if "due" in task else ""
            print(
                f"{status} ID: {task['id']} | Title: {task.get('title', '(No Title)')}{due}"
            )
    except HttpError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_tasks_create(args):
    """Creates a task in the task list."""
    creds = get_credentials()
    service = build_tasks_service(creds)

    task_body = {"title": args.title}
    if args.notes:
        task_body["notes"] = args.notes
    if args.due:
        # Convert YYYY-MM-DD to RFC 3339 timestamp
        task_body["due"] = f"{args.due}T00:00:00Z"

    try:
        task = service.tasks().insert(tasklist=args.tasklist, body=task_body).execute()
        print(f"Created Task ID: {task.get('id')}")
    except HttpError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_tasks_update(args):
    """Updates a task in the task list."""
    creds = get_credentials()
    service = build_tasks_service(creds)

    try:
        task = service.tasks().get(tasklist=args.tasklist, task=args.task_id).execute()

        if args.title:
            task["title"] = args.title
        if args.notes is not None:
            task["notes"] = args.notes
        if args.due is not None:
            task["due"] = f"{args.due}T00:00:00Z" if args.due else None
        if args.status:
            task["status"] = args.status

        updated_task = (
            service.tasks()
            .update(tasklist=args.tasklist, task=args.task_id, body=task)
            .execute()
        )
        print(f"Updated Task ID: {updated_task.get('id')}")
    except HttpError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_tasks_delete(args):
    """Deletes a task from the task list."""
    creds = get_credentials()
    service = build_tasks_service(creds)

    try:
        service.tasks().delete(tasklist=args.tasklist, task=args.task_id).execute()
        print(f"Deleted Task ID: {args.task_id}")
    except HttpError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Google Workspace Integration Client.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Auth check
    subparsers.add_parser("auth-check", help="Check authentication and scopes.")

    # Calendar subparsers
    cal_parser = subparsers.add_parser("calendar", help="Google Calendar operations.")
    cal_sub = cal_parser.add_subparsers(dest="action", required=True)

    cal_list = cal_sub.add_parser("list", help="List upcoming events.")
    cal_list.add_argument(
        "--days", type=int, default=7, help="Number of days of events to retrieve."
    )
    cal_list.set_defaults(func=handle_calendar_list)

    cal_create = cal_sub.add_parser("create", help="Create a calendar event.")
    cal_create.add_argument("--title", required=True, help="Title of the event.")
    cal_create.add_argument(
        "--start", required=True, help="Start time in ISO 8601 format."
    )
    cal_create.add_argument("--end", required=True, help="End time in ISO 8601 format.")
    cal_create.add_argument("--description", help="Optional description.")
    cal_create.set_defaults(func=handle_calendar_create)

    cal_update = cal_sub.add_parser("update", help="Update a calendar event.")
    cal_update.add_argument("--event-id", required=True, help="Event ID to update.")
    cal_update.add_argument("--title", help="New title.")
    cal_update.add_argument("--start", help="New start time.")
    cal_update.add_argument("--end", help="New end time.")
    cal_update.add_argument(
        "--description", help="New description (pass empty string to clear)."
    )
    cal_update.set_defaults(func=handle_calendar_update)

    cal_delete = cal_sub.add_parser("delete", help="Delete a calendar event.")
    cal_delete.add_argument("--event-id", required=True, help="Event ID to delete.")
    cal_delete.set_defaults(func=handle_calendar_delete)

    # Tasks subparsers
    tasks_parser = subparsers.add_parser("tasks", help="Google Tasks operations.")
    tasks_parser.add_argument(
        "--tasklist", default="@default", help="Task list ID (default: @default)."
    )
    tasks_sub = tasks_parser.add_subparsers(dest="action", required=True)

    tasks_list = tasks_sub.add_parser("list", help="List tasks.")
    tasks_list.add_argument(
        "--completed", action="store_true", help="Show completed tasks."
    )
    tasks_list.set_defaults(func=handle_tasks_list)

    tasks_create = tasks_sub.add_parser("create", help="Create a task.")
    tasks_create.add_argument("--title", required=True, help="Title of the task.")
    tasks_create.add_argument("--notes", help="Task description/notes.")
    tasks_create.add_argument("--due", help="Due date in YYYY-MM-DD format.")
    tasks_create.set_defaults(func=handle_tasks_create)

    tasks_update = tasks_sub.add_parser("update", help="Update a task.")
    tasks_update.add_argument("--task-id", required=True, help="Task ID to update.")
    tasks_update.add_argument("--title", help="New title.")
    tasks_update.add_argument("--notes", help="New description/notes.")
    tasks_update.add_argument("--due", help="New due date (YYYY-MM-DD).")
    tasks_update.add_argument(
        "--status", choices=["completed", "needsAction"], help="Task status."
    )
    tasks_update.set_defaults(func=handle_tasks_update)

    tasks_delete = tasks_sub.add_parser("delete", help="Delete a task.")
    tasks_delete.add_argument("--task-id", required=True, help="Task ID to delete.")
    tasks_delete.set_defaults(func=handle_tasks_delete)

    args = parser.parse_args()

    if args.command == "auth-check":
        handle_auth_check(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
