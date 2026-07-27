import multiprocessing
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import principled_dev.state as state
from principled_dev.state import StateStore


def _record_approved_spec(path, repository, barrier):
    store = StateStore(path)
    barrier.wait(timeout=10)
    store.set_artifact(repository, "agent/topic", "spec", repository)
    store.approve(repository, "agent/topic", "spec")


def _persist_stale_publication(path, captured, invalidated, result):
    store = StateStore(path)
    token = store.record_token("repo", "agent/topic")
    captured.set()
    if not invalidated.wait(timeout=10):
        result.put("invalidation timed out")
        return
    try:
        store.set_metadata(
            "repo",
            "agent/topic",
            expected_token=token,
            remote_sha="2" * 40,
            published_remote="origin",
            review_digest="8" * 64,
        )
    except Exception as error:
        result.put(type(error).__name__)
    else:
        result.put("saved")


def _invalidate_build(path, captured, invalidated):
    if not captured.wait(timeout=10):
        return
    StateStore(path).set_artifact("repo", "agent/topic", "build", "changed build")
    invalidated.set()


def _fork_access_state(path, parent_locked, attempted, completed, result):
    if not parent_locked.wait(timeout=10):
        result.put("parent lock timed out")
        return
    attempted.set()
    try:
        result.put(StateStore(path).record_token("repo", "agent/topic"))
    except Exception as error:
        result.put(f"{type(error).__name__}: {error}")
    finally:
        completed.set()


def _join(processes):
    for process in processes:
        process.join(timeout=15)
        if process.is_alive():
            process.terminate()
            process.join()
        assert process.exitcode == 0


def test_forked_child_drops_inherited_registry_and_waits_for_parent_lock(tmp_path):
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("multiprocessing fork is unavailable")
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.set_artifact("repo", "agent/topic", "spec", "spec")
    token = store.record_token("repo", "agent/topic")
    context = multiprocessing.get_context("fork")
    parent_locked = context.Event()
    attempted = context.Event()
    completed = context.Event()
    result = context.Queue()
    process = context.Process(
        target=_fork_access_state,
        args=(path, parent_locked, attempted, completed, result),
    )

    def while_locked():
        process.start()
        parent_locked.set()
        assert attempted.wait(timeout=10)
        assert not completed.wait(timeout=0.2)
        assert state._HELD_LOCKS
        assert state._ACTIVE_LOCK_FILES

    store.with_valid_token("repo", "agent/topic", token, while_locked)
    assert completed.wait(timeout=10)
    _join((process,))
    assert result.get(timeout=2) == token
    assert not state._HELD_LOCKS
    assert not state._ACTIVE_LOCK_FILES
    assert store.record_token("repo", "agent/topic") == token


def test_forked_child_replaces_inherited_locked_registry_guard(tmp_path):
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("multiprocessing fork is unavailable")
    path = tmp_path / "state.json"
    store = StateStore(path)
    token = store.record_token("repo", "agent/topic")
    context = multiprocessing.get_context("fork")
    parent_locked = context.Event()
    attempted = context.Event()
    completed = context.Event()
    result = context.Queue()
    process = context.Process(
        target=_fork_access_state,
        args=(path, parent_locked, attempted, completed, result),
    )

    state._HELD_LOCKS_GUARD.acquire()
    try:
        process.start()
    finally:
        state._HELD_LOCKS_GUARD.release()
    parent_locked.set()

    assert completed.wait(timeout=10)
    _join((process,))
    assert result.get(timeout=2) == token


def test_concurrent_writers_do_not_lose_records(tmp_path):
    context = multiprocessing.get_context("spawn")
    path = tmp_path / "state.json"
    barrier = context.Barrier(2)
    processes = [
        context.Process(target=_record_approved_spec, args=(path, repository, barrier))
        for repository in ("repo-a", "repo-b")
    ]

    for process in processes:
        process.start()
    _join(processes)

    store = StateStore(path)
    assert store.is_approved("repo-a", "agent/topic", "spec", "repo-a")
    assert store.is_approved("repo-b", "agent/topic", "spec", "repo-b")


def test_stale_writer_cannot_restore_invalidated_approval_or_publication(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    for gate in ("spec", "plan", "build"):
        store.set_artifact("repo", "agent/topic", gate, gate)
        store.approve("repo", "agent/topic", gate)
    store.set_metadata(
        "repo",
        "agent/topic",
        remote_sha="2" * 40,
        published_remote="origin",
        review_digest="8" * 64,
    )

    context = multiprocessing.get_context("spawn")
    captured = context.Event()
    invalidated = context.Event()
    result = context.Queue()
    processes = (
        context.Process(
            target=_persist_stale_publication,
            args=(path, captured, invalidated, result),
        ),
        context.Process(
            target=_invalidate_build,
            args=(path, captured, invalidated),
        ),
    )

    for process in processes:
        process.start()
    _join(processes)

    assert result.get(timeout=2) == "StateConflict"
    refreshed = StateStore(path)
    assert not refreshed.is_approved("repo", "agent/topic", "build")
    metadata = refreshed.get_metadata("repo", "agent/topic")
    assert "remote_sha" not in metadata
    assert "published_remote" not in metadata
    assert "review_digest" not in metadata
