"""Resolve review bases and targets to immutable commits and detached worktrees."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .git import Git, GitError
from .worktrees import WorktreeManager


class ResolverError(RuntimeError):
    """Review context cannot be resolved without guessing."""


@dataclass(frozen=True)
class Candidate:
    """Selectable local or remote branch."""

    ref: str
    sha: str
    subject: str
    timestamp: int

    @property
    def full_name(self) -> str:
        return self.ref

    @property
    def branch_name(self) -> str:
        return self.ref.split("/", 1)[-1] if "/" in self.ref else self.ref

    @property
    def commit_hash(self) -> str:
        return self.sha


@dataclass(frozen=True)
class Resolution:
    """Review context bound to exact commit IDs."""

    base_ref: str
    base_sha: str
    target_ref: str | None
    target_sha: str | None
    mode: str
    candidates: tuple[Candidate, ...] = ()
    ambiguous: bool = False
    fetch_error: str | None = None
    review_path: Path | None = None
    pr_number: int | None = None
    range_operator: str | None = None

    @property
    def reference_branch(self) -> str:
        return self.base_ref

    @property
    def reference_ref(self) -> str:
        return self.base_ref

    @property
    def reference_commit_hash(self) -> str:
        return self.base_sha

    @property
    def feature_ref(self) -> str | None:
        return self.target_ref

    @property
    def feature_branch(self) -> str | None:
        if self.target_ref is None:
            return None
        return _short_branch(self.target_ref, ())

    @property
    def commit_hash(self) -> str | None:
        return self.target_sha

    @property
    def worktree_path(self) -> Path | None:
        return self.review_path


_PR_URL_PATTERNS = (
    re.compile(
        r"^(?P<base>https?://[^/\s]+/\S+?)/pulls?/(?P<num>\d+)(?:[/?#]\S*)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<base>https?://[^/\s]+/\S+?)(?:/-)?/merge_requests/(?P<num>\d+)"
        r"(?:[/?#]\S*)?$",
        re.IGNORECASE,
    ),
)
_RANGE = re.compile(r"^(.+?)(\.\.\.?)(.+)$")


def parse_pr_target(target: str | None) -> tuple[int, str | None] | None:
    """Parse ``#N`` or a GitHub/Gitea/Forgejo/GitLab PR/MR URL."""
    if not target:
        return None
    value = target.strip()
    match = re.fullmatch(r"#(\d+)", value)
    if match:
        return int(match.group(1)), None
    for pattern in _PR_URL_PATTERNS:
        match = pattern.match(value)
        if match:
            return int(match.group("num")), match.group("base")
    return None


def normalize_git_url(url: str) -> str:
    """Reduce common Git URLs to a lowercase host/path comparison value."""
    value = url.strip().lower()
    if value.startswith("git@"):
        value = value[4:].replace(":", "/", 1)
    else:
        for prefix in ("ssh://git@", "https://", "http://", "ssh://", "git://"):
            if value.startswith(prefix):
                value = value[len(prefix) :]
                break
    value = value.rstrip("/")
    return value[:-4] if value.endswith(".git") else value


def pr_ref_candidates(remote_url: str, pr_number: int) -> tuple[str, str]:
    """Return provider PR head refs in preferred fetch order."""
    pull = f"refs/pull/{pr_number}/head"
    merge_request = f"refs/merge-requests/{pr_number}/head"
    if "gitlab" in normalize_git_url(remote_url):
        return merge_request, pull
    return pull, merge_request


def _short_branch(ref: str, remotes: tuple[str, ...] | list[str]) -> str:
    if ref.startswith("refs/heads/"):
        return ref.removeprefix("refs/heads/")
    if ref.startswith("refs/remotes/"):
        ref = ref.removeprefix("refs/remotes/")
    if ref.startswith("remotes/"):
        ref = ref.removeprefix("remotes/")
    for remote in remotes:
        if ref.startswith(f"{remote}/"):
            return ref[len(remote) + 1 :]
    return ref


class _AmbiguousTarget(Exception):
    def __init__(self, candidates: tuple[Candidate, ...]):
        self.candidates = candidates


class Resolver:
    """Resolve mutable Git names once, then review only their immutable SHAs."""

    def __init__(self, repository: str | Path, cache_root: str | Path):
        self.repository = Path(repository).resolve(strict=True)
        self.git = Git(self.repository)
        self.worktrees = WorktreeManager(self.repository, cache_root)

    def resolve(
        self, target: str | None = None, *, reference: str | None = None
    ) -> Resolution:
        """Resolve branch, commit, range, or PR target and create exact review worktree."""
        fetch_error = self._fetch_all()
        remotes = self._remotes()

        range_match = _RANGE.fullmatch(target.strip()) if target else None
        if range_match:
            if reference is not None:
                raise ResolverError(
                    "range target cannot be combined with an explicit reference"
                )
            left, operator, right = range_match.groups()
            base_ref, base_sha = self._normalize_reference(left, remotes)
            try:
                target_ref, target_sha, _ = self._select_target(right, remotes)
            except _AmbiguousTarget as error:
                return Resolution(
                    base_ref,
                    base_sha,
                    None,
                    None,
                    "range",
                    error.candidates,
                    True,
                    fetch_error,
                    range_operator=operator,
                )
            return self._finalize(
                base_ref,
                base_sha,
                target_ref,
                target_sha,
                "range",
                fetch_error,
                range_operator=operator,
            )

        parsed_pr = parse_pr_target(target)
        if reference is not None:
            base_ref, base_sha = self._normalize_reference(reference, remotes)
        else:
            base_ref, base_sha = self._default_base(target, parsed_pr, remotes)

        if parsed_pr:
            number, repository_url = parsed_pr
            remote = self._pr_remote(repository_url, remotes)
            source_ref, local_ref = self._fetch_pr(remote, number)
            target_sha = self._commit(local_ref)
            return self._finalize(
                base_ref,
                base_sha,
                f"{remote}/{source_ref.removeprefix('refs/')}",
                target_sha,
                "pr",
                fetch_error,
                pr_number=number,
            )

        candidates = self._candidates(base_ref, remotes)
        if target is None:
            return Resolution(
                base_ref,
                base_sha,
                None,
                None,
                "branch",
                candidates,
                True,
                fetch_error,
            )

        try:
            target_ref, target_sha, mode = self._select_target(target, remotes)
        except _AmbiguousTarget as error:
            return Resolution(
                base_ref,
                base_sha,
                None,
                None,
                "branch",
                error.candidates,
                True,
                fetch_error,
            )
        return self._finalize(
            base_ref,
            base_sha,
            target_ref,
            target_sha,
            mode,
            fetch_error,
        )

    def _finalize(
        self,
        base_ref: str,
        base_sha: str,
        target_ref: str,
        target_sha: str,
        mode: str,
        fetch_error: str | None,
        *,
        pr_number: int | None = None,
        range_operator: str | None = None,
    ) -> Resolution:
        if base_sha == target_sha:
            raise ResolverError(
                f"reference and target resolve to the same commit: {base_sha}"
            )
        review_path = self.worktrees.create_review(target_sha)
        return Resolution(
            base_ref,
            base_sha,
            target_ref,
            target_sha,
            mode,
            fetch_error=fetch_error,
            review_path=review_path,
            pr_number=pr_number,
            range_operator=range_operator,
        )

    def _fetch_all(self) -> str | None:
        result = self.git.run("fetch", "--all", "--prune", check=False)
        if result.returncode == 0:
            return None
        detail = result.stderr.strip() or result.stdout.strip()
        return f"git fetch --all --prune failed: {detail}"

    def _remotes(self) -> tuple[str, ...]:
        result = self.git.run("remote")
        remotes = tuple(
            line.strip() for line in result.stdout.splitlines() if line.strip()
        )
        return tuple(sorted(remotes, key=lambda item: (item != "origin", item)))

    def _remote_url(self, remote: str) -> str:
        result = self.git.run("config", "--get", f"remote.{remote}.url", check=False)
        return result.stdout.strip() if result.returncode == 0 else ""

    def _default_base(
        self,
        target: str | None,
        parsed_pr: tuple[int, str | None] | None,
        remotes: tuple[str, ...],
    ) -> tuple[str, str]:
        symbolic = self.git.symbolic_branch()
        current = symbolic.removeprefix("refs/heads/") if symbolic else None
        target_short = None if parsed_pr else _short_branch(target or "", remotes)
        if current and current != target_short:
            current_sha = self._commit(f"refs/heads/{current}")
            target_commit = (
                self.git.run(
                    "rev-parse", "--verify", f"{target}^{{commit}}", check=False
                )
                if target and not parsed_pr
                else None
            )
            if (
                target_commit is None
                or target_commit.returncode
                or target_commit.stdout.strip() != current_sha
            ):
                return current, current_sha
        integration = self._integration_branch(remotes)
        return integration, self._commit(self._revision(integration, remotes))

    def _integration_branch(self, remotes: tuple[str, ...]) -> str:
        for remote in remotes:
            result = self.git.run(
                "symbolic-ref", "-q", f"refs/remotes/{remote}/HEAD", check=False
            )
            if result.returncode == 0:
                ref = result.stdout.strip()
                if ref.startswith("refs/remotes/"):
                    return ref.removeprefix("refs/remotes/")
        for remote in remotes:
            for name in ("main", "master", "develop"):
                if self._exists(f"refs/remotes/{remote}/{name}"):
                    return f"{remote}/{name}"
        for name in ("main", "master", "develop"):
            if self._exists(f"refs/heads/{name}"):
                return name
        symbolic = self.git.symbolic_branch()
        if symbolic:
            return symbolic.removeprefix("refs/heads/")
        return "HEAD"

    def _normalize_reference(
        self, reference: str, remotes: tuple[str, ...]
    ) -> tuple[str, str]:
        value = reference.strip()
        if not value:
            raise ResolverError("reference must not be empty")
        if value.startswith("refs/heads/"):
            display = value.removeprefix("refs/heads/")
            return display, self._commit(value)
        if value.startswith("refs/remotes/"):
            display = value.removeprefix("refs/remotes/")
            return display, self._commit(value)
        if value.startswith("remotes/"):
            display = value.removeprefix("remotes/")
            return display, self._commit(f"refs/remotes/{display}")
        for remote in remotes:
            if value.startswith(f"{remote}/"):
                return value, self._commit(f"refs/remotes/{value}")

        remote_refs = self._remote_refs(value)
        if len(remote_refs) > 1:
            refs = ", ".join(remote_refs)
            raise ResolverError(f"reference '{value}' is ambiguous: {refs}")
        if remote_refs:
            return remote_refs[0], self._commit(f"refs/remotes/{remote_refs[0]}")
        if self._exists(f"refs/heads/{value}"):
            return value, self._commit(f"refs/heads/{value}")
        return value, self._commit(value)

    def _select_target(
        self, target: str, remotes: tuple[str, ...]
    ) -> tuple[str, str, str]:
        value = target.strip()
        if not value:
            raise ResolverError("target must not be empty")
        if value.startswith("refs/heads/"):
            display = value.removeprefix("refs/heads/")
            return display, self._commit(value), "branch"
        if value.startswith("refs/remotes/"):
            display = value.removeprefix("refs/remotes/")
            return display, self._commit(value), "branch"
        if value.startswith("remotes/"):
            display = value.removeprefix("remotes/")
            return display, self._commit(f"refs/remotes/{display}"), "branch"
        for remote in remotes:
            if value.startswith(f"{remote}/"):
                return value, self._commit(f"refs/remotes/{value}"), "branch"
        if self._exists(f"refs/heads/{value}"):
            return value, self._commit(f"refs/heads/{value}"), "branch"

        remote_refs = self._remote_refs(value)
        if len(remote_refs) > 1:
            candidates = tuple(
                self._candidate(ref, f"refs/remotes/{ref}") for ref in remote_refs
            )
            raise _AmbiguousTarget(candidates)
        if remote_refs:
            ref = remote_refs[0]
            return ref, self._commit(f"refs/remotes/{ref}"), "branch"
        return value, self._commit(value), "commit"

    def _remote_refs(self, short_name: str) -> tuple[str, ...]:
        result = self.git.run(
            "for-each-ref", "--format=%(refname)", f"refs/remotes/*/{short_name}"
        )
        refs = []
        for line in result.stdout.splitlines():
            ref = line.strip()
            if ref and not ref.endswith("/HEAD"):
                refs.append(ref.removeprefix("refs/remotes/"))
        return tuple(sorted(refs))

    def _revision(self, display_ref: str, remotes: tuple[str, ...]) -> str:
        for remote in remotes:
            if display_ref.startswith(f"{remote}/"):
                return f"refs/remotes/{display_ref}"
        return (
            f"refs/heads/{display_ref}"
            if self._exists(f"refs/heads/{display_ref}")
            else display_ref
        )

    def _commit(self, revision: str) -> str:
        try:
            return self.git.resolve_commit(revision)
        except GitError as error:
            raise ResolverError(
                f"Git reference not found or not a commit: {revision}"
            ) from error

    def _exists(self, ref: str) -> bool:
        return (
            self.git.run("show-ref", "--verify", "--quiet", ref, check=False).returncode
            == 0
        )

    def _candidate(self, display_ref: str, revision: str) -> Candidate:
        sha = self._commit(revision)
        result = self.git.run("show", "-s", "--format=%ct|%s", sha)
        timestamp_text, _, subject = result.stdout.strip().partition("|")
        return Candidate(display_ref, sha, subject, int(timestamp_text or 0))

    def _candidates(
        self, base_ref: str, remotes: tuple[str, ...]
    ) -> tuple[Candidate, ...]:
        result = self.git.run(
            "for-each-ref",
            "--format=%(refname)|%(objectname)|%(committerdate:unix)|%(subject)",
            "refs/heads/",
            "refs/remotes/",
        )
        base_short = _short_branch(base_ref, remotes)
        candidates = []
        for line in result.stdout.splitlines():
            refname, sha, timestamp, subject = line.split("|", 3)
            if refname.endswith("/HEAD"):
                continue
            if refname.startswith("refs/heads/"):
                display = refname.removeprefix("refs/heads/")
            else:
                display = refname.removeprefix("refs/remotes/")
            if _short_branch(display, remotes) == base_short:
                continue
            candidates.append(Candidate(display, sha, subject, int(timestamp or 0)))
        return tuple(sorted(candidates, key=lambda item: (-item.timestamp, item.ref)))

    def _pr_remote(self, repository_url: str | None, remotes: tuple[str, ...]) -> str:
        if not remotes:
            raise ResolverError("no Git remote is configured for PR resolution")
        if repository_url is None:
            return remotes[0]
        wanted = normalize_git_url(repository_url)
        for remote in remotes:
            if normalize_git_url(self._remote_url(remote)) == wanted:
                return remote
        raise ResolverError(f"no Git remote matches PR repository: {repository_url}")

    def _fetch_pr(self, remote: str, number: int) -> tuple[str, str]:
        local_ref = f"refs/principled-dev/reviews/{remote}/pr/{number}"
        errors = []
        for source_ref in pr_ref_candidates(self._remote_url(remote), number):
            result = self.git.run(
                "fetch", remote, f"+{source_ref}:{local_ref}", check=False
            )
            if result.returncode == 0:
                return source_ref, local_ref
            errors.append(result.stderr.strip() or result.stdout.strip())
        raise ResolverError(
            f"Could not fetch PR/MR #{number} from remote '{remote}': "
            + " | ".join(errors)
        )


def resolve(
    repository: str | Path,
    cache_root: str | Path,
    target: str | None = None,
    *,
    reference: str | None = None,
) -> Resolution:
    """Convenience wrapper around :class:`Resolver`."""
    return Resolver(repository, cache_root).resolve(target, reference=reference)
