import multiprocessing
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

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


def _join(processes):
    for process in processes:
        process.join(timeout=15)
        if process.is_alive():
            process.terminate()
            process.join()
        assert process.exitcode == 0


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
