import hashlib
import re
from pathlib import Path

from .git import Git, GitError, repository_id
from .signoff import create_attestation
from .state import GateError, StateConflict
from .worktrees import WorktreeManager


_URL_USERINFO = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@")
_QUERY_SECRET = re.compile(
    r"([?&][^=&#\s]*(?:token|password|passwd|pwd|secret|api[_-]?key)[^=&#\s]*=)[^&#\s]*",
    re.IGNORECASE,
)


def _redact(value):
    if value is None:
        return None
    value = _URL_USERINFO.sub(r"\1[REDACTED]@", str(value))
    return _QUERY_SECRET.sub(r"\1[REDACTED]", value)


class LifecycleError(RuntimeError):
    pass


class PublicationPartialSuccess(LifecycleError):
    """Remote publication succeeded but local state compare-and-swap failed."""

    def __init__(self, remote, branch, pushed_sha, *, phase="local_state_persistence", observed_sha=None, cause=None):
        self.remote = _redact(remote)
        self.branch = _redact(branch)
        self.pushed_sha = pushed_sha
        self.phase = phase
        self.observed_sha = _redact(observed_sha)
        self.cause = _redact(cause)
        super().__init__(
            f"publication succeeded on remote {self.remote} branch {self.branch} "
            f"at intended SHA {pushed_sha}, but {phase} failed"
            + (f": {self.cause}" if self.cause else "")
        )


class Lifecycle:
    def __init__(
        self,
        repository,
        worktree_root,
        state,
        *,
        feature_branch="agent/feature",
        base_branch="main",
    ):
        self.repository = Path(repository).resolve()
        self.git = Git(self.repository)
        self.state = state
        self.repository_id = repository_id(self.repository)
        self.feature_branch = feature_branch
        self.base_branch = base_branch
        self.worktrees = WorktreeManager(self.repository, worktree_root)
        self.feature_worktree = None
        self.base_sha = None
        self.remote_sha = None
        self.published_remote = None
        self.review_digest = None
        self._manifest = None
        metadata = self.state.get_metadata(self.repository_id, self.feature_branch)
        if metadata:
            self.base_branch = metadata.get("base_branch", self.base_branch)
            self.base_sha = metadata.get("base_sha")
            self.remote_sha = metadata.get("remote_sha")
            self.published_remote = metadata.get("published_remote")
            self.review_digest = metadata.get("review_digest")
            if metadata.get("feature_worktree"):
                self.feature_worktree = Path(metadata["feature_worktree"])
            manifest_keys = (
                "manifest_commit_sha",
                "manifest_tree_sha",
                "manifest_diff_digest",
            )
            if all(metadata.get(key) for key in manifest_keys):
                self._manifest = {
                    "base_sha": self.base_sha,
                    "commit_sha": metadata["manifest_commit_sha"],
                    "tree_sha": metadata["manifest_tree_sha"],
                    "diff_digest": metadata["manifest_diff_digest"],
                }

    def record_artifact(self, gate, content):
        return self.state.set_artifact(
            self.repository_id, self.feature_branch, gate, content
        )

    def approve(self, gate):
        return self.state.approve(self.repository_id, self.feature_branch, gate)

    def create_feature(self, base_revision):
        if not self.state.is_approved(
            self.repository_id, self.feature_branch, "plan"
        ):
            raise LifecycleError("approved plan is required before feature creation")
        self.base_sha = self.git.resolve_commit(base_revision)
        try:
            self.feature_worktree = self.worktrees.create_feature(
                self.feature_branch, self.base_sha
            )
        except (GitError, RuntimeError, ValueError) as error:
            raise LifecycleError(str(error)) from error
        self.state.set_metadata(
            self.repository_id,
            self.feature_branch,
            base_branch=self.base_branch,
            base_sha=self.base_sha,
            feature_branch=self.feature_branch,
            feature_worktree=str(self.feature_worktree),
        )
        return self.feature_worktree

    def _feature_git(self):
        if self.feature_worktree is None:
            raise LifecycleError("feature worktree has not been created")
        return Git(self.feature_worktree)

    def _diff_bytes(self, commit_sha):
        result = self.git.run(
            "diff", "--binary", f"{self.base_sha}...{commit_sha}"
        )
        return result.stdout.encode()

    def bind_manifest(self, summary):
        feature = self._feature_git()
        if feature.is_dirty():
            raise LifecycleError("commit changes before binding manifest")
        commit_sha = feature.head()
        tree_sha = feature.run("rev-parse", "HEAD^{tree}").stdout.strip()
        self._manifest = {
            "summary": summary,
            "base_sha": self.base_sha,
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
            "diff_digest": hashlib.sha256(self._diff_bytes(commit_sha)).hexdigest(),
        }
        self.state.set_metadata(
            self.repository_id,
            self.feature_branch,
            manifest_commit_sha=commit_sha,
            manifest_tree_sha=tree_sha,
            manifest_diff_digest=self._manifest["diff_digest"],
        )
        return dict(self._manifest)

    def approve_manifest(self, manifest):
        comparable = {key: value for key, value in manifest.items() if key != "summary"}
        current = {key: value for key, value in (self._manifest or {}).items() if key != "summary"}
        if comparable != current or not self.manifest_is_fresh():
            raise LifecycleError("manifest is stale")
        self.record_artifact("build", self._manifest_bytes())
        return self.approve("build")

    def _manifest_bytes(self):
        manifest = self._manifest or {}
        return "\n".join(
            f"{key}={manifest[key]}" for key in sorted(manifest) if key != "summary"
        )

    def manifest_is_fresh(self):
        if not self._manifest or self.feature_worktree is None:
            return False
        feature = self._feature_git()
        if feature.is_dirty() or feature.head() != self._manifest["commit_sha"]:
            return False
        tree = feature.run("rev-parse", "HEAD^{tree}").stdout.strip()
        if tree != self._manifest["tree_sha"]:
            return False
        digest = hashlib.sha256(self._diff_bytes(feature.head())).hexdigest()
        return digest == self._manifest["diff_digest"]

    def publish(self, review, remote=None):
        if self.feature_branch == self.base_branch:
            raise LifecycleError("integration branch cannot be a publication target")
        if review is None or review.verdict != "APPROVE":
            raise LifecycleError("APPROVE review is required before publication")
        feature = self._feature_git()
        head = feature.head()
        tree = feature.run("rev-parse", "HEAD^{tree}").stdout.strip()
        if not review.is_fresh(self.base_sha, head, tree):
            raise LifecycleError("reviewed SHA is stale")
        if not self.manifest_is_fresh():
            raise LifecycleError("approved fresh manifest is required before publication")
        if feature.is_dirty():
            raise LifecycleError("feature worktree is dirty")
        remote = remote or feature.run(
            "config", "--get", f"branch.{self.base_branch}.remote", check=False
        ).stdout.strip() or "origin"
        configured_remotes = set(feature.run("remote").stdout.splitlines())
        if "/" in remote or remote not in configured_remotes:
            raise LifecycleError("configured remote alias is required")
        try:
            review_digest = review.digest()
        except Exception as error:
            raise LifecycleError("review digest cannot be computed") from error
        refspec = f"{head}:refs/heads/{self.feature_branch}"
        try:
            expected_token = self.state.require_approved_and_token(
                self.repository_id,
                self.feature_branch,
                "build",
                self._manifest_bytes(),
            )
        except GateError as error:
            raise LifecycleError("approved fresh manifest is required before publication") from error
        try:
            feature.run("push", remote, refspec)
        except GitError as error:
            raise LifecycleError("publication failed before remote accepted push") from error
        try:
            fields = feature.run(
                "ls-remote", remote, f"refs/heads/{self.feature_branch}"
            ).stdout.split()
            remote_sha = fields[0]
            if remote_sha != head:
                raise PublicationPartialSuccess(
                    remote,
                    self.feature_branch,
                    head,
                    phase="remote_mismatch",
                    observed_sha=remote_sha,
                    cause=f"observed {remote_sha}",
                )
        except PublicationPartialSuccess:
            raise
        except Exception as error:
            raise PublicationPartialSuccess(
                remote,
                self.feature_branch,
                head,
                phase="remote_verification",
                cause=str(error),
            ) from error
        try:
            self.state.set_metadata(
                self.repository_id,
                self.feature_branch,
                expected_token=expected_token,
                remote_sha=remote_sha,
                published_remote=remote,
                review_digest=review_digest,
            )
        except Exception as error:
            raise PublicationPartialSuccess(
                remote,
                self.feature_branch,
                remote_sha,
                phase="local_state_persistence",
                observed_sha=remote_sha,
                cause=str(error),
            ) from error
        self.remote_sha = remote_sha
        self.published_remote = remote
        self.review_digest = review_digest
        return {
            "remote": remote,
            "branch": self.feature_branch,
            "pushed_sha": head,
            "review_digest": review_digest,
        }

    def signoff(self, review, *, human_reviewed, identity, emitter=None, **details):
        try:
            metadata, token = self.state.publication_snapshot(
                self.repository_id, self.feature_branch
            )

            def attest_and_emit():
                attestation = create_attestation(
                    self.feature_worktree,
                    review,
                    human_reviewed=human_reviewed,
                    identity=identity,
                    published_remote=metadata["published_remote"],
                    published_branch=self.feature_branch,
                    published_sha=metadata["remote_sha"],
                    expected_review_digest=metadata["review_digest"],
                    **details,
                )
                if emitter is not None:
                    emitter(attestation)
                return attestation

            return self.state.with_valid_token(
                self.repository_id,
                self.feature_branch,
                token,
                attest_and_emit,
            )
        except StateConflict as error:
            raise LifecycleError("state changed during signoff") from error
