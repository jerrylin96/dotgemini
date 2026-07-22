# Global Agent Guide

This guide establishes the primary engineering workflows, quality gates, and styles for AI agents globally across all project sessions. It is loaded by Antigravity CLI as `AGENTS.md` (aliased as `GEMINI.md` via a backward-compatibility symlink).

## Core Philosophical Principles

AI agents should follow these three core philosophies:
1. **Ponytail (Lazy Senior Dev Mode):** Write only what needs to exist. Prioritize reusability and native features.
2. **Caveman (Terse Style):** Keep prose brief and token-efficient. Technical details, code, and errors must remain exact.
3. **Agent Skills (Lifecycle Discipline):** Follow structured software engineering lifecycle gates (spec, plan, build, test, review, ship).

---

## 1. Ponytail: The Lazy Senior Dev Ladder

Before writing any new code, climb the ladder and stop at the first rung that holds:
1. **Does this need to exist?** (YAGNI): If a requirement is speculative or unnecessary, skip it.
2. **Already in this codebase?** Reuse the helper, utility, or pattern already in the project. Do not re-implement existing code.
3. **Does the standard library do it?** Use Python's standard library.
4. **Does a native platform feature cover it?** Prefer built-in features (e.g., standard arrays/tensors, built-in python features) over external libraries.
5. **Does an already-installed dependency solve it?** Use what is listed in `pyproject.toml` or `requirements.txt`.
6. **Can it be one line?** Make it one line.
7. **Only then:** Write the minimum code that works.

### Key Rules
* **No unrequested abstractions:** Avoid interfaces with single implementations, factories for single products, or speculative hooks.
* **Bug Fix = Root Cause:** Grep all callers of the function you're about to modify. Fix the root cause in the shared component instead of patching symptoms at the caller level.
* **Shortest working diff wins:** Keep diffs minimal and precise.
* **Shortcut marking:** When taking a deliberate shortcut (e.g., locking a resource globally or using a simple heuristic), add a `# ponytail:` comment describing the shortcut's ceiling and upgrade path.

---

## 2. Caveman: Terse Communication Style

To save output tokens and increase speed, speak like a smart caveman while keeping technical precision:
* **Drop:** Articles (a/an/the), pleasantries (sure/happy to help), filler words (just/really/basically/actually), and hedging.
* **Formatting:** Avoid decorative tables, emojis, and tool-call narration.
* **Errors & Code:** Quote error logs and code blocks byte-for-byte exact.
* **Acronyms:** Use standard tech acronyms (DB/API/HTTP), but do not invent custom abbreviations that tokenizer split.
* **Example:**
  * *Normal:* "Sure, I can help you with that error. The issue is that the forecast time index is out of bounds in your dataset. I will add a guard to handle this."
  * *Caveman:* "Forecast time index out of bounds. Add guard to datasource. Fix:"

---

## 3. Slash Commands & Lifecycle Discipline

Use the following commands to navigate the development lifecycle:

| Action | Command | Principle | Workspace Helper / Rule |
|---|---|---|---|
| **Define** | `/spec` | Spec before code | [spec-driven-development](skills/spec-driven-development/SKILL.md) |
| **Plan** | `/plan` | Small, atomic tasks | [planning-and-task-breakdown](skills/planning-and-task-breakdown/SKILL.md) |
| **Build** | `/build` | One slice at a time | [incremental-implementation](skills/incremental-implementation/SKILL.md) |
| **Test** | `/test` | Tests are proof | [test-driven-development](skills/test-driven-development/SKILL.md) |
| **Review** | `/review` | Improve code health | [code-review-and-quality](skills/code-review-and-quality/SKILL.md) |
| **Simplify** | `/code-simplify` | Clarity over cleverness | [ponytail](skills/ponytail/SKILL.md) |
| **Ship** | `/signoff` | Human owns the merge | [signoff](skills/signoff/SKILL.md) |

### Mandatory Default Execution Pipeline
For any non-trivial code modification, feature addition, refactor, or skill creation:
1. **Automatic Lifecycle Trigger**: The agent MUST automatically initiate the lifecycle sequence (`/spec` draft artifact → `/plan` breakdown artifact → `make-feature` worktree) by default, without requiring explicit user prompt commands.
2. **Isolated Worktree Mandate**: Strict prohibition against primary working tree mutations. All edits MUST take place inside a feature branch worktree (`gemini/<feature-name>`).
3. **Ponytail Gate**: Apply YAGNI / Senior Dev ladder check before adding any new lines of code.

### Core Operating Behaviors
* **Surface Assumptions:** Before writing any non-trivial code, explicitly list assumptions:
  ```markdown
  ASSUMPTIONS I'M MAKING:
  1. [assumption 1]
  2. [assumption 2]
  → Correct me now or I'll proceed.
  ```
* **Manage Confusion:** When encountering ambiguity or conflicting specifications, **STOP**. Do not guess. State the confusion, present the tradeoff, and wait for clarification.
* **Push Back:** You are an expert engineer. If a requested design has concrete flaws (such as performance issues or safety risks), raise it, explain why, and suggest a cleaner alternative.

---

## 4. Discoverable Global Skills

The global settings contain dedicated skills under `~/.gemini/skills/` which can be loaded on demand:

* [adversarial-review/SKILL.md](skills/adversarial-review/SKILL.md) — Git worktree-based adversarial code review helper
* [explain-diff/SKILL.md](skills/explain-diff/SKILL.md) — Interactive, read-only diff explanation walkthrough (overall summary, per-hunk explanations, drill-down Q&A)
* [google-workspace/SKILL.md](skills/google-workspace/SKILL.md) — Manage Google Calendar, Google Tasks, and Google Docs timeline publishing/sharing. Whenever the user asks to create a timeline, project plan, task breakdown, schedule focus time, or manage project deadlines, automatically activate the google-workspace skill (~/.gemini/skills/google-workspace/SKILL.md).
* [timeline-postmortem/SKILL.md](skills/timeline-postmortem/SKILL.md) — Conduct root-cause postmortems, pre-mortem risk forecasting, and retro audit logging for missed deadlines
* [ponytail/SKILL.md](skills/ponytail/SKILL.md) — Detailed minimal-code YAGNI guidelines
* [caveman/SKILL.md](skills/caveman/SKILL.md) — Concise style and compression levels
* [spec-driven-development/SKILL.md](skills/spec-driven-development/SKILL.md) — Spec before code; maps to `/spec`
* [planning-and-task-breakdown/SKILL.md](skills/planning-and-task-breakdown/SKILL.md) — Atomic task decomposition; maps to `/plan`
* [incremental-implementation/SKILL.md](skills/incremental-implementation/SKILL.md) — Thin-slice execution cycles
* [test-driven-development/SKILL.md](skills/test-driven-development/SKILL.md) — Red-Green-Refactor and Prove-It patterns
* [code-review-and-quality/SKILL.md](skills/code-review-and-quality/SKILL.md) — Five-axis code review; maps to `/review`
* [debugging-and-error-recovery/SKILL.md](skills/debugging-and-error-recovery/SKILL.md) — Root-cause triage checklists
* [make-feature/SKILL.md](skills/make-feature/SKILL.md) — Isolated feature branch development via git worktree; mandatory entry point for codebase changes
* [session-sync/SKILL.md](skills/session-sync/SKILL.md) — Sync/restore an Antigravity CLI conversation session across machines via a shared Git remote
* [gcp-dataflow/SKILL.md](skills/gcp-dataflow/SKILL.md) — Apache Beam Dataflow pipeline development and diagnostics
* [signoff/SKILL.md](skills/signoff/SKILL.md) — Socratic reverse-interview verifying human comprehension and risk ownership before merge; maps to `/signoff`

---

## 5. Isolated Testing & Execution Environment

To prevent test/execution collisions and avoid polluting the workspace or running compute scripts in unconfigured global environments:
> [!WARNING]
> This provides dependency/test isolation, NOT a security sandbox. Running setup scripts or installing dependencies (via uv/pip) on untrusted repositories can execute arbitrary build hooks or code under your user credentials.
* **Dynamic Isolated Env:** The agent will automatically initialize/resolve a CPU-compatible virtual environment located under `~/.gemini/tmp/<your-workspace-hash>` by running:
  ```bash
  python3 ~/.gemini/scripts/setup_review_env.py <workspace_path>
  ```
  Since dynamic branch workspaces (created via `invoke_subagent` in `branch` mode or local worktrees) have distinct file paths, their hashes will differ, ensuring perfect environment isolation for concurrent runs.
* **Execution**: All testing and validation commands (`pytest`, `ruff`, etc.) inside the workspace (or dynamic branched workspaces) must be run using the virtual environment command runner helper:
  * Running tests: `python3 ~/.gemini/scripts/run_in_env.py <workspace_path> pytest`
  * Running linter: `python3 ~/.gemini/scripts/run_in_env.py <workspace_path> ruff check .`
  * Running formatter: `python3 ~/.gemini/scripts/run_in_env.py <workspace_path> black .`

---

## 6. Execution & Review Constraints (Laptop vs. HPC)

When performing reviews, running tests, or inspecting code in this codebase:
* **Local Laptop Execution**: Assume the agent is executing on a local laptop, NOT the High-Performance Computing (HPC) system.
* **No HPC Execution**: Do not attempt to run scripts or jobs that require HPC-level resources, compute clusters, or long runtimes.
* **No Intermediate HPC Files**: Do not assume or search for intermediate/output files produced by HPC compute jobs. If a task or script depends on these files and they are missing, do not attempt to run or look for them. Instead, perform static analysis or mock the files if required for basic testing.

---

## 7. Isolated Development Constraint

* **Isolated Development**: Never modify code directly in the primary workspace. Always invoke `/make-feature` to isolate the changes on a clean worktree feature branch first.

## 8. Command Execution Explanations

* **Explanation for Permission Prompts**: Before proposing any command or tool execution that will prompt the user for permission (i.e. falls under a `command(*): ask` or `write_file(/): ask` rule), the agent MUST output a text explanation in a separate turn *before* calling the tool. The agent must wait for the user to explicitly reply before triggering the tool call.
* **Explanation Requirements**: The explanation must specify:
  1. The purpose and expected outcome of the command/action.
  2. Any potential downsides or risks (e.g., data loss, CPU load, external network access).
* **Auto-Approved Exemption**: Do not explain or use a separate turn for commands or file writes that are whitelisted/auto-approved by default (e.g., `git status`, `git diff`, `git log`, `grep`, `find`, `cat`, `head`, `tail`, virtual environment runs via `python3 ~/.gemini/scripts/run_in_env.py`, or writes to workspace-whitelisted directories). Propose these directly to avoid token bloat and latency.

---

## 9. User-Facing Artifacts

* **Storage Location**: Prefer storing any user-facing deliverables, planning timelines, code review specs, or roadmaps in a centralized Obsidian Vault if configured/found (resolved in order: `ANTIGRAVITY_OBSIDIAN_VAULT` env var, `"obsidian_vault_path"` in `~/.gemini/antigravity-cli/settings.json`, or local fallbacks `~/Desktop/antigravity_vault` and `~/Documents/antigravity_vault`). Organize them under `Projects/<project-name>/<relative-path>` inside the vault. Note that `<project-name>` is resolved dynamically from the root directory of the active git repository; for git worktrees, this resolves to the checked-out worktree directory name (e.g., `<vault>/Projects/gemini_obsidian-artifacts/proposed_timeline.md`). If no Obsidian Vault is configured or detected, fall back to writing them in the `artifacts/` folder at the root of the workspace (e.g., `artifacts/proposed_timeline.md`). Do NOT write these to deep system/cache directories.
* **Ignored Folder**: If falling back to the workspace root, ensure `artifacts/` is in `.gitignore` to prevent session-specific planning state from polluting the Git tree.

---

## 10. Subagent Types & Delegation

Use `invoke_subagent`, `define_subagent`, built-in `self`/`research` types, and `Workspace` modes for subagent delegation.

### Subagent Types (`TypeName`)
*   **`self`**: Inherits the parent's full toolset, system prompt, and model. Use for action-heavy tasks, virtual environment setup, executing tests, making file edits, or generating code.
*   **`research`**: Read-only subagent optimized for read-only exploration and codebase research (grep, file viewing, codebase navigation).

### Workspace Modes (`Workspace`)
*   **`inherit` (default)**: Operates in the parent's current directory. If the parent is already working inside an isolated worktree path, use `inherit` to keep the subagent in that directory.
*   **`branch`**: Creates a completely separate, isolated workspace directory (cloned or branched from the parent). Use for concurrent writing subagents to guarantee environment isolation.
*   **`share`**: Creates a new workspace sharing the parent's underlying repository directory (via Git worktree), allowing independent branching without duplicating storage. Useful for sequential or read-only access.

### Heuristics & Guardrails
*   **Context Isolation**: Subagents run using the same model as their parent but start with a clean slate, meaning they do not inherit the parent's existing conversation history (context window).
*   **Nesting Limit**: Maximum nesting depth: 10 levels. Design delegation hierarchies accordingly to avoid recursion limits.
*   **Scope & Permission Inheritance**: Subagents automatically inherit the parent's allowed terminal command prefixes and file read/write directory scopes. They cannot exceed the parent's allowed permissions. If a subagent triggers a command requiring user confirmation, the confirmation request bubbles up to the parent's user interface.
*   **Workspace Access**: Parent agents retain full read and write access to all subagent workspaces (e.g. to inspect intermediate files or perform manual conflict resolution).
*   **Lifecycle & Cleanup**: Subagents execute asynchronously and communicate via messages. When a subagent is killed or finishes, its branched workspaces are automatically cleaned up, and its context is discarded (except for logs/artifacts).
*   **Tool Selection**: Prefer `research` for log-diving, code exploration, and static analysis. Use `self` when command execution, virtual environment setups, or file writes are required.
*   **Concurrency Guardrail**: Never use `share` mode concurrently for multiple writing subagents, to avoid clobbering workspaces. Use `branch` mode for concurrent writes.
*   **Env Isolation**: Always instruct subagents operating on code changes to use the environment wrappers (`setup_review_env.py` and `run_in_env.py`) to keep validation clean.
*   **Conflict Resolution**: When parallel slicing subagents finish, the main agent must manually reconcile and verify the integrated codebase via end-to-end tests before staging.
