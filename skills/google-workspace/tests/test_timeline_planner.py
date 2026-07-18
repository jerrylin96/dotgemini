import datetime
import os
import sys
from zoneinfo import ZoneInfo
import unittest.mock as mock
import pytest

# Insert scripts folder to sys.path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")),
)
from timeline_planner import (
    Interval,
    parse_iso_datetime,
    find_free_slot,
    parse_proposed_timeline,
    preflight_validate_timeline,
    handle_apply,
    handle_status,
    resolve_artifact_path,
)


def test_interval_overlaps():
    # Overlapping intervals
    int1 = Interval(datetime.time(9, 0), datetime.time(11, 0))
    int2 = Interval(datetime.time(10, 0), datetime.time(12, 0))
    assert int1.overlaps(int2) is True
    assert int2.overlaps(int1) is True

    # Non-overlapping intervals
    int3 = Interval(datetime.time(9, 0), datetime.time(10, 0))
    int4 = Interval(datetime.time(10, 0), datetime.time(11, 0))
    assert int3.overlaps(int4) is False
    assert int4.overlaps(int3) is False


def test_parse_iso_datetime_enforce_offset():
    # Valid timezone aware strings
    dt1 = parse_iso_datetime("2026-07-16T15:00:00Z")
    assert dt1.tzinfo is not None
    assert dt1.utcoffset() == datetime.timedelta(0)

    dt2 = parse_iso_datetime("2026-07-16T15:00:00-04:00")
    assert dt2.tzinfo is not None
    assert dt2.utcoffset() == datetime.timedelta(hours=-4)

    # Naive ISO string must raise ValueError
    with pytest.raises(ValueError, match="Naive datetimes are not allowed"):
        parse_iso_datetime("2026-07-16T15:00:00")


def test_find_free_slot_empty():
    tz = ZoneInfo("UTC")
    working_start = datetime.datetime(2026, 7, 16, 9, 0, tzinfo=tz)
    working_end = datetime.datetime(2026, 7, 16, 17, 0, tzinfo=tz)
    busy_intervals = []
    duration = datetime.timedelta(hours=2)

    slot = find_free_slot(working_start, working_end, busy_intervals, duration)
    assert slot is not None
    assert slot[0] == working_start
    assert slot[1] == working_start + duration


def test_find_free_slot_with_conflicts():
    tz = ZoneInfo("UTC")
    working_start = datetime.datetime(2026, 7, 16, 9, 0, tzinfo=tz)
    working_end = datetime.datetime(2026, 7, 16, 17, 0, tzinfo=tz)

    busy_intervals = [
        Interval(
            datetime.datetime(2026, 7, 16, 9, 0, tzinfo=tz),
            datetime.datetime(2026, 7, 16, 11, 0, tzinfo=tz),
        ),
        Interval(
            datetime.datetime(2026, 7, 16, 13, 0, tzinfo=tz),
            datetime.datetime(2026, 7, 16, 14, 0, tzinfo=tz),
        ),
    ]

    duration = datetime.timedelta(hours=2)
    slot = find_free_slot(working_start, working_end, busy_intervals, duration)
    assert slot is not None
    assert slot[0] == datetime.datetime(2026, 7, 16, 11, 0, tzinfo=tz)
    assert slot[1] == datetime.datetime(2026, 7, 16, 13, 0, tzinfo=tz)


def test_parse_proposed_timeline_with_ids():
    markdown = """# Proposed Timeline: Project Alpha

## Metadata
- **Task List Name**: Project Alpha List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **First Action Item** <!-- task_id: T_123 -->
  - **Due**: 2026-07-18
  - **Notes**: Setup environment.
- [x] **Second Action Item** <!-- task_id: T_456 -->
  - **Due**: 2026-07-19
  - **Notes**: Code implementation.

## Proposed Calendar Events
- **Event**: Focus: First Action Item <!-- event_id: E_789 -->
  - **Start**: 2026-07-18T09:00:00-04:00
  - **End**: 2026-07-18T11:00:00-04:00
  - **Description**: Setup environment.
"""
    parsed = parse_proposed_timeline(markdown)
    assert parsed["tasklist_name"] == "Project Alpha List"
    assert parsed["timezone"] == "America/New_York"
    assert len(parsed["errors"]) == 0
    assert len(parsed["tasks"]) == 2
    assert parsed["tasks"][0]["title"] == "First Action Item"
    assert parsed["tasks"][0]["id"] == "T_123"
    assert parsed["tasks"][0]["completed"] is False
    assert parsed["tasks"][1]["title"] == "Second Action Item"
    assert parsed["tasks"][1]["id"] == "T_456"
    assert parsed["tasks"][1]["completed"] is True

    assert len(parsed["events"]) == 1
    assert parsed["events"][0]["summary"] == "Focus: First Action Item"
    assert parsed["events"][0]["id"] == "E_789"


def test_parse_proposed_timeline_malformed_errors():
    # Plan missing events section and having unrecognized metadata lines
    markdown = """# Proposed Timeline: Project Alpha

## Metadata
- **Task List Name**: Project Alpha List
- **Unrecognized Property**: Hello World

## Proposed Google Tasks
- [ ] **First Action Item**
  - **Due**: 2026-07-18
  - **Notes**: Setup environment.
"""
    parsed = parse_proposed_timeline(markdown)
    assert len(parsed["errors"]) > 0
    assert any("Unrecognized metadata entry" in e for e in parsed["errors"])
    assert any(
        "Missing required markdown section: '## Proposed Calendar Events'" in e
        for e in parsed["errors"]
    )


def test_preflight_validate_timeline_success():
    plan_data = {
        "tasklist_name": "My Valid List",
        "timezone": "America/New_York",
        "tasks": [
            {"title": "Task 1", "due": "2026-07-18", "notes": ""},
        ],
        "events": [
            {
                "summary": "Focus 1",
                "start": "2026-07-18T09:00:00-04:00",
                "end": "2026-07-18T11:00:00-04:00",
            }
        ],
        "errors": [],
    }
    errors = preflight_validate_timeline(plan_data)
    assert len(errors) == 0


def test_preflight_validate_timeline_failures():
    # Multi-error scenario
    plan_data = {
        "tasklist_name": "",  # Blank name
        "timezone": "Invalid/Timezone",  # Invalid tz
        "tasks": [
            {"title": "", "due": "2026-07-18"},  # Blank title
            {"title": "Task 2", "due": "2026-07-35"},  # Invalid date
        ],
        "events": [
            {
                "summary": "Focus 1",
                "start": "2026-07-18T11:00:00-04:00",
                "end": "2026-07-18T09:00:00-04:00",  # End <= start
            },
            {
                "summary": "Focus 2",
                "start": "2026-07-18T09:00:00",  # Naive (missing offset)
                "end": "2026-07-18T10:00:00Z",
            },
        ],
        "errors": [],
    }
    errors = preflight_validate_timeline(plan_data)
    assert len(errors) > 0
    # Must capture the invalid timezone, empty tasklist, blank task title, invalid task due date, end <= start, and naive start datetime errors
    assert any("Task List Name cannot be empty" in e for e in errors)
    assert any("Invalid timezone" in e for e in errors)
    assert any("Title cannot be empty" in e for e in errors)
    assert any("Due date" in e and "YYYY-MM-DD" in e for e in errors)
    assert any("must be strictly after start time" in e for e in errors)
    assert any("Naive datetimes are not allowed" in e for e in errors)


def test_all_day_multi_day_expansion_clipped_to_horizon():
    # Event range is July 10 to July 30 (multi-week trip)
    # Planning horizon is July 18 to July 25 (limit 7 days)
    raw_events = [
        {
            "start": {"date": "2026-07-10"},
            "end": {"date": "2026-07-30"},
            "summary": "PTO",
        }
    ]

    tz = ZoneInfo("UTC")
    working_start_time = datetime.time(9, 0)
    working_end_time = datetime.time(17, 0)

    # Inputs parameters for clip logic
    start_date = datetime.date(2026, 7, 18)
    days_limit = 7

    # Clip and expand logic
    calendar_intervals = []
    for item in raw_events:
        start_data = item.get("start", {})
        end_data = item.get("end", {})
        if "date" in start_data:
            start_date_val = datetime.datetime.strptime(
                start_data["date"], "%Y-%m-%d"
            ).date()
            end_date_val = datetime.datetime.strptime(
                end_data["date"], "%Y-%m-%d"
            ).date()

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

    # Should only expand 7 days (July 18 to July 24 inclusive, exclusive of horizon_end July 25)
    assert len(calendar_intervals) == 7
    assert calendar_intervals[0].start == datetime.datetime(
        2026, 7, 18, 9, 0, tzinfo=tz
    )
    assert calendar_intervals[-1].start == datetime.datetime(
        2026, 7, 24, 9, 0, tzinfo=tz
    )


@mock.patch("timeline_planner.get_credentials")
@mock.patch("timeline_planner.build_tasks_service")
@mock.patch("timeline_planner.build_calendar_service")
def test_handle_apply_success(
    mock_build_cal, mock_build_tasks, mock_get_creds, tmp_path
):
    proposed_file = tmp_path / "proposed_timeline.md"
    state_file = tmp_path / "timeline_state.json"

    # Valid proposed timeline
    proposed_content = """# Proposed Timeline: Project Alpha

## Metadata
- **Task List Name**: Project Alpha List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **First Action Item**
  - **Due**: 2026-07-18
  - **Notes**: Setup environment.

## Proposed Calendar Events
- **Event**: Focus: First Action Item
  - **Start**: 2026-07-18T09:00:00-04:00
  - **End**: 2026-07-18T11:00:00-04:00
  - **Description**: Setup environment.
"""
    proposed_file.write_text(proposed_content)

    mock_tasks = mock.Mock()
    mock_cal = mock.Mock()
    mock_build_tasks.return_value = mock_tasks
    mock_build_cal.return_value = mock_cal

    # Mock tasklists list returning nothing, insert creating new tasklist
    mock_tasks.tasklists.return_value.list.return_value.execute.return_value = {
        "items": []
    }
    mock_tasks.tasklists.return_value.insert.return_value.execute.return_value = {
        "id": "tl_123"
    }
    # Mock task creation
    mock_tasks.tasks.return_value.insert.return_value.execute.return_value = {
        "id": "t_456"
    }
    # Mock calendar event creation
    mock_cal.events.return_value.insert.return_value.execute.return_value = {
        "id": "e_789"
    }

    args = mock.Mock()
    args.proposed_file = str(proposed_file)
    args.state_file = str(state_file)
    args.confirm = True

    handle_apply(args)

    # Verify calls
    mock_tasks.tasks.return_value.insert.assert_called_once()
    mock_cal.events.return_value.insert.assert_called_once()

    # Verify file modifications
    updated_content = proposed_file.read_text()
    assert "task_id: t_456" in updated_content
    assert "event_id: e_789" in updated_content
    assert "Timeline State**: applied" in updated_content

    # Run apply a second time, verify idempotency (no insert calls made)
    mock_tasks.reset_mock()
    mock_cal.reset_mock()

    handle_apply(args)
    mock_tasks.tasks.return_value.insert.assert_not_called()
    mock_cal.events.return_value.insert.assert_not_called()


@mock.patch("timeline_planner.get_credentials")
@mock.patch("timeline_planner.build_tasks_service")
@mock.patch("timeline_planner.build_calendar_service")
def test_handle_apply_preflight_validation_skips_writes(
    mock_build_cal, mock_build_tasks, mock_get_creds, tmp_path
):
    proposed_file = tmp_path / "proposed_timeline.md"
    state_file = tmp_path / "timeline_state.json"

    # Malformed timeline (invalid end time <= start time)
    proposed_content = """# Proposed Timeline: Project Alpha

## Metadata
- **Task List Name**: Project Alpha List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **First Action Item**
  - **Due**: 2026-07-18
  - **Notes**: Setup environment.

## Proposed Calendar Events
- **Event**: Focus: First Action Item
  - **Start**: 2026-07-18T11:00:00-04:00
  - **End**: 2026-07-18T09:00:00-04:00
  - **Description**: Setup environment.
"""
    proposed_file.write_text(proposed_content)

    mock_tasks = mock.Mock()
    mock_cal = mock.Mock()
    mock_build_tasks.return_value = mock_tasks
    mock_build_cal.return_value = mock_cal

    args = mock.Mock()
    args.proposed_file = str(proposed_file)
    args.state_file = str(state_file)
    args.confirm = True

    # Should exit with SystemExit due to validation error
    with pytest.raises(SystemExit):
        handle_apply(args)

    # Verify no credential/insert calls made
    mock_get_creds.assert_not_called()
    mock_tasks.tasks.return_value.insert.assert_not_called()
    mock_cal.events.return_value.insert.assert_not_called()


@mock.patch("timeline_planner.get_credentials")
@mock.patch("timeline_planner.build_tasks_service")
@mock.patch("timeline_planner.build_calendar_service")
def test_handle_status_duplicate_titles_sync_independently(
    mock_build_cal, mock_build_tasks, mock_get_creds, tmp_path
):
    proposed_file = tmp_path / "proposed_timeline.md"
    state_file = tmp_path / "timeline_state.json"

    # Timeline containing duplicate task titles, but unique task IDs
    proposed_content = """# Proposed Timeline: Project Alpha

## Metadata
- **Task List Name**: Project Alpha List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: applied

## Proposed Google Tasks
- [ ] **Duplicate Task** <!-- task_id: T_1 -->
  - **Due**: 2026-07-18
  - **Notes**: Note 1
- [ ] **Duplicate Task** <!-- task_id: T_2 -->
  - **Due**: 2026-07-19
  - **Notes**: Note 2

## Proposed Calendar Events
"""
    proposed_file.write_text(proposed_content)

    mock_tasks = mock.Mock()
    mock_build_tasks.return_value = mock_tasks

    # Mock Task List lookup
    mock_tasks.tasklists.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "tl_123", "title": "Project Alpha List"}]
    }

    # First task T_1 is completed, second task T_2 is needsAction (incomplete)
    def mock_get_task_execute(tasklist, task):
        if task == "T_1":
            return {"id": "T_1", "status": "completed"}
        else:
            return {"id": "T_2", "status": "needsAction"}

    mock_tasks.tasks.return_value.get.side_effect = lambda tasklist, task: mock.Mock(
        execute=lambda: mock_get_task_execute(tasklist, task)
    )

    args = mock.Mock()
    args.proposed_file = str(proposed_file)
    args.state_file = str(state_file)

    handle_status(args)

    # Verify checklist was updated correctly (only first checkbox is marked [x])
    updated_content = proposed_file.read_text()
    assert "- [x] **Duplicate Task** <!-- task_id: T_1 -->" in updated_content
    assert "- [ ] **Duplicate Task** <!-- task_id: T_2 -->" in updated_content


def test_resolve_artifact_path(tmp_path, monkeypatch):
    import timeline_planner
    # Clear global cache using cache_clear
    timeline_planner.get_project_info.cache_clear()

    # Helper to mock git root
    def mock_check_output(cmd, cwd=None, stderr=None):
        if "rev-parse" in cmd:
            return b"/workspace/ClimateShift-Alpha"
        return b""

    monkeypatch.setattr("subprocess.check_output", mock_check_output)

    # Set up HOME and USERPROFILE environment variables so expanduser resolves natively (Agent 4 Nit 6)
    home_dir = tmp_path / "home_user"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))

    # 1. Non-artifact paths remain unchanged
    assert resolve_artifact_path("src/main.py") == "src/main.py"
    assert resolve_artifact_path("foo/artifacts/bar.json") == "foo/artifacts/bar.json"
    assert resolve_artifact_path("subdir/artifacts/x.json") == "subdir/artifacts/x.json"

    # 2. Artifact path with no vault config remains unchanged
    monkeypatch.delenv("ANTIGRAVITY_OBSIDIAN_VAULT", raising=False)
    with mock.patch("os.path.exists", return_value=False), \
         mock.patch("os.path.isdir", return_value=False):
        assert resolve_artifact_path("artifacts/goals.json") == "artifacts/goals.json"

    # 3. Env var configuration & Home directory validation (Blocker 1)
    # A. Valid Vault inside HOME
    vault = home_dir / "my_vault"
    vault.mkdir()
    
    # B. Env var precedence and tilde expansion (Agent 1 Point 1)
    monkeypatch.setenv("ANTIGRAVITY_OBSIDIAN_VAULT", "~/my_vault")
    with mock.patch("os.getcwd", return_value="/workspace/ClimateShift-Alpha"):
        resolved = resolve_artifact_path("artifacts/sub/dir/goals.json")
        expected = os.path.join(str(vault), "Projects", "ClimateShift-Alpha", "sub/dir/goals.json")
        assert os.path.normpath(resolved) == os.path.normpath(expected)

    # C. Invalid Vault outside HOME
    outside_vault = tmp_path / "outside_vault"
    outside_vault.mkdir()
    monkeypatch.setenv("ANTIGRAVITY_OBSIDIAN_VAULT", str(outside_vault))
    
    import io
    import sys
    stderr_capture = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr_capture)
    
    with mock.patch("os.getcwd", return_value="/workspace/ClimateShift-Alpha"):
        resolved = resolve_artifact_path("artifacts/goals.json")
        assert resolved == "artifacts/goals.json"
        assert "outside user's HOME directory" in stderr_capture.getvalue()

    monkeypatch.setattr(sys, "stderr", sys.__stderr__)

    # D. ValueError on commonpath (Agent 4 Nit 2)
    monkeypatch.setenv("ANTIGRAVITY_OBSIDIAN_VAULT", str(vault))
    stderr_capture = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr_capture)
    
    with mock.patch("os.path.commonpath", side_effect=ValueError("different drives")), \
         mock.patch("os.getcwd", return_value="/workspace/ClimateShift-Alpha"):
        resolved = resolve_artifact_path("artifacts/goals.json")
        assert resolved == "artifacts/goals.json"
        assert "Safety check failed for vault path" in stderr_capture.getvalue()

    monkeypatch.setattr(sys, "stderr", sys.__stderr__)

    # E. Existing local file fallback
    monkeypatch.setenv("ANTIGRAVITY_OBSIDIAN_VAULT", str(vault))
    
    def mock_path_exists(path):
        if "my_vault" in path:
            return False
        if "ClimateShift-Alpha/artifacts/goals.json" in path:
            return True
        return False
        
    with mock.patch("os.getcwd", return_value="/workspace/ClimateShift-Alpha"), \
         mock.patch("os.path.exists", side_effect=mock_path_exists):
        resolved = resolve_artifact_path("artifacts/goals.json")
        assert os.path.normpath(resolved) == os.path.normpath("/workspace/ClimateShift-Alpha/artifacts/goals.json")

    # 4. settings.json configuration
    monkeypatch.delenv("ANTIGRAVITY_OBSIDIAN_VAULT", raising=False)
    
    cli_dir = home_dir / ".gemini" / "antigravity-cli"
    cli_dir.mkdir(parents=True)
    settings_file = cli_dir / "settings.json"
    
    # Test valid settings.json with tilde expansion
    import json
    settings_file.write_text(json.dumps({"obsidian_vault_path": "~/my_vault"}))
    
    with mock.patch("os.getcwd", return_value="/workspace/ClimateShift-Alpha"):
        resolved = resolve_artifact_path("artifacts/goals.json")
        expected = os.path.join(str(vault), "Projects", "ClimateShift-Alpha", "goals.json")
        assert os.path.normpath(resolved) == os.path.normpath(expected)

    # Test invalid JSON decode error in settings.json
    settings_file.write_text("{invalid json")
    stderr_capture = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr_capture)
    
    with mock.patch("os.getcwd", return_value="/workspace/ClimateShift-Alpha"):
        resolved = resolve_artifact_path("artifacts/goals.json")
        assert resolved == "artifacts/goals.json"
        assert "Could not read obsidian_vault_path from settings.json" in stderr_capture.getvalue()
        
    settings_file.unlink()
    monkeypatch.setattr(sys, "stderr", sys.__stderr__)

    # 5. Respect explicit opt-outs
    # A. Empty string ""
    settings_file.write_text(json.dumps({"obsidian_vault_path": ""}))
    with mock.patch("os.getcwd", return_value="/workspace/ClimateShift-Alpha"), \
         mock.patch("os.path.isdir", return_value=True):
        resolved = resolve_artifact_path("artifacts/goals.json")
        assert resolved == "artifacts/goals.json"
        
    # B. False
    settings_file.write_text(json.dumps({"obsidian_vault_path": False}))
    with mock.patch("os.getcwd", return_value="/workspace/ClimateShift-Alpha"), \
         mock.patch("os.path.isdir", return_value=True):
        resolved = resolve_artifact_path("artifacts/goals.json")
        assert resolved == "artifacts/goals.json"

    settings_file.unlink()

    # 6. Fallback directories lookup
    desktop_vault = home_dir / "Desktop" / "antigravity_vault"
    desktop_vault.mkdir(parents=True)
    
    def mock_isdir(path):
        return path == str(desktop_vault)
        
    with mock.patch("os.path.isdir", side_effect=mock_isdir), \
         mock.patch("os.getcwd", return_value="/workspace/ClimateShift-Alpha"):
        resolved = resolve_artifact_path("artifacts/goals.json")
        expected = os.path.join(str(desktop_vault), "Projects", "ClimateShift-Alpha", "goals.json")
        assert os.path.normpath(resolved) == os.path.normpath(expected)

