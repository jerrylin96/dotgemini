import datetime
import os
import sys
from zoneinfo import ZoneInfo

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


def test_parse_iso_datetime():
    dt = parse_iso_datetime("2026-07-16T15:00:00Z")
    assert dt.year == 2026
    assert dt.month == 7
    assert dt.day == 16
    assert dt.tzinfo is not None

    dt_offset = parse_iso_datetime("2026-07-16T15:00:00-04:00")
    assert dt_offset.tzinfo.utcoffset(dt_offset) == datetime.timedelta(hours=-4)


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

    # Busy from 9:00 to 11:00 and 13:00 to 14:00
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

    # Need 2 hours. Should fit between 11:00 and 13:00
    duration = datetime.timedelta(hours=2)
    slot = find_free_slot(working_start, working_end, busy_intervals, duration)
    assert slot is not None
    assert slot[0] == datetime.datetime(2026, 7, 16, 11, 0, tzinfo=tz)
    assert slot[1] == datetime.datetime(2026, 7, 16, 13, 0, tzinfo=tz)

    # Need 3 hours. Should fit after 14:00 (14:00 to 17:00)
    duration_long = datetime.timedelta(hours=3)
    slot_long = find_free_slot(
        working_start, working_end, busy_intervals, duration_long
    )
    assert slot_long is not None
    assert slot_long[0] == datetime.datetime(2026, 7, 16, 14, 0, tzinfo=tz)
    assert slot_long[1] == datetime.datetime(2026, 7, 16, 17, 0, tzinfo=tz)


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


def test_all_day_multi_day_expansion():
    # Mocking Calendar API events for multi-day all-day event
    raw_events = [
        {
            "start": {"date": "2026-07-20"},
            "end": {"date": "2026-07-23"},  # July 20, 21, 22 are busy (exclusive of 23)
            "summary": "PTO",
        }
    ]

    tz = ZoneInfo("UTC")
    working_start_time = datetime.time(9, 0)
    working_end_time = datetime.time(17, 0)

    # Process into intervals
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

    assert len(calendar_intervals) == 3
    assert calendar_intervals[0].start == datetime.datetime(
        2026, 7, 20, 9, 0, tzinfo=tz
    )
    assert calendar_intervals[0].end == datetime.datetime(2026, 7, 20, 17, 0, tzinfo=tz)
    assert calendar_intervals[1].start == datetime.datetime(
        2026, 7, 21, 9, 0, tzinfo=tz
    )
    assert calendar_intervals[2].start == datetime.datetime(
        2026, 7, 22, 9, 0, tzinfo=tz
    )


def test_ignore_transparent_and_reminder_events():
    # Mocking Calendar API events
    raw_events = [
        {
            "start": {"date": "2026-07-20"},
            "end": {"date": "2026-07-21"},
            "summary": "Mom's Birthday",
        },
        {
            "start": {"date": "2026-07-21"},
            "end": {"date": "2026-07-22"},
            "summary": "Rent reminder",
        },
        {
            "start": {"dateTime": "2026-07-22T10:00:00Z"},
            "end": {"dateTime": "2026-07-22T11:00:00Z"},
            "summary": "Quick chat",
            "transparency": "transparent",
        },
        {
            "start": {"dateTime": "2026-07-22T13:00:00Z"},
            "end": {"dateTime": "2026-07-22T14:00:00Z"},
            "summary": "Important Meeting",
            "transparency": "opaque",
        },
    ]

    tz = ZoneInfo("UTC")
    working_start_time = datetime.time(9, 0)
    working_end_time = datetime.time(17, 0)

    calendar_intervals = []
    for item in raw_events:
        # Skip free/reminder events
        if item.get("transparency") == "transparent":
            continue

        # Skip events containing common reminder/birthday keywords in the summary
        summary = item.get("summary", "").lower()
        if any(kw in summary for kw in ["birthday", "bday", "anniversary", "reminder"]):
            continue

        start_data = item.get("start", {})
        end_data = item.get("end", {})
        if "date" in start_data:
            start_date_val = datetime.datetime.strptime(
                start_data["date"], "%Y-%m-%d"
            ).date()
            end_date_val = datetime.datetime.strptime(
                end_data["date"], "%Y-%m-%d"
            ).date()
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

    # Should only contain "Important Meeting"
    assert len(calendar_intervals) == 1
    assert calendar_intervals[0].start == datetime.datetime(
        2026, 7, 22, 13, 0, tzinfo=tz
    )
    assert calendar_intervals[0].end == datetime.datetime(2026, 7, 22, 14, 0, tzinfo=tz)
