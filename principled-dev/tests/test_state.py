import importlib.util
import json
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "principled_dev" / "state.py"
SPEC = importlib.util.spec_from_file_location("principled_dev_state", MODULE_PATH)
state = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = state
SPEC.loader.exec_module(state)


def test_state_is_keyed_by_repository_and_feature(tmp_path):
    store = state.StateStore(tmp_path / "state.json")

    store.set_artifact("repo-a", "feature-a", "spec", "same spec")
    store.approve("repo-a", "feature-a", "spec")

    assert store.is_approved("repo-a", "feature-a", "spec", "same spec")
    assert not store.is_approved("repo-b", "feature-a", "spec", "same spec")
    assert not store.is_approved("repo-a", "feature-b", "spec", "same spec")


def test_approvals_are_bound_to_content_digest(tmp_path):
    store = state.StateStore(tmp_path / "state.json")
    expected_digest = state.content_digest("approved spec")

    assert store.set_artifact("repo", "feature", "spec", "approved spec") == expected_digest
    assert store.approve("repo", "feature", "spec") == expected_digest
    assert store.is_approved("repo", "feature", "spec", "approved spec")
    assert not store.is_approved("repo", "feature", "spec", "edited spec")

    document = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    record = next(iter(document["records"].values()))
    assert record["artifacts"]["spec"] == expected_digest
    assert record["approvals"]["spec"] == expected_digest


def test_gate_approvals_are_sequential(tmp_path):
    store = state.StateStore(tmp_path / "state.json")
    store.set_artifact("repo", "feature", "plan", "plan")

    with pytest.raises(state.GateError, match="spec approval"):
        store.approve("repo", "feature", "plan")

    store.set_artifact("repo", "feature", "spec", "spec")
    store.approve("repo", "feature", "spec")
    store.approve("repo", "feature", "plan")
    store.set_artifact("repo", "feature", "build", "source tree")
    store.approve("repo", "feature", "build")

    assert store.is_approved("repo", "feature", "build")

    other = state.StateStore(tmp_path / "other.json")
    other.set_artifact("repo", "feature", "build", "source tree")
    with pytest.raises(state.GateError, match="plan approval"):
        other.approve("repo", "feature", "build")


def test_changed_artifact_invalidates_its_and_downstream_approvals(tmp_path):
    store = state.StateStore(tmp_path / "state.json")
    for gate, content in (("spec", "spec v1"), ("plan", "plan v1"), ("build", "build v1")):
        store.set_artifact("repo", "feature", gate, content)
        store.approve("repo", "feature", gate)

    store.set_artifact("repo", "feature", "plan", "plan v2")

    assert store.is_approved("repo", "feature", "spec")
    assert not store.is_approved("repo", "feature", "plan")
    assert not store.is_approved("repo", "feature", "build")

    store.set_artifact("repo", "feature", "spec", "spec v2")

    assert not store.is_approved("repo", "feature", "spec")
    assert not store.is_approved("repo", "feature", "plan")
    assert not store.is_approved("repo", "feature", "build")


def test_persistence_is_versioned_atomic_and_reloadable(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    replacements = []
    real_replace = state.os.replace

    def observe_replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        assert Path(source).parent == path.parent
        assert Path(source) != path
        real_replace(source, destination)

    monkeypatch.setattr(state.os, "replace", observe_replace)
    store = state.StateStore(path)
    store.set_artifact("repo", "feature", "spec", "spec")
    store.approve("repo", "feature", "spec")

    assert replacements
    assert all(destination == path for _, destination in replacements)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == state.STATE_VERSION
    assert state.StateStore(path).is_approved("repo", "feature", "spec", "spec")
    assert not list(tmp_path.glob(f".{path.name}.*.tmp"))


def test_state_excludes_artifacts_credentials_and_transcripts(tmp_path):
    path = tmp_path / "state.json"
    repository = "https://alice:super-secret@example.invalid/owner/repo.git"
    artifact = "password=hunter2\nAuthorization: Bearer token-value"
    transcript = "human said APPROVE in private conversation"

    store = state.StateStore(path)
    store.set_artifact(repository, "feature", "spec", artifact + transcript)
    store.approve(repository, "feature", "spec")

    persisted = path.read_text(encoding="utf-8")
    for sensitive in (repository, "alice", "super-secret", artifact, "hunter2", "token-value", transcript):
        assert sensitive not in persisted
    assert state.content_digest(artifact + transcript) in persisted


def test_malformed_and_unknown_state_versions_fail_closed(tmp_path):
    cases = (
        "not json",
        json.dumps({"version": state.STATE_VERSION + 1, "records": {}}),
        json.dumps({"version": state.STATE_VERSION, "records": []}),
        json.dumps(
            {
                "version": state.STATE_VERSION,
                "records": {
                    "0" * 64: {
                        "artifacts": {"spec": state.content_digest("spec")},
                        "approvals": {"plan": state.content_digest("plan")},
                    }
                },
            }
        ),
    )

    for index, persisted in enumerate(cases):
        path = tmp_path / f"state-{index}.json"
        path.write_text(persisted, encoding="utf-8")
        with pytest.raises(state.StateError):
            state.StateStore(path)
        assert path.read_text(encoding="utf-8") == persisted
