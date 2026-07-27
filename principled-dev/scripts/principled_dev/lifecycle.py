import hashlib
from pathlib import Path

from .git import Git, GitError, repository_id
from .worktrees import WorktreeManager


class LifecycleError(RuntimeError):
    pass


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
        self._manifest = None

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
        return dict(self._manifest)

    def approve_manifest(self, manifest):
        if manifest != self._manifest or not self.manifest_is_fresh():
            raise LifecycleError("manifest is stale")
        return self.record_artifact("build", self._manifest_bytes())

    def _manifest_bytes(self):
        manifest = self._manifest or {}
        return "\n".join(f"{key}={manifest[key]}" for key in sorted(manifest))

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
        if feature.is_dirty():
            raise LifecycleError("feature worktree is dirty")
        remote = remote or feature.run(
            "config", "--get", f"branch.{self.base_branch}.remote", check=False
        ).stdout.strip() or "origin"
        refspec = f"{head}:refs/heads/{self.feature_branch}"
        try:
            feature.run("push", remote, refspec)
            remote_sha = feature.run(
                "ls-remote", remote, f"refs/heads/{self.feature_branch}"
            ).stdout.split()[0]
        except (GitError, IndexError) as error:
            raise LifecycleError("publication or remote verification failed") from error
        if remote_sha != head:
            raise LifecycleError("remote SHA differs from approved SHA")
        return {"remote": remote, "branch": self.feature_branch, "pushed_sha": head}
