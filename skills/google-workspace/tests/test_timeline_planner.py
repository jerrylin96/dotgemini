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

    # C. True (invalid config type safety check)
    settings_file.write_text(json.dumps({"obsidian_vault_path": True}))
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

    # 7. Symlink resolution check
    real_dir = tmp_path / "real_project"
    real_dir.mkdir()
    symlink_dir = tmp_path / "symlink_project"
    try:
        os.symlink(str(real_dir), str(symlink_dir))
    except (OSError, NotImplementedError):
        return

    timeline_planner.get_project_info.cache_clear()
    
    def mock_check_output_symlink(cmd, cwd=None, stderr=None):
        if "rev-parse" in cmd:
            return str(real_dir).encode()
        return b""
    monkeypatch.setattr("subprocess.check_output", mock_check_output_symlink)
    
    monkeypatch.setenv("ANTIGRAVITY_OBSIDIAN_VAULT", str(vault))
    symlinked_artifact_path = os.path.join(str(symlink_dir), "artifacts", "goals.json")
    
    with mock.patch("os.getcwd", return_value=str(symlink_dir)):
        resolved = resolve_artifact_path(symlinked_artifact_path)
        expected = os.path.join(str(vault), "Projects", os.path.basename(str(real_dir)), "goals.json")
        assert os.path.normpath(resolved) == os.path.normpath(expected)


def test_parse_proposed_timeline_hierarchical():
    markdown = """# Proposed Timeline: Project Alpha

## Metadata
- **Task List Name**: Project Alpha List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **Write Section 3.2 of the paper**
  - **Notes**: parent notes
  - [ ] **Validate code and results for 3.2** <!-- task_id: SUB_T_123 -->
    - **Due**: 2026-07-18
    - **Notes**: subtask 1 notes
  - [ ] **Generate figures for 3.2**
    - **Due**: 2026-07-19

## Proposed Calendar Events
- **Event**: Focus: Validate code and results for 3.2 <!-- event_id: E_789 -->
  - **Start**: 2026-07-18T09:00:00-04:00
  - **End**: 2026-07-18T11:00:00-04:00
  - **Description**: subtask 1 notes
"""
    parsed = parse_proposed_timeline(markdown)
    assert len(parsed["errors"]) == 0
    assert len(parsed["tasks"]) == 3
    
    # Check parent task
    parent = parsed["tasks"][0]
    assert parent["title"] == "Write Section 3.2 of the paper"
    assert parent["is_parent"] is True
    assert parent["parent_idx"] is None
    assert parent["notes"] == "parent notes"
    
    # Check subtask 1
    sub1 = parsed["tasks"][1]
    assert sub1["title"] == "Validate code and results for 3.2"
    assert sub1["is_parent"] is False
    assert sub1["parent_idx"] == 0
    assert sub1["due"] == "2026-07-18"
    assert sub1["notes"] == "subtask 1 notes"
    assert sub1["id"] == "SUB_T_123"

    # Check subtask 2
    sub2 = parsed["tasks"][2]
    assert sub2["title"] == "Generate figures for 3.2"
    assert sub2["is_parent"] is False
    assert sub2["parent_idx"] == 0
    assert sub2["due"] == "2026-07-19"


def test_preflight_validate_timeline_hierarchical():
    # Verify that parent tasks without a due date validate successfully
    plan_data = {
        "tasklist_name": "Project Alpha List",
        "timezone": "America/New_York",
        "tasks": [
            {
                "title": "Write Section 3.2 of the paper",
                "is_parent": True,
                "parent_idx": None,
                "due": "",
            },
            {
                "title": "Validate code and results for 3.2",
                "is_parent": False,
                "parent_idx": 0,
                "due": "2026-07-18",
            }
        ],
        "events": [
            {
                "summary": "Focus: Validate code and results for 3.2",
                "start": "2026-07-18T09:00:00-04:00",
                "end": "2026-07-18T11:00:00-04:00",
            }
        ]
    }
    errors = preflight_validate_timeline(plan_data)
    assert len(errors) == 0


def test_handle_plan_hierarchical(tmp_path, monkeypatch):
    import timeline_planner
    goals_file = tmp_path / "goals.json"
    proposed_file = tmp_path / "proposed.md"
    
    goals_data = {
        "tasklist_title": "Paper Writing",
        "timezone": "America/New_York",
        "start_date": "2026-07-18",
        "days_limit": 14,
        "working_hours": {
            "start": "09:00",
            "end": "17:00"
        },
        "tasks": [
            {
                "title": "Write Section 3.2 of the paper",
                "notes": "parent notes",
                "subtasks": [
                    {
                        "title": "Validate code and results for 3.2",
                        "duration_hours": 1.5,
                        "notes": "subtask 1 notes"
                    },
                    {
                        "title": "Generate figures for 3.2",
                        "duration_hours": 1.0,
                    }
                ]
            }
        ]
    }
    import json
    goals_file.write_text(json.dumps(goals_data))
    
    # Mock credentials and service builds
    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    
    class MockEvents:
        def list(self, *args, **kwargs):
            return self
        def execute(self):
            return {"items": []}
            
    class MockService:
        def events(self):
            return MockEvents()
            
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: MockService())
    
    class Args:
        def __init__(self):
            self.goals_file = str(goals_file)
            self.proposed_file = str(proposed_file)
    
    timeline_planner.handle_plan(Args())
    
    # Read generated proposed file
    content = proposed_file.read_text()
    assert "# Proposed Timeline: Paper Writing" in content
    assert "- [ ] **Write Section 3.2 of the paper**" in content
    assert "  - **Notes**: parent notes" in content
    assert "  - [ ] **Validate code and results for 3.2**" in content
    assert "    - **Notes**: subtask 1 notes" in content
    assert "  - [ ] **Generate figures for 3.2**" in content
    assert "- **Event**: Focus: Validate code and results for 3.2" in content


def test_handle_apply_hierarchical(tmp_path, monkeypatch):
    import timeline_planner
    proposed_file = tmp_path / "proposed.md"
    state_file = tmp_path / "state.json"
    
    markdown = """# Proposed Timeline: Paper Writing

## Metadata
- **Task List Name**: Paper Writing List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **Write Section 3.2 of the paper**
  - **Notes**: parent notes
  - [ ] **Validate code and results for 3.2**
    - **Due**: 2026-07-18
    - **Notes**: subtask 1 notes
  - [ ] **Generate figures for 3.2**
    - **Due**: 2026-07-19

## Proposed Calendar Events
- **Event**: Focus: Validate code and results for 3.2
  - **Start**: 2026-07-18T09:00:00-04:00
  - **End**: 2026-07-18T11:00:00-04:00
  - **Description**: subtask 1 notes
"""
    proposed_file.write_text(markdown)
    
    # Mock credentials and services
    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    monkeypatch.setattr("timeline_planner.fetch_tasklists", lambda service: [])
    
    # Track Tasks API insert calls
    inserted_tasks = []
    
    class MockTasksResource:
        def insert(self, tasklist, body, parent=None):
            inserted_tasks.append((body, parent))
            class Exec:
                def execute(self):
                    # Return deterministic ID based on title
                    return {"id": "ID_" + body["title"].replace(" ", "_")}
            return Exec()
            
    class MockTasklistsResource:
        def insert(self, body):
            class Exec:
                def execute(self):
                    return {"id": "TASKLIST_123"}
            return Exec()
            
    class MockTasksService:
        def tasklists(self):
            return MockTasklistsResource()
        def tasks(self):
            return MockTasksResource()
            
    class MockCalendarEventsResource:
        def insert(self, calendarId, body):
            class Exec:
                def execute(self):
                    return {"id": "EVENT_123"}
            return Exec()
            
    class MockCalendarService:
        def events(self):
            return MockCalendarEventsResource()
            
    monkeypatch.setattr("timeline_planner.build_tasks_service", lambda creds: MockTasksService())
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: MockCalendarService())
    
    class Args:
        def __init__(self):
            self.proposed_file = str(proposed_file)
            self.state_file = str(state_file)
            self.confirm = True
            
    timeline_planner.handle_apply(Args())
    
    # Check inserted tasks and hierarchies
    assert len(inserted_tasks) == 3
    # Parent task created first
    assert inserted_tasks[0][0]["title"] == "Write Section 3.2 of the paper"
    assert inserted_tasks[0][1] is None # No parent
    
    # Subtask 1 created second, with parent ID pointing to parent task
    assert inserted_tasks[1][0]["title"] == "Validate code and results for 3.2"
    assert inserted_tasks[1][1] == "ID_Write_Section_3.2_of_the_paper"
    
    # Subtask 2 created third, with parent ID pointing to parent task
    assert inserted_tasks[2][0]["title"] == "Generate figures for 3.2"
    assert inserted_tasks[2][1] == "ID_Write_Section_3.2_of_the_paper"


def test_preflight_validate_standalone_missing_due():
    # A standalone task (not a parent, not referenced by anyone) missing a due date MUST fail
    markdown = """# Proposed Timeline: Project Alpha

## Metadata
- **Task List Name**: Project Alpha List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **Standalone Task**
  - **Notes**: Standalone task notes

## Proposed Calendar Events
"""
    plan_data = parse_proposed_timeline(markdown)
    errors = preflight_validate_timeline(plan_data)
    assert len(errors) == 1
    assert "Due date cannot be empty" in errors[0]


def test_handle_apply_parent_failure_skips_subtasks(tmp_path, monkeypatch):
    import timeline_planner
    proposed_file = tmp_path / "proposed.md"
    state_file = tmp_path / "state.json"
    
    markdown = """# Proposed Timeline: Paper Writing

## Metadata
- **Task List Name**: Paper Writing List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **Write Section 3.2 of the paper**
  - [ ] **Validate code and results for 3.2**
    - **Due**: 2026-07-18

## Proposed Calendar Events
- **Event**: Focus: Validate code and results for 3.2
  - **Start**: 2026-07-18T09:00:00-04:00
  - **End**: 2026-07-18T11:00:00-04:00
"""
    proposed_file.write_text(markdown)
    
    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    monkeypatch.setattr("timeline_planner.fetch_tasklists", lambda service: [])
    
    inserted_tasks = []
    
    class MockTasksResource:
        def insert(self, tasklist, body, parent=None):
            if body["title"] == "Write Section 3.2 of the paper":
                # Mock failure for parent task creation
                raise Exception("API Error")
            inserted_tasks.append((body, parent))
            class Exec:
                def execute(self):
                    return {"id": "ID_" + body["title"].replace(" ", "_")}
            return Exec()
            
    class MockTasklistsResource:
        def insert(self, body):
            class Exec:
                def execute(self):
                    return {"id": "TASKLIST_123"}
            return Exec()
            
    class MockTasksService:
        def tasklists(self):
            return MockTasklistsResource()
        def tasks(self):
            return MockTasksResource()
            
    monkeypatch.setattr("timeline_planner.build_tasks_service", lambda creds: MockTasksService())
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: None)
    
    class Args:
        def __init__(self):
            self.proposed_file = str(proposed_file)
            self.state_file = str(state_file)
            self.confirm = True
            
    # Should not crash, and should skip the subtask because the parent failed to create
    with pytest.raises(SystemExit) as exc_info:
        timeline_planner.handle_apply(Args())
    assert exc_info.value.code == 1
    
    assert len(inserted_tasks) == 0 # Subtask was skipped


def test_parse_proposed_timeline_tab_and_space_indentation():
    # Verify that properties indented with tabs or spaces are parsed correctly
    markdown = """# Proposed Timeline: Project Alpha

## Metadata
- **Task List Name**: Project Alpha List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **Write Section 3.2 of the paper**
\t- [ ] **Subtask with tab**
\t\t- **Due**: 2026-07-18
\t\t- **Notes**: tab notes
  - [ ] **Subtask with spaces**
    - **Due**: 2026-07-19
    - **Notes**: spaces notes

## Proposed Calendar Events
- **Event**: Focus: Subtask with tab
  - **Start**: 2026-07-18T09:00:00-04:00
  - **End**: 2026-07-18T11:00:00-04:00
"""
    parsed = parse_proposed_timeline(markdown)
    assert len(parsed["errors"]) == 0
    assert len(parsed["tasks"]) == 3
    
    # Subtask with tab
    sub_tab = parsed["tasks"][1]
    assert sub_tab["title"] == "Subtask with tab"
    assert sub_tab["due"] == "2026-07-18"
    assert sub_tab["notes"] == "tab notes"
    
    # Subtask with spaces
    sub_spaces = parsed["tasks"][2]
    assert sub_spaces["title"] == "Subtask with spaces"
    assert sub_spaces["due"] == "2026-07-19"
    assert sub_spaces["notes"] == "spaces notes"


def test_handle_plan_invalid_subtasks_validation(tmp_path, monkeypatch, capsys):
    import timeline_planner
    goals_file = tmp_path / "goals.json"
    
    goals_data = {
        "tasklist_title": "Paper Writing",
        "timezone": "America/New_York",
        "start_date": "2026-07-18",
        "days_limit": 14,
        "tasks": [
            {
                "title": "Write Section 3.2",
                "subtasks": "not a list"
            }
        ]
    }
    import json
    goals_file.write_text(json.dumps(goals_data))
    
    class Args:
        def __init__(self):
            self.goals_file = str(goals_file)
            self.proposed_file = str(tmp_path / "proposed.md")
            
    with pytest.raises(SystemExit) as exc_info:
        timeline_planner.handle_plan(Args())
    assert exc_info.value.code == 1
    
    captured = capsys.readouterr()
    assert "has a 'subtasks' field that is not a list" in captured.err


def test_handle_plan_empty_subtasks_invalid_duration(tmp_path, monkeypatch, capsys):
    import timeline_planner
    goals_file = tmp_path / "goals.json"
    
    goals_data = {
        "tasklist_title": "Paper Writing",
        "timezone": "America/New_York",
        "start_date": "2026-07-18",
        "days_limit": 14,
        "tasks": [
            {
                "title": "Write Section 3.2",
                "subtasks": [],
                "duration_hours": "banana"
            }
        ]
    }
    import json
    goals_file.write_text(json.dumps(goals_data))
    
    class Args:
        def __init__(self):
            self.goals_file = str(goals_file)
            self.proposed_file = str(tmp_path / "proposed.md")
            
    with pytest.raises(SystemExit) as exc_info:
        timeline_planner.handle_plan(Args())
    assert exc_info.value.code == 1
    
    captured = capsys.readouterr()
    assert "must have a positive duration_hours" in captured.err


def test_preflight_validate_parent_with_malformed_due():
    # A parent task with a hand-added malformed due date MUST fail validation
    markdown = """# Proposed Timeline: Project Alpha

## Metadata
- **Task List Name**: Project Alpha List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-18
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **Parent Task**
  - **Due**: malformed-date
  - [ ] **Subtask**
    - **Due**: 2026-07-18

## Proposed Calendar Events
"""
    plan_data = parse_proposed_timeline(markdown)
    errors = preflight_validate_timeline(plan_data)
    assert len(errors) == 1
    assert "must be in YYYY-MM-DD format" in errors[0]


def test_handle_plan_mixed_tasks(tmp_path, monkeypatch):
    import timeline_planner
    goals_file = tmp_path / "goals.json"
    proposed_file = tmp_path / "proposed.md"
    
    goals_data = {
        "tasklist_title": "Mixed Tasks",
        "timezone": "America/New_York",
        "start_date": "2028-07-18",
        "days_limit": 14,
        "tasks": [
            {
                "title": "Standalone Task 1",
                "duration_hours": 1.0
            },
            {
                "title": "Parent Task 1",
                "subtasks": [
                    {
                        "title": "Subtask 1",
                        "duration_hours": 2.0
                    }
                ]
            },
            {
                "title": "Standalone Task 2",
                "duration_hours": 1.5
            }
        ]
    }
    import json
    goals_file.write_text(json.dumps(goals_data))
    
    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    
    class MockEvents:
        def list(self, *args, **kwargs):
            return self
        def execute(self):
            return {"items": []}
            
    class MockService:
        def events(self):
            return MockEvents()
            
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: MockService())
    
    class Args:
        def __init__(self):
            self.goals_file = str(goals_file)
            self.proposed_file = str(proposed_file)
            
    timeline_planner.handle_plan(Args())
    
    # Read generated proposed file
    content = proposed_file.read_text()
    assert "# Proposed Timeline: Mixed Tasks" in content
    assert "- [ ] **Standalone Task 1**" in content
    assert "- [ ] **Parent Task 1**" in content
    assert "  - [ ] **Subtask 1**" in content
    assert "- [ ] **Standalone Task 2**" in content


def test_handle_plan_partial_scheduling_conflict(tmp_path, monkeypatch):
    import timeline_planner
    goals_file = tmp_path / "goals.json"
    proposed_file = tmp_path / "proposed.md"
    
    # Let's request 2 subtasks of 8 hours each (total 16 hours), but calendar only has 8 hours free total
    goals_data = {
        "tasklist_title": "Conflict Tasks",
        "timezone": "America/New_York",
        "start_date": "2028-07-18",
        "days_limit": 1, # strictly 1 day
        "working_hours": {
            "start": "08:00",
            "end": "16:00" # 8 hours total working time
        },
        "tasks": [
            {
                "title": "Parent Task",
                "subtasks": [
                    {
                        "title": "Subtask 1",
                        "duration_hours": 8.0 # fills the entire day
                    },
                    {
                        "title": "Subtask 2",
                        "duration_hours": 8.0 # cannot be scheduled
                    }
                ]
            }
        ]
    }
    import json
    goals_file.write_text(json.dumps(goals_data))
    
    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    
    class MockEvents:
        def list(self, *args, **kwargs):
            return self
        def execute(self):
            return {"items": []}
            
    class MockService:
        def events(self):
            return MockEvents()
            
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: MockService())
    
    class Args:
        def __init__(self):
            self.goals_file = str(goals_file)
            self.proposed_file = str(proposed_file)
            
    timeline_planner.handle_plan(Args())
    
    content = proposed_file.read_text()
    # Subtask 1 is scheduled
    assert "  - [ ] **Subtask 1**" in content
    # Subtask 2 could not be scheduled, so it ends up in ## Unscheduled Tasks
    assert "## Unscheduled Tasks" in content
    assert "Parent Task -> Subtask 2" in content


def test_handle_publish_doc_new_and_append(tmp_path, monkeypatch):
    import timeline_planner
    from types import SimpleNamespace
    proposed_file = tmp_path / "proposed.md"
    proposed_file.write_text("# Proposed Timeline\n- [ ] Task 1")

    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    
    mock_create_doc = mock.MagicMock(return_value=("doc123", "https://docs.google.com/document/d/doc123/edit"))
    mock_append_doc = mock.MagicMock()
    mock_share_doc = mock.MagicMock(return_value=["boss@co.com"])

    monkeypatch.setattr("timeline_planner.create_google_doc", mock_create_doc)
    monkeypatch.setattr("timeline_planner.append_text_to_google_doc", mock_append_doc)
    monkeypatch.setattr("timeline_planner.share_google_doc", mock_share_doc)

    args_new = SimpleNamespace(
        proposed_file=str(proposed_file),
        doc_id=None,
        title="My Timeline",
        share="boss@co.com",
        role="reader",
    )

    timeline_planner.handle_publish_doc(args_new)
    mock_create_doc.assert_called_once_with(None, "My Timeline")
    mock_append_doc.assert_called_once()
    mock_share_doc.assert_called_once_with(None, "doc123", ["boss@co.com"], role="reader")

    # Test append mode
    mock_append_doc.reset_mock()
    args_append = SimpleNamespace(
        proposed_file=str(proposed_file),
        doc_id="doc123",
        title=None,
        share=None,
        role="reader",
    )
    timeline_planner.handle_publish_doc(args_append)
    mock_append_doc.assert_called_once()


def test_handle_publish_doc_guards_and_exceptions(tmp_path, monkeypatch):
    import timeline_planner
    from types import SimpleNamespace

    # Empty proposed_file
    args_empty = SimpleNamespace(proposed_file="", doc_id=None, title="Test", share=None, role="reader")
    with pytest.raises(SystemExit):
        timeline_planner.handle_publish_doc(args_empty)

    # Nonexistent file
    args_nonexistent = SimpleNamespace(proposed_file=str(tmp_path / "nonexistent.md"), doc_id=None, title="Test", share=None, role="reader")
    with pytest.raises(SystemExit):
        timeline_planner.handle_publish_doc(args_nonexistent)

    # API exception exit
    proposed_file = tmp_path / "proposed.md"
    proposed_file.write_text("# Proposed Timeline")
    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    monkeypatch.setattr("timeline_planner.create_google_doc", mock.MagicMock(side_effect=Exception("API Error")))
    args_api_error = SimpleNamespace(proposed_file=str(proposed_file), doc_id=None, title="Test", share=None, role="reader")
    with pytest.raises(SystemExit):
        timeline_planner.handle_publish_doc(args_api_error)


def test_handle_publish_doc_argparse_defaults(tmp_path, monkeypatch):
    import timeline_planner
    proposed_file = tmp_path / "proposed.md"
    proposed_file.write_text("# Proposed Timeline")

    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    mock_create_doc = mock.MagicMock(return_value=("doc123", "http://doc.url"))
    mock_append_doc = mock.MagicMock()
    monkeypatch.setattr("timeline_planner.create_google_doc", mock_create_doc)
    monkeypatch.setattr("timeline_planner.append_text_to_google_doc", mock_append_doc)

    with mock.patch.object(sys, "argv", ["timeline_planner.py", "publish-doc", "--proposed-file", str(proposed_file)]):
        try:
            timeline_planner.main()
        except SystemExit as e:
            assert e.code == 0
    mock_create_doc.assert_called_once_with(None, "Project Timeline & Execution Plan")


def test_parse_proposed_timeline_horizon():
    markdown = """# Proposed Timeline: OKR Project

## Metadata
- **Task List Name**: OKR Project List
- **Timezone**: America/New_York
- **Target Start Date**: 2026-07-22
- **Timeline State**: pending_approval

## Proposed Google Tasks
- [ ] **Quarterly OKR Goal**
  - **Horizon**: quarterly
  - **Due**: 2026-07-25
  - **Notes**: High-level objective.
- [ ] **Weekly Focus Task**
  - **Horizon**: weekly
  - **Due**: 2026-07-23

## Proposed Calendar Events
- **Event**: Focus: Weekly Focus Task
  - **Start**: 2026-07-23T09:00:00-04:00
  - **End**: 2026-07-23T11:00:00-04:00
"""
    parsed = parse_proposed_timeline(markdown)
    assert len(parsed["errors"]) == 0
    assert len(parsed["tasks"]) == 2
    assert parsed["tasks"][0]["horizon"] == "quarterly"
    assert parsed["tasks"][1]["horizon"] == "weekly"


def test_preflight_validate_timeline_horizon():
    plan_data = {
        "tasklist_name": "Test List",
        "timezone": "America/New_York",
        "tasks": [
            {"title": "Valid Task", "due": "2026-07-25", "horizon": "quarterly"},
            {"title": "Invalid Horizon Task", "due": "2026-07-25", "horizon": "monthly"},
        ],
        "events": [],
        "errors": [],
    }
    errors = preflight_validate_timeline(plan_data)
    assert any("Horizon 'monthly' must be 'quarterly' or 'weekly'" in e for e in errors)


def test_handle_plan_horizon_support(tmp_path, monkeypatch):
    import json
    import timeline_planner
    from types import SimpleNamespace

    goals_file = tmp_path / "goals.json"
    proposed_file = tmp_path / "proposed.md"

    data = {
        "tasklist_title": "OKR Sprint Plan",
        "timezone": "UTC",
        "days_limit": 7,
        "working_hours": {"start": "09:00", "end": "17:00"},
        "tasks": [
            {"title": "Strategic OKR", "horizon": "quarterly", "duration_hours": 2.0},
            {"title": "Tactical Sprint Task", "horizon": "weekly", "duration_hours": 1.0},
        ],
    }
    goals_file.write_text(json.dumps(data))

    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: mock.MagicMock())
    monkeypatch.setattr("timeline_planner.fetch_calendar_events", lambda s, min_iso, max_iso: [])

    args = SimpleNamespace(goals_file=str(goals_file), proposed_file=str(proposed_file))
    timeline_planner.handle_plan(args)

    assert proposed_file.exists()
    content = proposed_file.read_text()
    assert "- **Horizon**: quarterly" in content
    assert "- **Horizon**: weekly" in content


def test_handle_weekly_rollup(tmp_path, monkeypatch):
    import timeline_planner
    from types import SimpleNamespace

    proposed_file = tmp_path / "proposed.md"
    proposed_file.write_text("# Proposed Timeline\n- **Task List Name**: Test Task List\n")

    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    
    mock_tasks_svc = mock.MagicMock()
    mock_list_call = mock.MagicMock()
    now_iso = datetime.datetime.now(datetime.timezone.utc)
    completed_date = (now_iso - datetime.timedelta(days=2)).strftime("%Y-%m-%dT10:00:00.000Z")
    overdue_date = (now_iso - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
    future_date = (now_iso + datetime.timedelta(days=2)).strftime("%Y-%m-%dT00:00:00.000Z")

    mock_list_call.execute.return_value = {
        "items": [
            {"title": "Completed Task 1", "status": "completed", "completed": completed_date},
            {"title": "Overdue Task 2", "status": "needsAction", "due": overdue_date},
            {"title": "Upcoming Task 3", "status": "needsAction", "due": future_date},
        ]
    }
    mock_tasks_svc.tasks().list.return_value = mock_list_call
    monkeypatch.setattr("timeline_planner.build_tasks_service", lambda creds: mock_tasks_svc)

    mock_cal_svc = mock.MagicMock()
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: mock_cal_svc)
    monkeypatch.setattr(
        "timeline_planner.fetch_calendar_events",
        lambda s, min_iso, max_iso: [{"summary": "Focus: Upcoming Task 3", "start": {"dateTime": future_date}}],
    )

    mock_append = mock.MagicMock()
    mock_share = mock.MagicMock(return_value=["stakeholder@co.com"])
    monkeypatch.setattr("timeline_planner.append_text_to_google_doc", mock_append)
    monkeypatch.setattr("timeline_planner.share_google_doc", mock_share)

    args = SimpleNamespace(
        proposed_file=str(proposed_file),
        tasklist="@default",
        days=7,
        doc_id="doc_xyz",
        share="stakeholder@co.com",
        role="reader",
    )
    timeline_planner.handle_weekly_rollup(args)

    mock_append.assert_called_once()
    assert "Weekly Sprint Rollup" in mock_append.call_args[0][2]
    assert "Completed Task 1" in mock_append.call_args[0][2]
    assert "Overdue Task 2" in mock_append.call_args[0][2]
    assert "Upcoming Task 3" in mock_append.call_args[0][2]
    mock_share.assert_called_once_with(None, "doc_xyz", ["stakeholder@co.com"], role="reader")


def test_handle_plan_invalid_subtask_horizon(tmp_path, monkeypatch):
    import json
    import timeline_planner
    from types import SimpleNamespace

    goals_file = tmp_path / "goals.json"
    proposed_file = tmp_path / "proposed.md"

    data = {
        "tasklist_title": "Invalid Subtask Plan",
        "timezone": "UTC",
        "days_limit": 7,
        "working_hours": {"start": "09:00", "end": "17:00"},
        "tasks": [
            {
                "title": "Parent Goal",
                "horizon": "quarterly",
                "subtasks": [
                    {"title": "Subtask Bad", "horizon": "invalid_horizon", "duration_hours": 1.0}
                ],
            }
        ],
    }
    goals_file.write_text(json.dumps(data))
    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)

    args = SimpleNamespace(goals_file=str(goals_file), proposed_file=str(proposed_file))
    with pytest.raises(SystemExit):
        timeline_planner.handle_plan(args)


def test_handle_weekly_rollup_missing_tasklist(monkeypatch):
    import timeline_planner
    from types import SimpleNamespace

    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    mock_tasks_svc = mock.MagicMock()
    mock_tasks_svc.tasklists().list().execute.return_value = {"items": [{"id": "L1", "title": "Other List"}]}
    monkeypatch.setattr("timeline_planner.build_tasks_service", lambda creds: mock_tasks_svc)
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: mock.MagicMock())

    args = SimpleNamespace(
        proposed_file=None,
        tasklist="NonExistentList",
        days=7,
        doc_id=None,
        share=None,
        role="reader",
    )
    with pytest.raises(SystemExit):
        timeline_planner.handle_weekly_rollup(args)


def test_handle_weekly_rollup_invalid_days(monkeypatch):
    import timeline_planner
    from types import SimpleNamespace

    args = SimpleNamespace(
        proposed_file=None,
        tasklist="@default",
        days=-5,
        doc_id=None,
        share=None,
        role="reader",
    )
    with pytest.raises(SystemExit):
        timeline_planner.handle_weekly_rollup(args)


def test_handle_weekly_rollup_dynamic_days_and_stdout(monkeypatch, capsys):
    import timeline_planner
    from types import SimpleNamespace

    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    mock_tasks_svc = mock.MagicMock()
    mock_tasks_svc.tasks().list().execute.return_value = {"items": []}
    monkeypatch.setattr("timeline_planner.build_tasks_service", lambda creds: mock_tasks_svc)

    mock_cal_svc = mock.MagicMock()
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: mock_cal_svc)
    monkeypatch.setattr(
        "timeline_planner.fetch_calendar_events",
        lambda s, min_iso, max_iso: [
            {"summary": "Focus: Core Feature", "start": {"dateTime": "2026-07-23T10:00:00Z"}},
            {"summary": "Lunch with Friend", "start": {"dateTime": "2026-07-23T12:00:00Z"}},
        ],
    )

    args = SimpleNamespace(
        proposed_file=None,
        tasklist="@default",
        days=14,
        doc_id=None,
        share=None,
        role="reader",
    )
    timeline_planner.handle_weekly_rollup(args)
    captured = capsys.readouterr().out

    assert "Past 14 Days" in captured
    assert "Upcoming 14 Days" in captured
    assert "Focus: Core Feature" in captured
    assert "Lunch with Friend" not in captured


def test_safe_parse_task_datetime():
    from timeline_planner import safe_parse_task_datetime

    # Date-only YYYY-MM-DD
    dt_date = safe_parse_task_datetime("2026-07-23")
    assert dt_date is not None
    assert dt_date.year == 2026 and dt_date.month == 7 and dt_date.day == 23
    assert dt_date.hour == 23 and dt_date.minute == 59 and dt_date.second == 59

    # RFC 3339 timestamp with Z
    dt_z = safe_parse_task_datetime("2026-07-23T10:00:00Z")
    assert dt_z is not None
    assert dt_z.year == 2026 and dt_z.hour == 10

    # None and empty string
    assert safe_parse_task_datetime(None) is None
    assert safe_parse_task_datetime("") is None

    # Naive timestamp (no offset)
    assert safe_parse_task_datetime("2026-07-23T10:00:00") is None


def test_handle_weekly_rollup_resolves_tasklist_from_proposed_file(tmp_path, monkeypatch):
    import timeline_planner
    from types import SimpleNamespace

    proposed_file = tmp_path / "proposed.md"
    proposed_file.write_text(
        "# Proposed Timeline: Resolved Custom List\n\n"
        "## Metadata\n"
        "- **Task List Name**: Resolved Custom List\n"
        "- **Timezone**: UTC\n\n"
        "## Proposed Google Tasks\n\n"
        "## Proposed Calendar Events\n"
    )

    monkeypatch.setattr("timeline_planner.get_credentials", lambda: None)
    mock_tasks_svc = mock.MagicMock()
    mock_tasks_svc.tasklists().list().execute.return_value = {
        "items": [
            {"id": "L1", "title": "Other List"},
            {"id": "L2", "title": "Resolved Custom List"},
        ]
    }
    mock_tasks_svc.tasks().list().execute.return_value = {"items": []}
    monkeypatch.setattr("timeline_planner.build_tasks_service", lambda creds: mock_tasks_svc)
    monkeypatch.setattr("timeline_planner.build_calendar_service", lambda creds: mock.MagicMock())
    monkeypatch.setattr("timeline_planner.fetch_calendar_events", lambda s, min_iso, max_iso: [])

    args = SimpleNamespace(
        proposed_file=str(proposed_file),
        tasklist=None,
        days=7,
        doc_id=None,
        share=None,
        role="reader",
    )
    timeline_planner.handle_weekly_rollup(args)
    # Verify tasks.list was called with tasklist='L2'
    assert mock_tasks_svc.tasks().list.call_args[1]["tasklist"] == "L2"





