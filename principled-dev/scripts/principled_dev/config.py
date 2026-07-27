import os
from pathlib import Path


def roots():
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    worktrees = Path(
        os.environ.get(
            "PRINCIPLED_DEV_WORKTREE_ROOT",
            cache_home / "principled-dev" / "worktrees",
        )
    ).expanduser()
    state = Path(
        os.environ.get(
            "PRINCIPLED_DEV_STATE_ROOT", state_home / "principled-dev"
        )
    ).expanduser()
    return worktrees, state
