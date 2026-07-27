import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from principled_dev.git import Git
from principled_dev.resolver import (
    Resolver,
    ResolverError,
    parse_pr_target,
    pr_ref_candidates,
)


def run(*args, cwd=None, check=True):
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)


def git(repo, *args, check=True):
    return run("git", "-C", str(repo), *args, check=check)


def configure(repo):
    git(repo, "config", "user.name", "principled-dev test")
    git(repo, "config", "user.email", "test@example.invalid")


def commit(repo, name, text):
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-qm", text.strip())
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def make_clone(tmp_path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    local = tmp_path / "local"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    seed.mkdir()
    git(seed, "init", "-q", "-b", "main")
    configure(seed)
    main = commit(seed, "tracked.txt", "main one\n")
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "-q", "-u", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    run("git", "clone", "-q", str(remote), str(local), cwd=tmp_path)
    configure(local)
    return remote, seed, local, main


def make_local_feature(local, name="topic"):
    git(local, "switch", "-qc", name)
    return commit(local, f"{name}.txt", f"{name}\n")


def resolver(local, tmp_path):
    return Resolver(local, tmp_path / "cache")


def test_pr_target_parsing_and_host_ref_order():
    assert parse_pr_target("#42") == (42, None)
    assert parse_pr_target("https://github.com/o/r/pull/7/files") == (
        7,
        "https://github.com/o/r",
    )
    assert parse_pr_target("https://gitea.example/o/r/pulls/3") == (
        3,
        "https://gitea.example/o/r",
    )
    assert parse_pr_target("https://forgejo.example/o/r/pulls/4") == (
        4,
        "https://forgejo.example/o/r",
    )
    assert parse_pr_target("https://gitlab.example/g/sub/r/-/merge_requests/13") == (
        13,
        "https://gitlab.example/g/sub/r",
    )
    assert parse_pr_target("42") is None
    assert parse_pr_target("feature/42") is None

    assert pr_ref_candidates("https://github.com/o/r.git", 5)[0] == "refs/pull/5/head"
    assert (
        pr_ref_candidates("https://gitea.example/o/r.git", 5)[0] == "refs/pull/5/head"
    )
    assert (
        pr_ref_candidates("https://forgejo.example/o/r.git", 5)[0] == "refs/pull/5/head"
    )
    assert pr_ref_candidates("https://gitlab.example/o/r.git", 5)[0] == (
        "refs/merge-requests/5/head"
    )


def test_current_target_uses_fetched_remote_default_and_exact_review_worktree(tmp_path):
    remote, seed, local, first_main = make_clone(tmp_path)
    target_sha = make_local_feature(local)

    git(seed, "switch", "main")
    advanced_main = commit(seed, "tracked.txt", "main two\n")
    git(seed, "push", "-q", "origin", "main")

    result = resolver(local, tmp_path).resolve("topic")

    assert result.base_ref == "origin/main"
    assert result.base_sha == advanced_main != first_main
    assert result.target_ref == "topic"
    assert result.target_sha == target_sha
    assert result.mode == "branch"
    assert result.fetch_error is None
    assert result.review_path is not None
    assert Git(result.review_path).head() == target_sha
    assert Git(result.review_path).symbolic_branch() is None


def test_explicit_reference_normalizes_unique_remote_and_rejects_ambiguity(tmp_path):
    remote, seed, local, _ = make_clone(tmp_path)
    git(seed, "switch", "-c", "release")
    release_sha = commit(seed, "release.txt", "release\n")
    git(seed, "push", "-q", "origin", "release")
    target_sha = make_local_feature(local)

    result = resolver(local, tmp_path).resolve("topic", reference="release")
    assert result.base_ref == "origin/release"
    assert result.base_sha == release_sha
    assert result.target_sha == target_sha

    upstream = tmp_path / "upstream.git"
    git(tmp_path, "clone", "-q", "--bare", str(remote), str(upstream))
    git(local, "remote", "add", "upstream", str(upstream))
    git(local, "fetch", "-q", "upstream")

    with pytest.raises(
        ResolverError, match="ambiguous.*origin/release.*upstream/release"
    ):
        resolver(local, tmp_path).resolve("topic", reference="release")

    qualified = resolver(local, tmp_path).resolve("topic", reference="origin/release")
    assert qualified.base_ref == "origin/release"
    assert qualified.base_sha == release_sha


def test_candidates_request_selection_and_preserve_same_named_refs(tmp_path):
    remote, seed, local, _ = make_clone(tmp_path)
    git(seed, "switch", "-c", "remote-only")
    remote_sha = commit(seed, "remote.txt", "remote\n")
    git(seed, "push", "-q", "origin", "remote-only")
    local_sha = make_local_feature(local, "local-only")

    result = resolver(local, tmp_path).resolve(reference="main")

    assert result.ambiguous
    assert result.target_sha is None
    assert result.review_path is None
    candidates = {candidate.ref: candidate.sha for candidate in result.candidates}
    assert candidates["origin/remote-only"] == remote_sha
    assert candidates["local-only"] == local_sha
    assert "main" not in candidates
    assert "origin/main" not in candidates


def test_exact_local_remote_qualified_and_unqualified_targets(tmp_path):
    remote, seed, local, _ = make_clone(tmp_path)
    git(seed, "switch", "-c", "topic")
    remote_sha = commit(seed, "topic.txt", "remote topic\n")
    git(seed, "push", "-q", "origin", "topic")
    git(local, "fetch", "-q", "origin")
    git(local, "switch", "-c", "topic", "origin/topic")
    local_sha = commit(local, "topic.txt", "local topic\n")
    git(local, "switch", "main")
    subject = resolver(local, tmp_path)

    assert subject.resolve("origin/topic").target_sha == remote_sha
    assert subject.resolve("refs/remotes/origin/topic").target_sha == remote_sha
    assert subject.resolve("refs/heads/topic").target_sha == local_sha
    assert subject.resolve("topic").target_sha == local_sha


def test_commit_and_range_modes_normalize_to_immutable_shas(tmp_path):
    _, _, local, base_sha = make_clone(tmp_path)
    target_sha = make_local_feature(local)
    subject = resolver(local, tmp_path)

    current_commit = subject.resolve(target_sha[:12])
    assert current_commit.mode == "commit"
    assert current_commit.base_ref == "origin/main"
    assert current_commit.base_sha == base_sha
    assert current_commit.target_sha == target_sha

    commit_result = subject.resolve(target_sha[:12], reference=base_sha[:12])
    assert commit_result.mode == "commit"
    assert commit_result.base_sha == base_sha
    assert commit_result.target_sha == target_sha

    range_result = subject.resolve(f"{base_sha[:12]}...{target_sha[:12]}")
    assert range_result.mode == "range"
    assert range_result.base_ref == base_sha[:12]
    assert range_result.base_sha == base_sha
    assert range_result.target_ref == target_sha[:12]
    assert range_result.target_sha == target_sha

    with pytest.raises(FrozenInstanceError):
        range_result.target_sha = base_sha


def configure_web_remote(local, remote, web_url):
    git(local, "remote", "set-url", "origin", web_url)
    git(local, "config", f"url.{remote}.insteadOf", web_url)


@pytest.mark.parametrize(
    ("web_url", "source_ref"),
    [
        ("https://github.example/o/r", "refs/pull/8/head"),
        ("https://gitea.example/o/r", "refs/pull/8/head"),
        ("https://forgejo.example/o/r", "refs/pull/8/head"),
        ("https://gitlab.example/g/r", "refs/merge-requests/8/head"),
    ],
)
def test_pr_urls_fetch_provider_head_without_network(tmp_path, web_url, source_ref):
    remote, seed, local, _ = make_clone(tmp_path)
    target_sha = make_local_feature(seed, "pr-source")
    git(seed, "push", "-q", "origin", f"{target_sha}:{source_ref}")
    git(seed, "switch", "main")
    git(seed, "branch", "-D", "pr-source")
    configure_web_remote(local, remote, web_url)

    if "gitlab" in web_url:
        target = f"{web_url}/-/merge_requests/8"
    else:
        target = f"{web_url}/pull/8"
    result = resolver(local, tmp_path).resolve(target)

    assert result.pr_number == 8
    assert result.target_ref == f"origin/{source_ref.removeprefix('refs/')}"
    assert result.target_sha == target_sha
    assert Git(result.review_path).head() == target_sha


def test_hash_pr_uses_origin_and_missing_pr_fetch_is_fatal(tmp_path):
    remote, seed, local, _ = make_clone(tmp_path)
    target_sha = make_local_feature(seed, "pr-source")
    git(seed, "push", "-q", "origin", f"{target_sha}:refs/pull/2/head")

    result = resolver(local, tmp_path).resolve("#2")
    assert result.pr_number == 2
    assert result.target_sha == target_sha

    with pytest.raises(ResolverError, match="Could not fetch PR/MR #99"):
        resolver(local, tmp_path).resolve("#99")


def test_fetch_failure_is_surfaced_while_stale_refs_remain_resolvable(tmp_path):
    remote, seed, local, base_sha = make_clone(tmp_path)
    git(seed, "switch", "-c", "topic")
    target_sha = commit(seed, "topic.txt", "topic\n")
    git(seed, "push", "-q", "origin", "topic")
    git(local, "fetch", "-q", "origin")
    run("rm", "-rf", str(remote))

    result = resolver(local, tmp_path).resolve("origin/topic", reference="origin/main")

    assert result.base_sha == base_sha
    assert result.target_sha == target_sha
    assert result.fetch_error is not None
    assert "fetch" in result.fetch_error
