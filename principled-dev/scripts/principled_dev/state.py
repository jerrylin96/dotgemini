"""Persistent approval state for the principled development lifecycle."""

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path


STATE_VERSION = 1
GATES = ("spec", "plan", "build")
_METADATA_SHA_KEYS = {"base_sha", "manifest_commit_sha", "manifest_tree_sha", "remote_sha"}
_METADATA_DIGEST_KEYS = {"manifest_diff_digest", "review_digest"}
_METADATA_TEXT_KEYS = {"base_branch", "feature_branch", "published_remote"}
_METADATA_PATH_KEYS = {"feature_worktree"}
_METADATA_KEYS = _METADATA_SHA_KEYS | _METADATA_DIGEST_KEYS | _METADATA_TEXT_KEYS | _METADATA_PATH_KEYS
_MANIFEST_KEYS = {"manifest_commit_sha", "manifest_tree_sha", "manifest_diff_digest"}


class StateError(RuntimeError):
    """State cannot be read or safely used."""


class GateError(StateError):
    """A lifecycle gate operation is invalid."""


def content_digest(content):
    """Return the SHA-256 digest of exact text or bytes content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    if not isinstance(content, bytes):
        raise TypeError("content must be str or bytes")
    return hashlib.sha256(content).hexdigest()


def _record_key(repository, feature):
    if not isinstance(repository, str) or not repository:
        raise ValueError("repository identity must be a non-empty string")
    if not isinstance(feature, str) or not feature:
        raise ValueError("feature must be a non-empty string")
    identity = json.dumps([repository, feature], ensure_ascii=False, separators=(",", ":"))
    return content_digest(identity)


def _is_digest(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_object_id(value):
    return (
        isinstance(value, str)
        and 40 <= len(value) <= 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_document(document):
    if not isinstance(document, dict) or set(document) != {"version", "records"}:
        raise StateError("malformed state document")
    if type(document["version"]) is not int or document["version"] != STATE_VERSION:
        raise StateError("unsupported state version")
    records = document["records"]
    if not isinstance(records, dict):
        raise StateError("malformed state records")

    for key, record in records.items():
        if not _is_digest(key):
            raise StateError("malformed state record key")
        if not isinstance(record, dict) or set(record) not in (
            {"artifacts", "approvals"},
            {"artifacts", "approvals", "metadata"},
        ):
            raise StateError("malformed state record")
        artifacts = record["artifacts"]
        approvals = record["approvals"]
        metadata = record.get("metadata", {})
        if not isinstance(artifacts, dict) or not isinstance(approvals, dict):
            raise StateError("malformed artifact or approval state")
        if any(gate not in GATES or not _is_digest(digest) for gate, digest in artifacts.items()):
            raise StateError("malformed artifact state")
        if any(gate not in GATES or not _is_digest(digest) for gate, digest in approvals.items()):
            raise StateError("malformed approval state")
        if not isinstance(metadata, dict) or any(key not in _METADATA_KEYS for key in metadata):
            raise StateError("malformed metadata")
        for key, value in metadata.items():
            if key in _METADATA_SHA_KEYS and not _is_object_id(value):
                raise StateError("malformed metadata SHA")
            if key in _METADATA_DIGEST_KEYS and not _is_digest(value):
                raise StateError("malformed metadata digest")
            if key in _METADATA_TEXT_KEYS and (not isinstance(value, str) or not value):
                raise StateError("malformed metadata text")
            if key in _METADATA_PATH_KEYS and (
                not isinstance(value, str) or not value or not Path(value).is_absolute()
            ):
                raise StateError("malformed metadata path")

        for index, gate in enumerate(GATES):
            if gate not in approvals:
                continue
            if approvals[gate] != artifacts.get(gate):
                raise StateError("approval does not match artifact")
            if index:
                predecessor = GATES[index - 1]
                predecessor_digest = artifacts.get(predecessor)
                if predecessor_digest is None or approvals.get(predecessor) != predecessor_digest:
                    raise StateError("approval sequence is invalid")


class StateStore:
    """Read and atomically persist digest-only lifecycle approval state."""

    def __init__(self, path):
        self.path = Path(path)
        self._document = self._load()

    def _load(self):
        if not self.path.exists():
            return {"version": STATE_VERSION, "records": {}}
        try:
            with self.path.open(encoding="utf-8") as state_file:
                document = json.load(state_file)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise StateError("state document cannot be read") from error
        _validate_document(document)
        return document

    def _save(self, document):
        _validate_document(document)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as state_file:
                    json.dump(document, state_file, sort_keys=True, separators=(",", ":"))
                    state_file.write("\n")
                    state_file.flush()
                    os.fsync(state_file.fileno())
                os.replace(temporary_name, self.path)
            except BaseException:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
                raise
        except OSError as error:
            raise StateError("state document cannot be persisted") from error

    @staticmethod
    def _gate(gate):
        if gate not in GATES:
            raise GateError(f"unknown gate: {gate!r}")
        return gate

    def set_artifact(self, repository, feature, gate, content):
        """Record artifact digest and invalidate its and later approvals if changed."""
        gate = self._gate(gate)
        key = _record_key(repository, feature)
        digest = content_digest(content)
        document = copy.deepcopy(self._document)
        record = document["records"].setdefault(
            key, {"artifacts": {}, "approvals": {}, "metadata": {}}
        )
        record.setdefault("metadata", {})
        if record["artifacts"].get(gate) == digest:
            return digest

        record["artifacts"][gate] = digest
        changed_index = GATES.index(gate)
        for invalidated_gate in GATES[changed_index:]:
            record["approvals"].pop(invalidated_gate, None)
        metadata = record.setdefault("metadata", {})
        metadata.pop("remote_sha", None)
        metadata.pop("published_remote", None)
        metadata.pop("review_digest", None)
        self._save(document)
        self._document = document
        return digest

    def approve(self, repository, feature, gate):
        """Approve current artifact digest if predecessor gate is approved."""
        gate = self._gate(gate)
        key = _record_key(repository, feature)
        document = copy.deepcopy(self._document)
        record = document["records"].get(key)
        if record is None or gate not in record["artifacts"]:
            raise GateError(f"{gate} artifact is not recorded")

        gate_index = GATES.index(gate)
        if gate_index:
            predecessor = GATES[gate_index - 1]
            predecessor_digest = record["artifacts"].get(predecessor)
            if predecessor_digest is None or record["approvals"].get(predecessor) != predecessor_digest:
                raise GateError(f"{predecessor} approval is required before {gate}")

        digest = record["artifacts"][gate]
        if record["approvals"].get(gate) == digest:
            return digest
        record["approvals"][gate] = digest
        self._save(document)
        self._document = document
        return digest

    def set_metadata(self, repository, feature, **values):
        unknown = set(values) - _METADATA_KEYS
        if unknown:
            raise StateError(f"unknown metadata: {sorted(unknown)}")
        key = _record_key(repository, feature)
        document = copy.deepcopy(self._document)
        record = document["records"].setdefault(
            key, {"artifacts": {}, "approvals": {}, "metadata": {}}
        )
        metadata = record.setdefault("metadata", {})
        manifest_changed = any(
            name in values and metadata.get(name) != values[name] for name in _MANIFEST_KEYS
        )
        metadata.update(values)
        if manifest_changed:
            record["approvals"].pop("build", None)
            metadata.pop("remote_sha", None)
            metadata.pop("review_digest", None)
        self._save(document)
        self._document = document
        return dict(metadata)

    def get_metadata(self, repository, feature):
        record = self._document["records"].get(_record_key(repository, feature), {})
        return dict(record.get("metadata", {}))

    def find_metadata_for_path(self, path):
        target = Path(path).resolve(strict=False)
        matches = []
        for record in self._document["records"].values():
            metadata = record.get("metadata", {})
            raw = metadata.get("feature_worktree")
            if not raw:
                continue
            root = Path(raw).resolve(strict=False)
            try:
                target.relative_to(root)
                matches.append((len(root.parts), metadata))
            except ValueError:
                pass
        return dict(max(matches, key=lambda item: item[0])[1]) if matches else {}

    def is_approved(self, repository, feature, gate, content=None):
        """Return whether gate approval matches current and optional supplied content."""
        gate = self._gate(gate)
        key = _record_key(repository, feature)
        record = self._document["records"].get(key)
        if record is None:
            return False
        artifact_digest = record["artifacts"].get(gate)
        if artifact_digest is None or record["approvals"].get(gate) != artifact_digest:
            return False
        return content is None or content_digest(content) == artifact_digest
