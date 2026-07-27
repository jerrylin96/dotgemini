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
        self.remote_sha = None
        self.review_digest = None
        self._manifest = None
        metadata = self.state.get_metadata(self.repository_id, self.feature_branch)
        if metadata:
            self.base_branch = metadata.get("base_branch", self.base_branch)
            self.base_sha = metadata.get("base_sha")
            self.remote_sha = metadata.get("remote_sha")
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
        if not self.state.is_approved(
            self.repository_id, self.feature_branch, "build", self._manifest_bytes()
        ) or not self.manifest_is_fresh():
            raise LifecycleError("approved fresh manifest is required before publication")
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
        self.remote_sha = remote_sha
        self.review_digest = review.digest()
        self.state.set_metadata(
            self.repository_id,
            self.feature_branch,
            remote_sha=remote_sha,
            review_digest=self.review_digest,
        )
        return {
            "remote": remote,
            "branch": self.feature_branch,
            "pushed_sha": head,
            "review_digest": self.review_digest,
        }
