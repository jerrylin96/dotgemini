import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Insert scripts folder to sys.path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")),
)
import workspace_client


class TestWorkspaceClient(unittest.TestCase):
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
        mock_service.events().list().execute.return_value = {"items": mock_events}

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
    def test_calendar_list_empty(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.events().list().execute.return_value = {"items": []}

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
        mock_service.events().insert().execute.return_value = {"id": "new_ev_id"}

        args = MagicMock()
        args.title = "New Event"
        args.start = "2026-07-16T15:00:00Z"
        args.end = "2026-07-16T16:00:00Z"
        args.description = "Test Desc"

        workspace_client.handle_calendar_create(args)

        output = mock_stdout.getvalue()
        self.assertIn("Created Event ID: new_ev_id", output)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_calendar_update(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.events().get().execute.return_value = {
            "id": "ev_id",
            "summary": "Old Summary",
        }
        mock_service.events().update().execute.return_value = {"id": "ev_id"}

        args = MagicMock()
        args.event_id = "ev_id"
        args.title = "New Summary"
        args.start = "2026-07-16T17:00:00Z"
        args.end = None
        args.description = None

        workspace_client.handle_calendar_update(args)

        output = mock_stdout.getvalue()
        self.assertIn("Updated Event ID: ev_id", output)

    @patch("workspace_client.build_calendar_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_calendar_delete(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.events().delete().execute.return_value = {}

        args = MagicMock()
        args.event_id = "ev_id"

        workspace_client.handle_calendar_delete(args)

        output = mock_stdout.getvalue()
        self.assertIn("Deleted Event ID: ev_id", output)

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
        mock_service.tasks().list().execute.return_value = {"items": mock_tasks}

        args = MagicMock()
        args.completed = True

        workspace_client.handle_tasks_list(args)

        output = mock_stdout.getvalue()
        self.assertIn("Task 1", output)
        self.assertIn("Task 2", output)
        self.assertIn("[x]", output)
        self.assertIn("[ ]", output)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_tasks_create(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.tasks().insert().execute.return_value = {"id": "new_t_id"}

        args = MagicMock()
        args.title = "New Task"
        args.notes = "Task notes"
        args.due = "2026-07-16"

        workspace_client.handle_tasks_create(args)

        output = mock_stdout.getvalue()
        self.assertIn("Created Task ID: new_t_id", output)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_tasks_update(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.tasks().get().execute.return_value = {
            "id": "t_id",
            "title": "Old Title",
        }
        mock_service.tasks().update().execute.return_value = {"id": "t_id"}

        args = MagicMock()
        args.task_id = "t_id"
        args.title = "New Title"
        args.notes = "New notes"
        args.due = ""
        args.status = "completed"

        workspace_client.handle_tasks_update(args)

        output = mock_stdout.getvalue()
        self.assertIn("Updated Task ID: t_id", output)

    @patch("workspace_client.build_tasks_service")
    @patch("workspace_client.get_credentials")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_tasks_delete(self, mock_stdout, mock_get_creds, mock_build_service):
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.tasks().delete().execute.return_value = {}

        args = MagicMock()
        args.task_id = "t_id"

        workspace_client.handle_tasks_delete(args)

        output = mock_stdout.getvalue()
        self.assertIn("Deleted Task ID: t_id", output)


if __name__ == "__main__":
    unittest.main()
