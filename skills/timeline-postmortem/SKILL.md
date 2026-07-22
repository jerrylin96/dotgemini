---
name: timeline-postmortem
description: Conducts root-cause postmortems on missed deadlines, performs pre-mortem risk forecasting, calculates buffered timelines, and reschedules Google Workspace tasks/events.
---

# Timeline Postmortem & Pre-Mortem Risk Forecaster

Provides a structured retrospective workflow whenever a scheduled deadline, task, or milestone is missed. Decoupled from direct API execution, it drives Socratic root-cause interviewing, pre-mortem risk forecasting, and hands off schedule updates to project tools (like `google-workspace`).

---

## 1. Trigger Conditions

Activate this skill when:
- A user indicates a task or timeline deadline was missed.
- The `google-workspace` skill status check reports overdue tasks.
- Rescheduling a delayed goal or milestone is requested.
- Explicitly invoked via `/postmortem`.

---

## 2. Phase 1: Socratic 5 Whys Interview Protocol

When a deadline is missed, **do not immediately reschedule without diagnosis**. Conduct a concise, Caveman-style interview using the 5 Whys method to uncover the friction root cause.

### Friction Taxonomy
Classify the failure into one of four root cause categories:
1. **Estimation Failure**: Initial duration underestimated task complexity or required depth.
2. **Scope Creep**: Added unplanned subtasks or expanded requirements mid-flight.
3. **Blocker / Dependency**: Unresolved technical dependency, missing input, or external blocker.
4. **Context Switch / Interruption**: Higher priority fire drills or unexpected interruptions.

### Interview Questions
1. *"What primary factor caused the original deadline to be missed?"*
2. *"Why did that factor occur?"* (Repeat up to 5 times until true root cause is surfaced).
3. *"Is the underlying blocker now cleared, or does it still pose an active risk?"*

---

## 3. Phase 2: Buffer Heuristics & Rescheduling

Calculate the new target date using a root-cause buffer multiplier applied to the remaining estimated effort:

| Root Cause Category | Buffer Multiplier | Rationale |
|---|---|---|
| **Estimation Failure** | **1.25x** | Adjusts for optimistic bias. |
| **Scope Creep** | **1.50x** | Accounts for expanded scope boundary. |
| **Blocker / Dependency** | **1.30x** | Covers waiting time and dependency sync. |
| **Context Switch** | **1.20x** | Covers context-switching recovery overhead. |

$$\text{New Duration} = \text{Remaining Estimated Effort} \times \text{Buffer Multiplier}$$

---

## 4. Phase 3: Pre-Mortem Risk Forecasting

Before committing to the newly calculated date, conduct a **Pre-Mortem**:

1. **Pre-Mortem Inquiry**: Ask the user:
   > *"Imagine we are at the NEW deadline and it was missed again. What top 2 foresights or risks caused that failure?"*
2. **Mitigation Rules**:
   - For every identified foresight risk, establish an explicit guard or fallback step.
   - If the pre-mortem reveals unresolved external dependencies, pause calendar scheduling until the dependency is cleared.

---

## 5. Phase 4: Integration & Schedule Sync

Once the new timeline and mitigations are agreed upon:

### Reschedule via Google Workspace (`google-workspace` skill)
If the project uses Google Workspace, hand off to `google-workspace` to update tasks and calendar slots:
```bash
# Update Google Task due date
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py tasks update --task-id "TASK_ID" --due "YYYY-MM-DD"

# Update Google Calendar Focus Block
python3 ~/.gemini/skills/google-workspace/scripts/workspace_client.py calendar update --event-id "EVENT_ID" --start "YYYY-MM-DDTHH:MM:SSZ" --end "YYYY-MM-DDTHH:MM:SSZ"
```

---

## 6. Phase 5: Retro Artifact Persistence

Save a concise retro report to `<workspace-root>/artifacts/postmortems/YYYY-MM-DD_<topic>_retro.md`:

```markdown
# Timeline Postmortem Retro

- **Date**: YYYY-MM-DD
- **Task / Goal**: <Goal Title>
- **Original Deadline**: YYYY-MM-DD
- **Root Cause Category**: <Estimation | Scope | Blocker | Interruption>
- **Root Cause Analysis**: <Brief 5 Whys summary>

## New Timeline & Pre-Mortem
- **New Deadline**: YYYY-MM-DD (Buffer: X.XXx)
- **Pre-Mortem Risks Identified**:
  1. <Risk 1> → Mitigation: <Guard 1>
  2. <Risk 2> → Mitigation: <Guard 2>
```
