"""Persistent approval state for the principled development lifecycle."""

import fcntl
import hashlib
import json
import os
import tempfile
import threading
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


class StateConflict(StateError):
    """State changed after a caller captured its expected record token."""


_HELD_LOCKS = set()
_HELD_LOCKS_GUARD = threading.Lock()


class FileLock:
    """Exclusive POSIX advisory lock backed by a sidecar file."""

    def __init__(self, path):
        self.path = Path(path)
        self._file = None

    def __enter__(self):
        self.path = self.path.resolve(strict=False)
        with _HELD_LOCKS_GUARD:
            if self.path in _HELD_LOCKS:
                raise StateError(f"reentrant state lock: {self.path}")
            _HELD_LOCKS.add(self.path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self.path.open("a+")
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX)
        except OSError as error:
            if self._file is not None:
                self._file.close()
                self._file = None
            with _HELD_LOCKS_GUARD:
                _HELD_LOCKS.discard(self.path)
            raise StateError("state lock cannot be acquired") from error
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()
        except OSError as error:
            raise StateError("state lock cannot be released") from error
        finally:
            self._file = None
            with _HELD_LOCKS_GUARD:
                _HELD_LOCKS.discard(self.path)


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
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")
        with FileLock(self.lock_path):
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
        with FileLock(self.lock_path):
            document = self._load()
            record = document["records"].setdefault(
                key, {"artifacts": {}, "approvals": {}, "metadata": {}}
            )
            record.setdefault("metadata", {})
            if record["artifacts"].get(gate) == digest:
                self._document = document
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
        with FileLock(self.lock_path):
            document = self._load()
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
                self._document = document
                return digest
            record["approvals"][gate] = digest
            self._save(document)
            self._document = document
            return digest

    @staticmethod
    def _record_token(document, key):
        record = document["records"].get(key)
        canonical = json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return content_digest(canonical)

    def record_token(self, repository, feature):
        """Return canonical SHA-256 token for current record, refreshing from disk."""
        key = _record_key(repository, feature)
        with FileLock(self.lock_path):
            self._document = self._load()
            return self._record_token(self._document, key)

    def require_approved_and_token(self, repository, feature, gate, content=None):
        """Atomically verify gate approval and return token for that exact record."""
        gate = self._gate(gate)
        key = _record_key(repository, feature)
        with FileLock(self.lock_path):
            self._document = self._load()
            record = self._document["records"].get(key)
            digest = record and record["artifacts"].get(gate)
            if (
                not digest
                or record["approvals"].get(gate) != digest
                or (content is not None and content_digest(content) != digest)
            ):
                raise GateError(f"{gate} approval is required")
            return self._record_token(self._document, key)

    def publication_snapshot(self, repository, feature):
        """Atomically return publication metadata and its exact record token."""
        key = _record_key(repository, feature)
        with FileLock(self.lock_path):
            self._document = self._load()
            record = self._document["records"].get(key)
            metadata = dict((record or {}).get("metadata", {}))
            required = ("remote_sha", "published_remote", "review_digest")
            if not record or any(not metadata.get(name) for name in required):
                raise StateError("persisted publication state is required")
            return metadata, self._record_token(self._document, key)

    def assert_token(self, repository, feature, expected_token):
        if not _is_digest(expected_token):
            raise StateError("malformed expected state token")
        if self.record_token(repository, feature) != expected_token:
            raise StateConflict("state record changed")

    def with_valid_token(self, repository, feature, expected_token, callback):
        """Run callback while holding lock if current record matches expected token."""
        if not _is_digest(expected_token):
            raise StateError("malformed expected state token")
        key = _record_key(repository, feature)
        with FileLock(self.lock_path):
            self._document = self._load()
            if self._record_token(self._document, key) != expected_token:
                raise StateConflict("state record changed")
            try:
                return callback()
            except RuntimeError as error:
                if "reentrant file lock" in str(error):
                    raise StateError("reentrant state access from locked callback") from error
                raise

    def set_metadata(self, repository, feature, *, expected_token=None, **values):
        unknown = set(values) - _METADATA_KEYS
        if unknown:
            raise StateError(f"unknown metadata: {sorted(unknown)}")
        if expected_token is not None and not _is_digest(expected_token):
            raise StateError("malformed expected state token")
        key = _record_key(repository, feature)
        with FileLock(self.lock_path):
            document = self._load()
            if expected_token is not None and self._record_token(document, key) != expected_token:
                self._document = document
                raise StateConflict("state record changed")
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
        with FileLock(self.lock_path):
            self._document = self._load()
            record = self._document["records"].get(_record_key(repository, feature), {})
            return dict(record.get("metadata", {}))

    def find_metadata_for_path(self, path):
        target = Path(path).resolve(strict=False)
        matches = []
        with FileLock(self.lock_path):
            self._document = self._load()
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
        with FileLock(self.lock_path):
            self._document = self._load()
            record = self._document["records"].get(key)
            if record is None:
                return False
            artifact_digest = record["artifacts"].get(gate)
            if artifact_digest is None or record["approvals"].get(gate) != artifact_digest:
                return False
            return content is None or content_digest(content) == artifact_digest
