import os
import sys
import unittest
import asyncio
from unittest.mock import patch, AsyncMock

# Add scripts directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
import dataplex_scanner

class TestDataplexScanner(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @patch("asyncio.create_subprocess_exec")
    @patch("asyncio.create_subprocess_shell")
    def test_run_command_async_uses_exec_no_shell(self, mock_shell, mock_exec):
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'{"count": 10}', b'')
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        argv = ["bq", "query", "SELECT 1"]
        result = self.loop.run_until_complete(dataplex_scanner.run_command_async(argv))
        
        self.assertEqual(result, '{"count": 10}')
        mock_exec.assert_called_once_with(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        mock_shell.assert_not_called()

    @patch("dataplex_scanner.run_command_async")
    def test_get_table_row_count(self, mock_run):
        mock_run.return_value = '[{"count": "42"}]'
        
        row_count = self.loop.run_until_complete(dataplex_scanner.get_table_row_count("proj.dataset.table"))
        self.assertEqual(row_count, 42)
        mock_run.assert_called_once_with([
            "bq", "query", "--quiet", "--nouse_legacy_sql", "--format=json",
            "SELECT count(*) as count FROM `proj.dataset.table`"
        ])

    @patch("dataplex_scanner.get_table_row_count")
    @patch("dataplex_scanner.run_command_async")
    @patch("os.makedirs")
    @patch("builtins.open")
    def test_create_and_wait_for_scan_valid_3_parts(self, mock_open, mock_makedirs, mock_run, mock_get_count):
        mock_get_count.return_value = 100
        mock_run.side_effect = [
            "", 
            '{"dataProfileResult": {"profile": {}}}' 
        ]

        with patch("asyncio.sleep", AsyncMock()):
            self.loop.run_until_complete(
                dataplex_scanner.create_and_wait_for_scan("my-project.my_dataset.my_table", "us-central1", "/tmp/out")
            )

        create_argv = mock_run.call_args_list[0][0][0]
        self.assertEqual(create_argv[0], "gcloud")
        self.assertEqual(create_argv[4], "data-profile")
        self.assertIn("--location=us-central1", create_argv)
        self.assertIn("--project=my-project", create_argv)
        self.assertIn("--data-source-resource=//bigquery.googleapis.com/projects/my-project/datasets/my_dataset/tables/my_table", create_argv)

    @patch("dataplex_scanner.run_command_async")
    def test_malicious_inputs_rejected(self, mock_run):
        # 1. Malicious location
        with patch("logging.error") as mock_log:
            self.loop.run_until_complete(
                dataplex_scanner.create_and_wait_for_scan("proj.ds.tbl", "us-central1; rm -rf /", "/tmp/out")
            )
            mock_log.assert_called_with("[%s] Invalid location: %s. Skipping.", "proj.ds.tbl", "us-central1; rm -rf /")
            mock_run.assert_not_called()

        # 2. Malicious project ID in 3-part table_id
        with patch("logging.error") as mock_log:
            self.loop.run_until_complete(
                dataplex_scanner.create_and_wait_for_scan("proj;inject.ds.tbl", "us-central1", "/tmp/out")
            )
            mock_log.assert_called_with("[%s] Invalid segments in table ID. Skipping.", "proj;inject.ds.tbl")
            mock_run.assert_not_called()

        # 3. Malicious dataset in 3-part table_id
        with patch("logging.error") as mock_log:
            self.loop.run_until_complete(
                dataplex_scanner.create_and_wait_for_scan("proj.ds;inject.tbl", "us-central1", "/tmp/out")
            )
            mock_log.assert_called_with("[%s] Invalid segments in table ID. Skipping.", "proj.ds;inject.tbl")
            mock_run.assert_not_called()

        # 4. Malicious catalog in 4-part table_id
        with patch("logging.error") as mock_log:
            self.loop.run_until_complete(
                dataplex_scanner.create_and_wait_for_scan("proj.cat;inject.ns.tbl", "us-central1", "/tmp/out")
            )
            mock_log.assert_called_with("[%s] Invalid segments in table ID. Skipping.", "proj.cat;inject.ns.tbl")
            mock_run.assert_not_called()

        # 5. Invalid format (2 parts)
        with patch("logging.error") as mock_log:
            self.loop.run_until_complete(
                dataplex_scanner.create_and_wait_for_scan("ds.tbl", "us-central1", "/tmp/out")
            )
            mock_log.assert_called_with(
                "[%s] Invalid format. Expected 'project.dataset.table' or 'project.catalog.namespace.table'. Skipping.",
                "ds.tbl"
            )
            mock_run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
