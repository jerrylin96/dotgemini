import argparse
import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError

# Insert scripts folder to sys.path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")),
)
import workspace_client


class TestWorkspaceClient(unittest.TestCase):
    def test_positive_int_valid(self):
        self.assertEqual(workspace_client.positive_int("5"), 5)
        self.assertEqual(workspace_client.positive_int("1"), 1)

    def test_positive_int_invalid(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            workspace_client.positive_int("0")
        with self.assertRaises(argparse.ArgumentTypeError):
            workspace_client.positive_int("-3")
        with self.assertRaises(argparse.ArgumentTypeError):
            workspace_client.positive_int("abc")

    @patch("workspace_client.google.auth.default")
    def test_get_credentials_success(self, mock_auth):
        mock_auth.return_value = ("credentials", "project")
        creds = workspace_client.get_credentials()
        self.assertEqual(creds, "credentials")

    @patch("workspace_client.google.auth.default")
    def test_get_credentials_failure(self, mock_auth):
        from google.auth.exceptions import DefaultCredentialsError

        mock_auth.side_effect = DefaultCredentialsError()
        with self.assertRaises(SystemExit):
            workspace_client.get_credentials()

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_auth_check_success(
        self, mock_stdout, mock_get_creds, mock_build_cal, mock_build_tasks
    ):
        mock_cal = MagicMock()
        mock_tasks = MagicMock()
        mock_build_cal.return_value = mock_cal
        mock_build_tasks.return_value = mock_tasks

        args = MagicMock()
        workspace_client.handle_auth_check(args)

        output = mock_stdout.getvalue()
        self.assertIn("Authenticated successfully with Google Workspace APIs", output)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    def test_auth_check_failure(self, mock_get_creds, mock_build_cal):
        mock_cal = MagicMock()
        mock_build_cal.return_value = mock_cal
        mock_cal.events.return_value.list.return_value.execute.side_effect = Exception(
            "API error"
        )

        args = MagicMock()
        with self.assertRaises(SystemExit):
            workspace_client.handle_auth_check(args)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_calendar_list_success(
        self, mock_stdout, mock_get_creds, mock_build_service
    ):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_events = [
            {
                "id": "ev1",
                "summary": "Meeting 1",
                "start": {"dateTime": "2026-07-16T15:00:00Z"},
            },
            {"id": "ev2", "summary": "Meeting 2", "start": {"date": "2026-07-17"}},
        ]
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": mock_events
        }

        args = MagicMock()
        args.days = 7
        workspace_client.handle_calendar_list(args)

        output = mock_stdout.getvalue()
        self.assertIn("ev1", output)
        self.assertIn("Meeting 1", output)
        self.assertIn("ev2", output)
        self.assertIn("Meeting 2", output)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_calendar_list_pagination(
        self, mock_stdout, mock_get_creds, mock_build_service
    ):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service

        # First call returns items + nextPageToken, second call returns items, no page token.
        call_responses = [
            {
                "items": [
                    {
                        "id": "ev1",
                        "summary": "Meeting 1",
                        "start": {"date": "2026-07-16"},
                    }
                ],
                "nextPageToken": "token123",
            },
            {
                "items": [
                    {
                        "id": "ev2",
                        "summary": "Meeting 2",
                        "start": {"date": "2026-07-17"},
                    }
                ]
            },
        ]
        mock_service.events.return_value.list.return_value.execute.side_effect = (
            call_responses
        )

        args = MagicMock()
        args.days = 7
        workspace_client.handle_calendar_list(args)

        output = mock_stdout.getvalue()
        self.assertIn("ev1", output)
        self.assertIn("ev2", output)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_calendar_list_empty(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": []
        }

        args = MagicMock()
        args.days = 7
        workspace_client.handle_calendar_list(args)

        output = mock_stdout.getvalue()
        self.assertIn("No upcoming events found.", output)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_calendar_create(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "new_ev_id"
        }

        args = MagicMock()
        args.title = "New Event"
        args.start = "2026-07-16T15:00:00Z"
        args.end = "2026-07-16T16:00:00Z"
        args.description = "Test Desc"

        workspace_client.handle_calendar_create(args)

        output = mock_stdout.getvalue()
        self.assertIn("Created Event ID: new_ev_id", output)

        called_body = mock_service.events.return_value.insert.call_args[1]["body"]
        self.assertEqual(called_body["summary"], "New Event")
        self.assertEqual(called_body["start"]["dateTime"], "2026-07-16T15:00:00Z")
        self.assertEqual(called_body["end"]["dateTime"], "2026-07-16T16:00:00Z")
        self.assertEqual(called_body["description"], "Test Desc")

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    def test_calendar_create_http_error(self, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_service.events.return_value.insert.return_value.execute.side_effect = (
            HttpError(resp=mock_resp, content=b"")
        )

        args = MagicMock()
        args.title = "New Event"
        args.start = "2026-07-16T15:00:00Z"
        args.end = "2026-07-16T16:00:00Z"
        args.description = "Test Desc"

        with self.assertRaises(SystemExit):
            workspace_client.handle_calendar_create(args)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_calendar_update(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.events.return_value.get.return_value.execute.return_value = {
            "id": "ev_id",
            "summary": "Old Summary",
            "start": {"date": "2026-07-16"},
            "end": {"date": "2026-07-17"},
        }
        mock_service.events.return_value.update.return_value.execute.return_value = {
            "id": "ev_id"
        }

        args = MagicMock()
        args.event_id = "ev_id"
        args.title = "New Summary"
        args.start = "2026-07-16T17:00:00Z"
        args.end = "2026-07-16T18:00:00Z"
        args.description = None

        workspace_client.handle_calendar_update(args)

        output = mock_stdout.getvalue()
        self.assertIn("Updated Event ID: ev_id", output)

        # Verify date key was popped from start/end to avoid schema mismatch
        called_body = mock_service.events.return_value.update.call_args[1]["body"]
        self.assertNotIn("date", called_body["start"])
        self.assertNotIn("date", called_body["end"])

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    def test_calendar_update_all_day_mixed_schema_error(
        self, mock_get_creds, mock_build_service
    ):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.events.return_value.get.return_value.execute.return_value = {
            "id": "ev_id",
            "summary": "All Day Event",
            "start": {"date": "2026-07-16"},
            "end": {"date": "2026-07-17"},
        }

        # Supply only start, which causes mixed schema on all-day event updates
        args = MagicMock()
        args.event_id = "ev_id"
        args.title = None
        args.start = "2026-07-16T17:00:00Z"
        args.end = None
        args.description = None

        with self.assertRaises(SystemExit):
            workspace_client.handle_calendar_update(args)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    def test_calendar_update_http_error(self, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_service.events.return_value.get.return_value.execute.side_effect = (
            HttpError(resp=mock_resp, content=b"")
        )

        args = MagicMock()
        args.event_id = "ev_id"
        args.title = "New Summary"
        args.start = "2026-07-16T17:00:00Z"
        args.end = "2026-07-16T18:00:00Z"
        args.description = None

        with self.assertRaises(SystemExit):
            workspace_client.handle_calendar_update(args)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_calendar_delete(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.events.return_value.delete.return_value.execute.return_value = {}

        args = MagicMock()
        args.event_id = "ev_id"

        workspace_client.handle_calendar_delete(args)

        output = mock_stdout.getvalue()
        self.assertIn("Deleted Event ID: ev_id", output)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    def test_calendar_delete_http_error(self, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_service.events.return_value.delete.return_value.execute.side_effect = (
            HttpError(resp=mock_resp, content=b"")
        )

        args = MagicMock()
        args.event_id = "ev_id"

        with self.assertRaises(SystemExit):
            workspace_client.handle_calendar_delete(args)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_tasks_list(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_tasks = [
            {"id": "t1", "title": "Task 1", "status": "needsAction"},
            {
                "id": "t2",
                "title": "Task 2",
                "status": "completed",
                "due": "2026-07-16T00:00:00Z",
            },
        ]
        mock_service.tasks.return_value.list.return_value.execute.return_value = {
            "items": mock_tasks
        }

        args = MagicMock()
        args.tasklist = "list-123"
        args.completed = True

        workspace_client.handle_tasks_list(args)

        output = mock_stdout.getvalue()
        self.assertIn("Task 1", output)
        self.assertIn("Task 2", output)
        self.assertIn("[x]", output)
        self.assertIn("[ ]", output)

        # Verify custom tasklist and showHidden was used
        mock_service.tasks.return_value.list.assert_called_with(
            tasklist="list-123", showCompleted=True, showHidden=True, pageToken=None
        )

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_tasks_list_pagination(
        self, mock_stdout, mock_get_creds, mock_build_service
    ):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service

        call_responses = [
            {
                "items": [{"id": "t1", "title": "Task 1", "status": "needsAction"}],
                "nextPageToken": "token456",
            },
            {
                "items": [
                    {
                        "id": "t2",
                        "title": "Task 2",
                        "status": "completed",
                        "due": "2026-07-16T00:00:00Z",
                    }
                ]
            },
        ]
        mock_service.tasks.return_value.list.return_value.execute.side_effect = (
            call_responses
        )

        args = MagicMock()
        args.tasklist = "list-123"
        args.completed = True

        workspace_client.handle_tasks_list(args)

        output = mock_stdout.getvalue()
        self.assertIn("Task 1", output)
        self.assertIn("Task 2", output)

        # Verify pageToken and showHidden was passed in the second call
        list_calls = mock_service.tasks.return_value.list.call_args_list
        self.assertEqual(len(list_calls), 2)
        self.assertEqual(list_calls[0][1]["pageToken"], None)
        self.assertEqual(list_calls[0][1]["showHidden"], True)
        self.assertEqual(list_calls[1][1]["pageToken"], "token456")
        self.assertEqual(list_calls[1][1]["showHidden"], True)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_tasks_create(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.tasks.return_value.insert.return_value.execute.return_value = {
            "id": "new_t_id"
        }

        args = MagicMock()
        args.tasklist = "@default"
        args.title = "New Task"
        args.notes = "Task notes"
        args.due = "2026-07-16"

        workspace_client.handle_tasks_create(args)

        output = mock_stdout.getvalue()
        self.assertIn("Created Task ID: new_t_id", output)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    def test_tasks_create_http_error(self, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_service.tasks.return_value.insert.return_value.execute.side_effect = (
            HttpError(resp=mock_resp, content=b"")
        )

        args = MagicMock()
        args.tasklist = "@default"
        args.title = "New Task"
        args.notes = "Task notes"
        args.due = "2026-07-16"

        with self.assertRaises(SystemExit):
            workspace_client.handle_tasks_create(args)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_tasks_update(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.tasks.return_value.get.return_value.execute.return_value = {
            "id": "t_id",
            "title": "Old Title",
            "status": "completed",
            "completed": "2026-07-16T15:00:00Z",
        }
        mock_service.tasks.return_value.update.return_value.execute.return_value = {
            "id": "t_id"
        }

        args = MagicMock()
        args.tasklist = "@default"
        args.task_id = "t_id"
        args.title = "New Title"
        args.notes = "New notes"
        args.due = ""
        args.status = "needsAction"

        workspace_client.handle_tasks_update(args)

        output = mock_stdout.getvalue()
        self.assertIn("Updated Task ID: t_id", output)

        # Verify completed key was popped from the body when setting needsAction
        called_body = mock_service.tasks.return_value.update.call_args[1]["body"]
        self.assertNotIn("completed", called_body)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    def test_tasks_update_http_error(self, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_service.tasks.return_value.get.return_value.execute.side_effect = (
            HttpError(resp=mock_resp, content=b"")
        )

        args = MagicMock()
        args.tasklist = "@default"
        args.task_id = "t_id"
        args.title = "New Title"
        args.notes = "New notes"
        args.due = ""
        args.status = "completed"

        with self.assertRaises(SystemExit):
            workspace_client.handle_tasks_update(args)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_tasks_delete(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.tasks.return_value.delete.return_value.execute.return_value = {}

        args = MagicMock()
        args.tasklist = "list-123"
        args.task_id = "t_id"

        workspace_client.handle_tasks_delete(args)

        output = mock_stdout.getvalue()
        self.assertIn("Deleted Task ID: t_id", output)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    def test_tasks_delete_http_error(self, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_service.tasks.return_value.delete.return_value.execute.side_effect = (
            HttpError(resp=mock_resp, content=b"")
        )

        args = MagicMock()
        args.tasklist = "list-123"
        args.task_id = "t_id"

        with self.assertRaises(SystemExit):
            workspace_client.handle_tasks_delete(args)


if __name__ == "__main__":
    unittest.main()
