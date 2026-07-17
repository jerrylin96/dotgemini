import datetime
import os
import sys
from zoneinfo import ZoneInfo
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
