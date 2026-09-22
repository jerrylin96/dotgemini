"""Tests for skills/git-signoff/attest.py — the deterministic GSA producer.

Everything runs against scratch repositories (helpers.py) with attest.py loaded
by path, the way the vendored folder is used. The CLI is exercised in-process
through attest.main(argv) so exit codes and stdout/stderr are asserted exactly.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest
from _attest_loader import SKILL_DIR, attest, verify_signoff
from helpers import commit_file, git, init_repo

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(autouse=True)
def _fast_marker_retry(monkeypatch):
    monkeypatch.setattr(attest, "MARKER_RETRY_DELAY", 0)


def _head(repo):
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def _tree(repo):
    return git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()


def _prepared(repo, reference="main", **kwargs):
    """Run prepare in-process so the preparation record `commit` requires exists."""
    return attest.prepare(str(repo), reference, **kwargs)


def _record(repo):
    return repo / ".git" / "git-signoff" / "prepared.json"


def _transcript(tmp_path, repo, extra=b"", name="transcript.jsonl", with_marker=True, sha=None):
    """Transcript file whose tail carries the approval marker for HEAD (or `sha`)."""
    body = b'{"role":"user","content":"hi"}\n{"role":"assistant","model":"model-from-transcript","content":"ok"}\n'
    if with_marker:
        body += f"GSA-APPROVAL {sha or _head(repo)} 2026-09-09T00:00:00Z\n".encode()
    body += extra
    f = tmp_path / name
    f.write_bytes(body)
    return f


def run(monkeypatch, capsys, cwd, *argv, env=None):
    """Run the CLI in-process from `cwd`; returns (exit_code, stdout, stderr)."""
    monkeypatch.chdir(cwd)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    try:
        code = attest.main(list(argv))
    except SystemExit as exc:  # argparse errors
        code = exc.code
    out, err = capsys.readouterr()
    return code, out, err


def run_json(monkeypatch, capsys, cwd, *argv, env=None):
    code, out, err = run(monkeypatch, capsys, cwd, *argv, "--json", env=env)
    return code, json.loads(out), err


# --- prepare ------------------------------------------------------------------


def test_prepare_resolves_shas_diff_profile_and_marker(scratch_repo, monkeypatch, capsys):
    code, data, err = run_json(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 0, err
    assert data["ok"] is True and data["command"] == "prepare"
    assert data["reviewed_commit_sha"] == _head(scratch_repo)
    assert data["base_sha"] == git(scratch_repo, "rev-parse", "main").stdout.strip()
    assert data["tree_sha"] == _tree(scratch_repo)
    assert data["reference"] == "main"
    assert data["name_status"] == ["A\tfeat.txt"]
    assert "1 file changed" in data["shortstat"]
    assert data["diff_command"] == f"git diff {data['base_sha']}..{data['reviewed_commit_sha']}"
    assert data["profile"] == {
        "source": "embedded-default", "path": None, "id": "software-general", "digest": None, "fallback_reason": None,
    }
    assert data["science_signals"] == []
    assert data["transcript"]["harness_id"] == "unknown"
    assert data["transcript"]["available"] is False
    assert data["marker"] == f"GSA-APPROVAL {data['reviewed_commit_sha']} " + data["marker"].split()[-1]
    assert attest.MARKER_RE.search(data["marker"].encode())
    assert data["hints"]["changed_files"] == 1
    assert data["hints"]["executable_lines_changed"] == 0  # feat.txt is documentation
    assert any("--ack-no-transcript" in w for w in data["warnings"])


def test_prepare_human_output_ends_with_marker_line(scratch_repo, monkeypatch, capsys):
    code, out, err = run(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == f"reviewed commit: {_head(scratch_repo)}"
    assert lines[-1].startswith(f"GSA-APPROVAL {_head(scratch_repo)} ")
    assert "approval marker" in lines[-2]
    assert "warning:" in err and "warning:" not in out  # diagnostics never pollute stdout


def test_marker_command_prints_only_the_marker(scratch_repo, monkeypatch, capsys):
    _prepared(scratch_repo)
    code, out, _ = run(monkeypatch, capsys, scratch_repo, "marker", "--reference", "main")
    assert code == 0
    assert out.strip().split("\n") == [out.strip()]
    assert out.startswith(f"GSA-APPROVAL {_head(scratch_repo)} ")


def test_prepare_works_from_a_subdirectory(scratch_repo, monkeypatch, capsys):
    sub = scratch_repo / "sub" / "dir"
    sub.mkdir(parents=True)
    commit_file(scratch_repo, "sub/dir/x.py", "x = 1\n", "sub file")
    code, data, _ = run_json(monkeypatch, capsys, sub, "prepare", "--reference", "main")
    assert code == 0
    assert data["reviewed_commit_sha"] == _head(scratch_repo)
    assert data["hints"]["executable_lines_changed"] == 1


def test_prepare_reference_defaults_to_upstream(tmp_path, monkeypatch, capsys):
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "-q", "--bare", "-b", "main")
    work = init_repo(tmp_path / "work")
    commit_file(work, "base.txt", "base\n", "base commit")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "-u", "origin", "main")
    git(work, "checkout", "-q", "-b", "feature")
    commit_file(work, "feat.txt", "feature\n", "feature commit")
    git(work, "branch", "-q", "--set-upstream-to=origin/main")
    code, data, err = run_json(monkeypatch, capsys, work, "prepare")
    assert code == 0
    assert data["reference"] == "origin/main"
    assert data["base_sha"] == git(work, "rev-parse", "origin/main").stdout.strip()
    assert not [w for w in data["warnings"] if "assuming base branch" in w]


def test_prepare_reference_falls_back_to_main_with_warning(scratch_repo, monkeypatch, capsys):
    code, data, err = run_json(monkeypatch, capsys, scratch_repo, "prepare")
    assert code == 0
    assert data["reference"] == "main"
    assert any("assuming base branch 'main'" in w for w in data["warnings"])
    assert "assuming base branch 'main'" in err


def test_prepare_reference_falls_back_to_master(tmp_path, monkeypatch, capsys):
    path = init_repo(tmp_path / "repo_master", branch="master")
    commit_file(path, "base.txt", "base\n", "base commit")
    git(path, "checkout", "-q", "-b", "feature")
    commit_file(path, "feat.txt", "feat\n", "feat commit")
    code, data, _ = run_json(monkeypatch, capsys, path, "prepare")
    assert code == 0 and data["reference"] == "master"


def test_prepare_ignores_an_upstream_that_is_the_branch_itself(tmp_path, monkeypatch, capsys):
    """`git push -u origin feature` makes origin/feature the upstream; it contains
    HEAD, so it is an empty range, not a base. prepare must fall back to main."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "-q", "--bare", "-b", "main")
    work = init_repo(tmp_path / "work")
    commit_file(work, "base.txt", "base\n", "base commit")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "-u", "origin", "main")
    git(work, "checkout", "-q", "-b", "feature")
    commit_file(work, "feat.py", "x = 1\n", "feature commit")
    git(work, "push", "-q", "-u", "origin", "feature")
    assert git(work, "rev-parse", "--abbrev-ref", "HEAD@{upstream}").stdout.strip() == "origin/feature"
    code, data, err = run_json(monkeypatch, capsys, work, "prepare")
    assert code == 0, err
    assert data["reference"] == "main"
    assert data["base_sha"] == git(work, "rev-parse", "main").stdout.strip()
    assert data["name_status"] == ["A\tfeat.py"]
    assert any("origin/feature" in w and "already contains HEAD" in w for w in data["warnings"])


def test_prepare_falls_back_to_origin_main_when_no_local_main(tmp_path, monkeypatch, capsys):
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "-q", "--bare", "-b", "main")
    seed = init_repo(tmp_path / "seed")
    commit_file(seed, "base.txt", "base\n", "base commit")
    git(seed, "remote", "add", "origin", str(origin))
    git(seed, "push", "-q", "origin", "main")
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), "work")
    git(work, "config", "user.email", "t@example.com")
    git(work, "config", "user.name", "T")
    git(work, "checkout", "-q", "-b", "feature", "origin/main")
    git(work, "branch", "-q", "-D", "main")
    commit_file(work, "feat.py", "x = 1\n", "feature commit")
    git(work, "push", "-q", "-u", "origin", "feature")
    code, data, err = run_json(monkeypatch, capsys, work, "prepare")
    assert code == 0, err
    assert data["reference"] == "origin/main"


def test_prepare_warns_when_explicit_reference_contains_head(scratch_repo, monkeypatch, capsys):
    """An explicit --reference is honored even when it already contains HEAD
    (post-hoc attestation of a merged commit), but the empty range is announced."""
    code, data, err = run_json(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "HEAD")
    assert code == 0
    assert data["base_sha"] == data["reviewed_commit_sha"] and data["name_status"] == []
    assert any("range to review is empty" in w for w in data["warnings"])
    assert "range to review is empty" in err


def test_prepare_never_diffs_main_against_itself(tmp_path, monkeypatch, capsys):
    path = init_repo(tmp_path / "repo_main", branch="main")
    commit_file(path, "base.txt", "base\n", "base commit")
    git(path, "branch", "master")
    code, data, err = run_json(monkeypatch, capsys, path, "prepare")
    assert code == 2
    assert data["ok"] is False and data["exit_code"] == 2
    assert "pass --reference" in err


def test_prepare_rejects_unresolvable_reference(scratch_repo, monkeypatch, capsys):
    code, _, err = run(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "no-such-branch")
    assert code == 2 and "does not resolve" in err


def test_prepare_refuses_unstaged_changes(scratch_repo, monkeypatch, capsys):
    (scratch_repo / "feat.txt").write_text("dirty\n")
    code, _, err = run(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 3 and "Unstaged" in err


def test_prepare_refuses_staged_changes(scratch_repo, monkeypatch, capsys):
    (scratch_repo / "staged.txt").write_text("s\n")
    git(scratch_repo, "add", "staged.txt")
    code, _, err = run(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 3 and "Staged" in err


def test_prepare_refuses_when_head_is_already_an_attestation(scratch_repo, tmp_path, monkeypatch, capsys):
    """After a successful commit (or a failed rollback that left the rejected
    attestation at HEAD), re-running prepare must stop rather than set up an
    attestation of the attestation, which the verifier would pass."""
    reviewed = _head(scratch_repo)
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    attestation = _head(scratch_repo)
    code, _, err = run(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 3
    assert "already an attestation commit" in err and attestation[:7] in err and reviewed[:7] in err
    assert "git reset --soft HEAD~1" in err
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 3 and _head(scratch_repo) == attestation  # nothing stacked on top


def test_prepare_refuses_unborn_head(tmp_path, monkeypatch, capsys):
    path = init_repo(tmp_path / "unborn")
    code, _, err = run(monkeypatch, capsys, path, "prepare")
    assert code == 6 and "unborn" in err


def test_prepare_outside_git_repo_is_git_failure(tmp_path, monkeypatch, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    code, _, err = run(monkeypatch, capsys, plain, "prepare")
    assert code == 6 and "not inside a git repository" in err


def test_prepare_unreadable_profile_override_is_exit_5(scratch_repo, tmp_path, monkeypatch, capsys):
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main",
        env={"GIT_SIGNOFF_PROFILE_FILE": str(tmp_path / "missing.md")},
    )
    assert code == 5 and "GIT_SIGNOFF_PROFILE_FILE" in err


def test_prepare_reports_repo_local_profile_and_malformed_fallback(scratch_repo, monkeypatch, capsys):
    d = scratch_repo / ".git-signoff"
    d.mkdir()
    valid = (
        "<!-- INTERVIEW-PROFILE:BEGIN -->\n### Interview Profile: lab\nProfile-ID: lab-x\n- emphasis\n"
        "<!-- INTERVIEW-PROFILE:END -->\n"
    )
    (d / "profile.md").write_text(valid, encoding="utf-8")
    git(scratch_repo, "add", ".")
    git(scratch_repo, "commit", "-q", "-m", "profile")
    code, data, _ = run_json(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 0
    assert data["profile"]["source"] == "repo-local" and data["profile"]["id"] == "lab-x"
    assert len(data["profile"]["digest"]) == 12

    (d / "profile.md").write_text(valid.replace("Profile-ID: lab-x\n", ""), encoding="utf-8")
    git(scratch_repo, "commit", "-q", "-am", "break profile")
    code, data, err = run_json(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 0  # malformed repo-local profile is announced, not fatal
    assert data["profile"]["source"] == "embedded-default" and data["profile"]["digest"] is None
    assert "malformed profile" in data["profile"]["fallback_reason"]
    assert "malformed profile" in err


def test_prepare_science_signals_and_tier2_hints(scratch_repo, monkeypatch, capsys):
    (scratch_repo / "ciwv.py").write_text("import numpy as np\nG0 = 9.80665\nrng = np.random.default_rng(seed=7)\n")
    (scratch_repo / "auth").mkdir()
    (scratch_repo / "auth" / "login.py").write_text("def login(): pass\n")
    (scratch_repo / "migrations").mkdir()
    (scratch_repo / "migrations" / "001.sql").write_text("ALTER TABLE users ADD COLUMN x int;\n")
    (scratch_repo / "api.proto").write_text("syntax = 'proto3';\n")
    (scratch_repo / "tests").mkdir()
    (scratch_repo / "tests" / "test_x.py").write_text("def test(): pass\n" * 300)
    (scratch_repo / "docs.md").write_text("# doc\n" * 500)
    git(scratch_repo, "add", ".")
    git(scratch_repo, "commit", "-q", "-m", "science + auth")
    code, data, _ = run_json(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 0
    assert set(data["science_signals"]) >= {"scientific-imports", "rng-seeding", "units-or-constants"}
    triggers = data["hints"]["tier2_triggers"]
    assert triggers["security-auth"] == ["auth/login.py"]
    assert set(triggers["schemas-migrations"]) == {"migrations/001.sql", "<diff content>"}
    assert triggers["public-api-contracts"] == ["api.proto"]
    assert triggers["scientific-computation"] == data["science_signals"]
    assert "executable-blast-radius" not in triggers  # tests and docs are excluded from the count
    assert data["hints"]["changed_files"] == 7
    assert data["hints"]["executable_files"] == 4
    assert data["hints"]["executable_lines_changed"] == 3 + 1 + 1 + 1


def test_intensity_hints_blast_radius_and_renames():
    numstat = "\n".join(f"50\t0\tsrc/mod{i}.py" for i in range(6)) + "\n3\t2\tsrc/{old => new}/thing.py\n-\t-\timg.png\n"
    hints = attest.intensity_hints(numstat, "", [])
    assert hints["changed_files"] == 8
    assert hints["executable_files"] == 8
    assert hints["executable_lines_changed"] == 305
    assert "executable-blast-radius" in hints["tier2_triggers"]
    docs_only = attest.intensity_hints("500\t0\tREADME.md\n10\t0\tauth/README.md\n", "", [])
    assert docs_only["executable_lines_changed"] == 0
    assert docs_only["tier2_triggers"] == {}  # path tokens do not trigger on docs
    assert docs_only["components"] == [] and docs_only["skeptical_min_probes"] == 8


def test_intensity_hints_components_scale_the_skeptical_floor():
    """A bundled range is interviewed as the sum of its changes: the floor is
    max(8, 4 + 2 * components), a component being a directory with executable
    changes (root files count as their own; docs, tests, lockfiles do not)."""
    numstat = (
        "1\t1\tinit.py\n"
        "40\t2\tskills/git-signoff/attest.py\n"
        "5\t5\tskills/git-signoff/verify_signoff.py\n"
        "9\t0\tscripts/recover_notes.py\n"
        "3\t3\tverify/action.yml\n"
        "2\t2\t.github/workflows/tag.yml\n"
        "100\t0\tscripts/tests/test_attest.py\n"
        "200\t0\tdocs/attest-any-target.md\n"
        "0\t293\tLICENSE-SPEC\n"          # a license file, whatever its suffix, is not a component
        "4\t1\tCITATION.cff\n"
        "3\t3\tsite/index.html\n"
    )
    hints = attest.intensity_hints(numstat, "", [])
    assert hints["components"] == [".github/workflows", "init.py", "scripts", "skills/git-signoff", "verify"]
    assert hints["skeptical_min_probes"] == 4 + 2 * 5
    assert attest.skeptical_min_probes(0) == 8 and attest.skeptical_min_probes(2) == 8
    assert attest.skeptical_min_probes(3) == 10


# --- commit: happy path --------------------------------------------------------


def test_commit_happy_path_with_marker(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    reviewed, tree = _head(scratch_repo), _tree(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    data_bytes = t.read_bytes()
    code, data, err = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--tradeoff", "t1", "--tradeoff", "t2", "--risk", "r1", "--summary", "Reviewed the widget.",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert data["ok"] is True and data["command"] == "commit"
    assert data["status"] == "VERIFIED_BY_HUMAN"
    assert data["transcript_digest"] == f"sha256:{hashlib.sha256(data_bytes).hexdigest()}"
    assert data["transcript_bytes"] == str(len(data_bytes))
    assert data["marker_found"] is True
    assert data["transcript_path"] == str(t)
    assert data["attestation_sha"] == _head(scratch_repo)
    assert data["noted_shas"] == [reviewed, tree]
    assert data["notes_pushed"] is False and data["notes_push_reason"] == "skipped (--no-push)"
    assert data["signed"] is False
    assert data["verifier"][0].startswith("PASS:")

    # empty attestation commit parented on the reviewed commit with the same tree
    assert git(scratch_repo, "rev-parse", "HEAD~1").stdout.strip() == reviewed
    assert _tree(scratch_repo) == tree
    message = git(scratch_repo, "log", "-1", "--format=%B").stdout
    assert message.rstrip("\n") == data["message"]
    trailers = attest.parse_trailers(message)
    assert trailers["Signoff-Tradeoff"] == ["t1", "t2"]
    assert trailers["Signoff-Risk"] == ["r1"]
    assert trailers["Signoff-Harness-ID"] == ["generic-file"]
    assert trailers["Signoff-Conversation-ID"] == ["unavailable"]
    assert trailers["Signoff-Agent"] == ["harness=generic-file/N/A model=model-from-transcript reasoning=N/A interview=standard/software-general"]
    assert message.splitlines()[2] == "Reviewed the widget."
    # dual persistence
    for sha in (reviewed, tree):
        note = git(scratch_repo, "notes", "--ref=signoff", "show", sha).stdout
        assert note.rstrip("\n") == data["message"]
    # the independent verifier agrees, in head mode on the attestation tip
    ok, lines = verify_signoff.check_head(str(scratch_repo), "HEAD")
    assert ok, lines


def test_commit_human_output(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, out, _ = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "cursory",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0
    assert out.startswith(f"attestation commit: {_head(scratch_repo)}\n")
    assert "status: VERIFIED_BY_HUMAN\n" in out
    assert "approval marker: found\n" in out
    assert "notes pushed: no (skipped (--no-push))" in out
    assert "verifier: PASS:" in out


def test_commit_none_rules_for_empty_tradeoffs_and_risks(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, data, _ = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0
    trailers = attest.parse_trailers(data["message"])
    assert trailers["Signoff-Tradeoff"] == ["none"] and trailers["Signoff-Risk"] == ["none"]


def test_commit_provenance_from_claude_code_env(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, data, _ = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "skeptical",
        "--reference", "main", "--no-push",
        env={
            "GIT_SIGNOFF_TRANSCRIPT_FILE": str(t),
            "CLAUDE_CODE_SESSION_ID": "sess-1",
            "CLAUDE_CODE_VERSION": "2.1.0",
            "CLAUDE_EFFORT": "high",
            "ANTHROPIC_MODEL": "claude-x-1",
        },
    )
    assert code == 0
    trailers = attest.parse_trailers(data["message"])
    # the override file wins for bytes; the conversation id comes from the harness id
    assert trailers["Signoff-Harness-ID"] == ["generic-file"]
    assert trailers["Signoff-Conversation-ID"] == ["sess-1"]
    assert trailers["Signoff-Agent"] == ["harness=generic-file/2.1.0 model=claude-x-1 reasoning=high interview=skeptical/software-general"]


def test_commit_version_and_reasoning_are_scoped_to_claude_code(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, data, _ = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push",
        env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t), "CLAUDE_CODE_VERSION": "2.1.0", "CLAUDE_EFFORT": "high"},
    )
    assert code == 0
    assert "harness=generic-file/N/A model=model-from-transcript reasoning=N/A" in data["message"]


def test_commit_model_self_report_is_last_resort(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    t = tmp_path / "t.jsonl"
    t.write_bytes(b"no model field here\n" + f"GSA-APPROVAL {_head(scratch_repo)} 2026-09-09T00:00:00Z\n".encode())
    code, data, _ = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", "--model", "self-reported-model", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0 and "model=self-reported-model" in data["message"]
    git(scratch_repo, "reset", "-q", "--hard", "HEAD~1")
    _prepared(scratch_repo)
    t2 = _transcript(tmp_path, scratch_repo)  # transcript carries a model field: it beats the self-report
    code, data, _ = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", "--model", "self-reported-model", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t2)},
    )
    assert code == 0 and "model=model-from-transcript" in data["message"]


def test_commit_repo_local_profile_digest_in_agent_token(scratch_repo, tmp_path, monkeypatch, capsys):
    d = scratch_repo / ".git-signoff"
    d.mkdir()
    (d / "profile.md").write_text(
        "<!-- INTERVIEW-PROFILE:BEGIN -->\nProfile-ID: lab-x\n<!-- INTERVIEW-PROFILE:END -->\n", encoding="utf-8"
    )
    git(scratch_repo, "add", ".")
    git(scratch_repo, "commit", "-q", "-m", "profile")
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, data, _ = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0
    digest = attest.profile_block_digest((d / "profile.md").read_bytes())
    assert f"interview=standard/lab-x/sha256:{digest}" in data["message"]


# --- commit: marker protocol ------------------------------------------------------


def test_commit_refuses_transcript_without_marker(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    t = _transcript(tmp_path, scratch_repo, with_marker=False)
    code, data, err = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 4 and data == {"ok": False, "command": "commit", "exit_code": 4, "error": data["error"]}
    assert str(t) in err and f"{t.stat().st_size} bytes" in err
    assert f"GSA-APPROVAL {head} <utc-timestamp>" in err
    assert "emit the marker line" in err.lower()
    assert _head(scratch_repo) == head  # no commit created
    assert git(scratch_repo, "notes", "--ref=signoff", "show", head, check=False).returncode != 0


def test_commit_refuses_marker_for_an_unrelated_commit(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    other = "f" * 40
    t = _transcript(tmp_path, scratch_repo, sha=other)
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 4
    assert other in err and head in err
    assert _head(scratch_repo) == head


def test_commit_stale_when_marker_names_an_earlier_commit_on_this_branch(scratch_repo, tmp_path, monkeypatch, capsys):
    """prepare ran, the human approved, then the branch moved: the marker names
    an ancestor of HEAD — stale (exit 3), not a wrong file (exit 4)."""
    _prepared(scratch_repo)
    prepared = _head(scratch_repo)
    t = _transcript(tmp_path, scratch_repo, sha=prepared)
    commit_file(scratch_repo, "later.txt", "x\n", "moves HEAD after prepare")
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 3
    assert "stale" in err and prepared in err and _head(scratch_repo) in err
    assert git(scratch_repo, "log", "--format=%s", "-1").stdout.strip() == "moves HEAD after prepare"


def test_commit_last_marker_governs(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    t = tmp_path / "t.jsonl"
    t.write_bytes(
        f"GSA-APPROVAL {head} 2026-09-09T00:00:00Z\nmore talk\nGSA-APPROVAL {'e' * 40} 2026-09-09T00:01:00Z\n".encode()
    )
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 4 and "e" * 40 in err


def test_commit_marker_outside_last_64kib_is_not_found(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    marker = f"GSA-APPROVAL {head} 2026-09-09T00:00:00Z\n".encode()
    t = tmp_path / "t.jsonl"
    t.write_bytes(marker + b"x" * (attest.MARKER_WINDOW + 10))
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 4 and "approval marker not found" in err
    assert f"last {attest.MARKER_WINDOW} bytes searched" in err
    t.write_bytes(b"x" * (attest.MARKER_WINDOW + 10) + marker)  # inside the window: accepted
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err


def test_commit_retries_once_for_a_late_flush(scratch_repo, tmp_path, monkeypatch):
    """The marker is not on disk on the first read but is on the second: one
    retry after MARKER_RETRY_DELAY covers a slow harness flush."""
    head = _head(scratch_repo)
    sleeps = []
    monkeypatch.setattr(attest, "MARKER_RETRY_DELAY", 0.25)
    monkeypatch.setattr(attest.time, "sleep", lambda s: sleeps.append(s))

    class LateAdapter:
        harness_id = "generic-file"

        def __init__(self):
            self.reads = 0

        def resolve_conversation_id(self):
            return "late"

        def describe_path(self):
            return "/virtual/late.jsonl"

        def fetch_transcript_bytes(self):
            # read 1: prepare's availability probe; read 2: the commit snapshot
            # (marker not flushed yet); read 3: the one retry.
            self.reads += 1
            return b"first read\n" if self.reads <= 2 else f"first read\nGSA-APPROVAL {head} 2026-09-09T00:00:00Z\n".encode()

    adapter = LateAdapter()
    _prepared(scratch_repo, env={}, adapter=adapter)
    opts = attest.CommitOptions(email="dev@example.com", level="standard", reference="main", push=False)
    result = attest.commit(str(scratch_repo), opts, env={}, adapter=adapter)
    assert result.marker_found and adapter.reads == 3 and sleeps == [0.25]
    assert result.transcript_bytes == str(len(f"first read\nGSA-APPROVAL {head} 2026-09-09T00:00:00Z\n"))
    assert result.transcript_digest == "sha256:" + hashlib.sha256(
        f"first read\nGSA-APPROVAL {head} 2026-09-09T00:00:00Z\n".encode()
    ).hexdigest()


def test_marker_survives_json_encoding_in_a_jsonl_transcript(scratch_repo):
    head = _head(scratch_repo)
    line = json.dumps({"role": "assistant", "content": f"Approved.\n\nGSA-APPROVAL {head} 2026-09-09T00:00:00Z\n\nRunning commit."})
    check = attest.find_marker(line.encode())
    assert check.found and check.sha == head


# --- integration branch and reference precedence (docs/attest-any-target.md §2.10) ------


def _repo_with_origin_default(tmp_path, default="dev"):
    """A clone whose origin's default branch (origin/HEAD) is `default`."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "-q", "--bare", "-b", default)
    work = init_repo(tmp_path / "work", branch=default)
    commit_file(work, "base.txt", "base\n", "base commit")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "-u", "origin", default)
    git(work, "remote", "set-head", "origin", default)
    return work


def _write_config(repo, branch):
    d = repo / ".git-signoff"
    d.mkdir(exist_ok=True)
    (d / "config.json").write_text(json.dumps({"integration_branch": branch}) + "\n")


def test_prepare_uses_the_configured_integration_branch_over_main(scratch_repo, monkeypatch, capsys):
    """scratch_repo has main and feature. With `dev` configured and present, dev
    wins over the main fallback; the warning names the config file."""
    git(scratch_repo, "branch", "dev", "main")
    commit_file(scratch_repo, "on-dev.txt", "d\n", "dev-only commit")  # on feature, but dev stays at main
    git(scratch_repo, "checkout", "-q", "dev")
    commit_file(scratch_repo, "dev.txt", "x\n", "dev advances")
    dev = _head(scratch_repo)
    git(scratch_repo, "checkout", "-q", "feature")
    _write_config(scratch_repo, "dev")
    code, data, err = run_json(monkeypatch, capsys, scratch_repo, "prepare")
    assert code == 0, err
    assert data["reference"] == "dev" and data["integration_branch"] == "dev"
    assert data["base_sha"] == git(scratch_repo, "merge-base", "dev", "feature").stdout.strip()
    assert any("integration branch 'dev'" in w and ".git-signoff" in w for w in data["warnings"])
    assert dev != data["base_sha"]  # merge-base, not dev's tip


def test_prepare_falls_back_to_origin_head_without_config(tmp_path, monkeypatch, capsys):
    """No config: the remote's default branch (origin/HEAD → dev) is the base,
    ahead of the main/master guess. This is the documented behaviour change."""
    work = _repo_with_origin_default(tmp_path, "dev")
    git(work, "checkout", "-q", "-b", "feature")
    commit_file(work, "feat.txt", "f\n", "feature")
    code, data, err = run_json(monkeypatch, capsys, work, "prepare")
    assert code == 0, err
    assert data["reference"] == "origin/dev" and data["integration_branch"] == "dev"
    assert any("origin/HEAD" in w for w in data["warnings"])


def test_prepare_explicit_reference_beats_config(scratch_repo, monkeypatch, capsys):
    git(scratch_repo, "branch", "dev", "main")
    _write_config(scratch_repo, "dev")
    code, data, _ = run_json(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 0 and data["reference"] == "main"


def test_prepare_on_integration_branch_with_nothing_unpushed_has_no_range(tmp_path, monkeypatch, capsys):
    work = _repo_with_origin_default(tmp_path, "dev")
    _write_config(work, "dev")
    code, data, err = run_json(monkeypatch, capsys, work, "prepare")
    assert code == 2 and data["ok"] is False
    assert "integration branch 'dev'" in err and "nothing unpushed" in err


def test_prepare_on_integration_branch_attests_own_unpushed_commits(tmp_path, monkeypatch, capsys):
    """The direct-push case (§2.4): on dev with origin/dev a strict ancestor of
    HEAD, the range is the reviewer's own unpushed commits."""
    work = _repo_with_origin_default(tmp_path, "dev")
    _write_config(work, "dev")
    commit_file(work, "local.txt", "l\n", "unpushed on dev")
    code, data, err = run_json(monkeypatch, capsys, work, "prepare")
    assert code == 0, err
    assert data["reference"] == "origin/dev"
    assert data["base_sha"] == git(work, "rev-parse", "origin/dev").stdout.strip()


def test_prepare_on_integration_branch_refuses_a_diverged_upstream(tmp_path, monkeypatch, capsys):
    work = _repo_with_origin_default(tmp_path, "dev")
    _write_config(work, "dev")
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), "other")
    git(other, "config", "user.email", "o@example.com")
    git(other, "config", "user.name", "O")
    commit_file(other, "theirs.txt", "t\n", "someone else pushed to dev")
    git(other, "push", "-q", "origin", "dev")
    git(work, "fetch", "-q", "origin")
    commit_file(work, "mine.txt", "m\n", "my local dev commit")
    code, _, err = run(monkeypatch, capsys, work, "prepare")
    assert code == 3 and "diverged" in err and "origin/dev" in err


def test_prepare_on_a_feature_branch_is_unaffected_by_integration_rules(tmp_path, monkeypatch, capsys):
    """Off the integration branch, an upstream that is the branch's own remote
    counterpart is still skipped, and the configured branch is the base."""
    work = _repo_with_origin_default(tmp_path, "dev")
    _write_config(work, "dev")
    git(work, "checkout", "-q", "-b", "feature")
    commit_file(work, "feat.txt", "f\n", "feature")
    git(work, "push", "-q", "-u", "origin", "feature")
    code, data, err = run_json(monkeypatch, capsys, work, "prepare")
    assert code == 0, err
    assert data["reference"] == "origin/dev"


def test_prepare_rejects_a_malformed_config(scratch_repo, monkeypatch, capsys):
    d = scratch_repo / ".git-signoff"
    d.mkdir()
    (d / "config.json").write_text("{not json")
    code, _, err = run(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 2 and "config.json" in err
    (d / "config.json").write_text(json.dumps({"integration_branch": "bad branch!"}))
    code, _, err = run(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 2 and "integration_branch must be a branch name" in err


def test_record_carries_the_integration_branch(scratch_repo, monkeypatch, capsys):
    git(scratch_repo, "branch", "dev", "main")
    _write_config(scratch_repo, "dev")
    assert run_json(monkeypatch, capsys, scratch_repo, "prepare")[0] == 0
    assert json.loads(_record(scratch_repo).read_text())["integration_branch"] == "dev"


# --- commit: the preparation record --------------------------------------------------


def test_prepare_writes_record_and_commit_clears_it(scratch_repo, tmp_path, monkeypatch, capsys):
    code, data, _ = run_json(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 0
    rec_path = _record(scratch_repo)
    assert data["record"] == str(rec_path) and rec_path.is_file()
    rec = json.loads(rec_path.read_text())
    assert rec["record_version"] == 1
    assert rec["reviewed_commit_sha"] == _head(scratch_repo) and rec["tree_sha"] == _tree(scratch_repo)
    assert rec["base_sha"] == git(scratch_repo, "rev-parse", "main").stdout.strip()
    assert rec["reference"] == "main" and rec["profile"]["id"] == "software-general"
    assert f"GSA-APPROVAL {rec['reviewed_commit_sha']} {rec['prepared_at']}" == data["marker"]
    code, out, _ = run(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert f"prepared state recorded: {rec_path}" in out
    t = _transcript(tmp_path, scratch_repo)
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert not rec_path.exists()  # attested: the next interview starts from prepare


def test_commit_without_record_is_stale_and_writes_nothing(scratch_repo, tmp_path, monkeypatch, capsys):
    head = _head(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 3 and "no preparation record" in err and "attest.py prepare" in err
    assert _head(scratch_repo) == head
    assert git(scratch_repo, "notes", "--ref=signoff", "list", check=False).stdout.strip() == ""


def test_commit_without_transcript_refuses_a_head_that_moved_after_prepare(scratch_repo, monkeypatch, capsys):
    """External review 2026-09-16: prepare on A, add B, commit --ack-no-transcript
    attested B — with no transcript there was no marker to tie commit to A.
    The record ties it regardless of transcript availability."""
    prepared = _head(scratch_repo)
    _prepared(scratch_repo)
    later = commit_file(scratch_repo, "later.txt", "x\n", "never reviewed")
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", "--ack-no-transcript",
    )
    assert code == 3
    assert "stale" in err and prepared in err and later in err
    assert _head(scratch_repo) == later  # no attestation commit
    assert git(scratch_repo, "notes", "--ref=signoff", "list", check=False).stdout.strip() == ""
    assert _record(scratch_repo).is_file()  # a refusal keeps the record; prepare overwrites it


def test_commit_refuses_when_the_profile_changed_after_prepare(scratch_repo, tmp_path, monkeypatch, capsys):
    """An untracked .git-signoff/profile.md dropped in mid-interview is not a
    dirty tree, but it changes which questions the attestation claims were
    asked: refused until prepare runs again against the new profile."""
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    d = scratch_repo / ".git-signoff"
    d.mkdir()
    (d / "profile.md").write_text(
        "<!-- INTERVIEW-PROFILE:BEGIN -->\nProfile-ID: swapped-in\n<!-- INTERVIEW-PROFILE:END -->\n", encoding="utf-8"
    )
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 3 and "profile changed" in err and "software-general from embedded-default" in err
    assert "swapped-in from repo-local" in err
    assert git(scratch_repo, "notes", "--ref=signoff", "list", check=False).stdout.strip() == ""
    _prepared(scratch_repo)  # re-prepared against the new profile: accepted, and recorded in the agent token
    code, data, err = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert "interview=standard/swapped-in/sha256:" in data["message"]


def test_commit_reference_must_agree_with_the_prepared_reference(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo, "main")
    t = _transcript(tmp_path, scratch_repo)
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "feature", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 2 and "differs from the prepared reference 'main'" in err
    # an equivalent spelling of the same commit is fine
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "HEAD~1", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err


def test_commit_attests_the_recorded_base_not_a_moved_reference(scratch_repo, tmp_path, monkeypatch, capsys):
    """If main advances during the interview, the attestation still carries the
    base the interview was conducted against; the trailers describe the range
    the human actually saw."""
    _prepared(scratch_repo, "main")
    base = git(scratch_repo, "rev-parse", "main").stdout.strip()
    git(scratch_repo, "branch", "-f", "main", "feature")  # main now contains HEAD
    t = _transcript(tmp_path, scratch_repo)
    code, data, err = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert attest.parse_trailers(data["message"])["Signoff-Base-SHA"] == [base]


def test_marker_command_reprints_the_recorded_marker(scratch_repo, monkeypatch, capsys):
    code, data, _ = run_json(monkeypatch, capsys, scratch_repo, "prepare", "--reference", "main")
    assert code == 0
    code, out, _ = run(monkeypatch, capsys, scratch_repo, "marker")
    assert code == 0 and out.strip() == data["marker"]  # same timestamp: the recorded one, not a fresh prepare
    prepared = data["reviewed_commit_sha"]
    commit_file(scratch_repo, "later.txt", "x\n", "moves HEAD")
    code, out, err = run(monkeypatch, capsys, scratch_repo, "marker", "--reference", "main")
    assert code == 3 and out == "" and "stale" in err and "attest.py prepare" in err
    assert json.loads(_record(scratch_repo).read_text())["reviewed_commit_sha"] == prepared  # untouched


def test_marker_without_record_is_stale(scratch_repo, monkeypatch, capsys):
    code, out, err = run(monkeypatch, capsys, scratch_repo, "marker")
    assert code == 3 and out == "" and "no preparation record" in err
    assert not _record(scratch_repo).exists()


def test_marker_cannot_clear_a_refusal(scratch_repo, monkeypatch, capsys):
    """External review, second pass: prepare A, add B, commit refuses, `marker`
    silently re-prepared for B, commit --ack-no-transcript attested B. Every
    command except prepare must leave a stale record stale."""
    _prepared(scratch_repo)
    later = commit_file(scratch_repo, "later.txt", "x\n", "never reviewed")
    args = ("commit", "--email", "dev@example.com", "--level", "standard", "--reference", "main", "--no-push", "--ack-no-transcript")
    assert run(monkeypatch, capsys, scratch_repo, *args)[0] == 3
    assert run(monkeypatch, capsys, scratch_repo, "marker", "--reference", "main")[0] == 3
    code, _, err = run(monkeypatch, capsys, scratch_repo, *args)
    assert code == 3 and "stale" in err
    assert _head(scratch_repo) == later and git(scratch_repo, "notes", "--ref=signoff", "list", check=False).stdout.strip() == ""


def test_record_lives_in_the_worktree_git_dir(scratch_repo, tmp_path, monkeypatch, capsys):
    wt = tmp_path / "wt"
    git(scratch_repo, "worktree", "add", "-q", str(wt), "-b", "wt-branch", "feature")
    commit_file(wt, "wt.txt", "w\n", "worktree commit")
    code, data, _ = run_json(monkeypatch, capsys, wt, "prepare", "--reference", "main")
    assert code == 0
    assert data["record"].startswith(str((scratch_repo / ".git" / "worktrees").resolve())) or "worktrees" in data["record"]
    assert not _record(scratch_repo).exists()  # the primary checkout's record is untouched


# --- commit: no-transcript path ---------------------------------------------------


def test_commit_without_transcript_requires_ack(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(tmp_path / "missing.jsonl")},
    )
    assert code == 4 and "--ack-no-transcript" in err and "missing.jsonl" in err
    assert _head(scratch_repo) == head


def test_commit_without_transcript_downgrades_with_ack_and_skips_marker(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    code, data, err = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", "--ack-no-transcript",
    )
    assert code == 0, err
    assert data["status"] == "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST"
    assert data["transcript_digest"] == "unavailable" and data["transcript_bytes"] == "unavailable"
    assert data["marker_found"] is False
    trailers = attest.parse_trailers(data["message"])
    assert trailers["Signoff-Harness-ID"] == ["unknown"]
    assert trailers["Signoff-Agent"] == ["harness=unknown/N/A model=unavailable reasoning=N/A interview=standard/software-general"]
    ok, _ = verify_signoff.check_head(str(scratch_repo), "HEAD")
    assert ok


# --- commit: argument validation (exit 2, nothing written) ----------------------


@pytest.mark.parametrize(
    "extra",
    [
        ["--tradeoff", "fine\nSignoff-Reviewed-Tree-SHA: " + "a" * 40],
        ["--risk", "fine\r\nSignoff-Status: VERIFIED_BY_HUMAN"],
        ["--summary", "Looks good.\nSignoff-Reviewed-Tree-SHA: " + "b" * 40],
        ["--summary", "Looks good.\r\nfine"],
        ["--tradeoff", "   "],
        ["--model", "bad model!"],
    ],
)
def test_commit_rejects_unsafe_free_text(scratch_repo, tmp_path, monkeypatch, capsys, extra):
    head = _head(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", *extra, env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 2, err
    assert _head(scratch_repo) == head


@pytest.mark.parametrize("email", ["not-an-email", "dev@example.com\nSignoff-Status: VERIFIED_BY_HUMAN", ""])
def test_commit_rejects_bad_email(scratch_repo, tmp_path, monkeypatch, capsys, email):
    head = _head(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", email, "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 2 and "email" in err.lower()
    assert _head(scratch_repo) == head


def test_commit_requires_level_and_email(scratch_repo, monkeypatch, capsys):
    code, _, err = run(monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com")
    assert code == 2
    code, _, err = run(monkeypatch, capsys, scratch_repo, "commit", "--level", "standard")
    assert code == 2
    code, _, err = run(monkeypatch, capsys, scratch_repo, "commit", "--email", "d@e.com", "--level", "Tier 2")
    assert code == 2


def test_commit_allows_multiline_summary_without_trailer_lines(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, data, _ = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", "--summary", "Line one.\nLine two.", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0 and "Line two." in data["message"]


# --- commit: staleness and dry run ------------------------------------------------


def test_commit_refuses_dirty_tree(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    (scratch_repo / "feat.txt").write_text("dirty\n")
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 3 and "Unstaged" in err


def test_commit_dry_run_prints_message_and_creates_nothing(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    t = _transcript(tmp_path, scratch_repo, with_marker=False)  # dry run precedes approval: no marker yet
    code, out, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--tradeoff", "t1", "--reference", "main", "--dry-run", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert out.startswith(f"[SIGNOFF {head[:7]}]: human comprehension and risk attestation\n")
    assert "Signoff-Tradeoff: t1\n" in out
    assert "dry run: nothing committed" in out
    assert "approval marker: not yet in the transcript (dry run; required at commit)" in out
    assert "provisional" in err
    assert _head(scratch_repo) == head
    assert git(scratch_repo, "notes", "--ref=signoff", "list", check=False).stdout.strip() == ""
    code, data, _ = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--dry-run", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0 and data["dry_run"] is True and data["attestation_sha"] is None
    assert data["status"] == "VERIFIED_BY_HUMAN" and data["marker_found"] is False


# --- commit: self-checks and rollback ----------------------------------------------


def test_commit_post_commit_self_check_failure_rolls_back(scratch_repo, tmp_path, monkeypatch):
    _prepared(scratch_repo)
    head, tree = _head(scratch_repo), _tree(scratch_repo)
    git(scratch_repo, "notes", "--ref=signoff", "add", "-m", "pre-existing note on tree", tree)
    prior_tree_note = git(scratch_repo, "notes", "--ref=signoff", "show", tree).stdout
    t = _transcript(tmp_path, scratch_repo)
    adapter = attest.GenericFileAdapter(str(t))

    class RejectingVerifier:
        parse_trailers = staticmethod(verify_signoff.parse_trailers)
        validate_single = staticmethod(verify_signoff.validate_single)

        @staticmethod
        def check_head(repo, target):
            return False, ["FAIL: simulated verifier rejection"]

    opts = attest.CommitOptions(email="dev@example.com", level="standard", reference="main", push=False)
    with pytest.raises(attest.AttestError) as exc:
        attest.commit(str(scratch_repo), opts, env={}, adapter=adapter, verifier=RejectingVerifier())
    assert exc.value.code == 7 and "simulated verifier rejection" in str(exc.value)
    assert _head(scratch_repo) == head  # empty commit removed
    assert git(scratch_repo, "diff", "--quiet").returncode == 0 and git(scratch_repo, "diff", "--cached", "--quiet").returncode == 0
    assert git(scratch_repo, "notes", "--ref=signoff", "show", head, check=False).returncode != 0  # note removed
    assert git(scratch_repo, "notes", "--ref=signoff", "show", tree).stdout == prior_tree_note  # note restored


def test_commit_pre_commit_structural_self_check_failure_writes_nothing(scratch_repo, tmp_path, monkeypatch):
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    adapter = attest.GenericFileAdapter(str(t))

    class ParanoidVerifier:
        parse_trailers = staticmethod(verify_signoff.parse_trailers)

        @staticmethod
        def validate_single(trailers):
            return ["simulated structural problem"]

        check_head = staticmethod(verify_signoff.check_head)

    opts = attest.CommitOptions(email="dev@example.com", level="standard", reference="main", push=False)
    with pytest.raises(attest.AttestError) as exc:
        attest.commit(str(scratch_repo), opts, env={}, adapter=adapter, verifier=ParanoidVerifier())
    assert exc.value.code == 7 and "bug in attest.py" in str(exc.value)
    assert _head(scratch_repo) == head
    assert git(scratch_repo, "notes", "--ref=signoff", "list", check=False).stdout.strip() == ""


def test_commit_integrity_failure_rolls_back(scratch_repo, tmp_path, monkeypatch):
    """If the commit lands with a different tree (simulated by a post-commit
    hook amending it), the helper removes it and exits 7."""
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    hook = scratch_repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nif [ -z \"$GSA_IN_HOOK\" ]; then echo smuggled > smuggled.txt; git add smuggled.txt; GSA_IN_HOOK=1 git commit -q --amend --no-edit; fi\n")
    hook.chmod(0o755)
    t = _transcript(tmp_path, scratch_repo)
    adapter = attest.GenericFileAdapter(str(t))
    opts = attest.CommitOptions(email="dev@example.com", level="standard", reference="main", push=False)
    with pytest.raises(attest.AttestError) as exc:
        attest.commit(str(scratch_repo), opts, env={}, adapter=adapter)
    assert exc.value.code == 7 and "integrity" in str(exc.value)
    assert _head(scratch_repo) == head
    assert git(scratch_repo, "notes", "--ref=signoff", "list", check=False).stdout.strip() == ""


def test_rollback_failure_is_reported_not_claimed(scratch_repo, tmp_path, monkeypatch):
    """If `git reset --soft HEAD~1` fails inside the rollback, the exit-7 message
    must say ROLLBACK INCOMPLETE and name the step, never "commit removed"."""
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    adapter = attest.GenericFileAdapter(str(t))

    class RejectingVerifier:
        parse_trailers = staticmethod(verify_signoff.parse_trailers)
        validate_single = staticmethod(verify_signoff.validate_single)

        @staticmethod
        def check_head(repo, target):
            return False, ["FAIL: simulated verifier rejection"]

    real_git = attest.GitRepo.git

    def failing_reset(self, *args, check=True):
        if args[:2] == ("reset", "-q"):
            return subprocess.CompletedProcess(["git", *args], 128, "", "fatal: Unable to create '.git/HEAD.lock': File exists.")
        return real_git(self, *args, check=check)

    monkeypatch.setattr(attest.GitRepo, "git", failing_reset)
    opts = attest.CommitOptions(email="dev@example.com", level="standard", reference="main", push=False)
    with pytest.raises(attest.AttestError) as exc:
        attest.commit(str(scratch_repo), opts, env={}, adapter=adapter, verifier=RejectingVerifier())
    msg = str(exc.value)
    assert exc.value.code == 7
    assert "ROLLBACK INCOMPLETE" in msg and "HEAD.lock" in msg and "git reset --soft HEAD~1" in msg
    assert "commit and notes removed" not in msg
    assert "git log -1" in msg
    # the message told the truth: the rejected attestation commit is still at HEAD,
    # while the notes (whose restore did not fail) are gone
    assert _head(scratch_repo) != head and git(scratch_repo, "rev-parse", "HEAD~1").stdout.strip() == head
    assert git(scratch_repo, "notes", "--ref=signoff", "list", check=False).stdout.strip() == ""


def test_rollback_success_message_is_unqualified(scratch_repo, tmp_path, monkeypatch):
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    adapter = attest.GenericFileAdapter(str(t))

    class RejectingVerifier:
        parse_trailers = staticmethod(verify_signoff.parse_trailers)
        validate_single = staticmethod(verify_signoff.validate_single)

        @staticmethod
        def check_head(repo, target):
            return False, ["FAIL: simulated verifier rejection"]

    opts = attest.CommitOptions(email="dev@example.com", level="standard", reference="main", push=False)
    with pytest.raises(attest.AttestError) as exc:
        attest.commit(str(scratch_repo), opts, env={}, adapter=adapter, verifier=RejectingVerifier())
    assert "commit and notes removed" in str(exc.value) and "ROLLBACK INCOMPLETE" not in str(exc.value)


def test_load_verifier_requires_the_sibling_file(tmp_path, monkeypatch):
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    shutil.copy(os.path.join(SKILL_DIR, "attest.py"), lonely / "attest.py")
    repo = init_repo(tmp_path / "repo")
    commit_file(repo, "a.txt", "a", "a")
    proc = subprocess.run(
        [sys.executable, str(lonely / "attest.py"), "commit", "--email", "d@e.com", "--level", "standard", "--no-push"],
        cwd=str(repo), capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "verify_signoff.py not found next to attest.py" in proc.stderr


# --- commit: notes push ------------------------------------------------------------


@pytest.fixture
def repo_with_origin(tmp_path):
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "-q", "--bare", "-b", "main")
    work = init_repo(tmp_path / "work")
    commit_file(work, "base.txt", "base\n", "base commit")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "-u", "origin", "main")
    git(work, "checkout", "-q", "-b", "feature")
    commit_file(work, "feat.txt", "feature\n", "feature commit")
    git(work, "branch", "-q", "--set-upstream-to=origin/main")
    return work, origin


def test_commit_pushes_notes_by_default(repo_with_origin, tmp_path, monkeypatch, capsys):
    work, origin = repo_with_origin
    _prepared(work, None)
    t = _transcript(tmp_path, work)
    code, data, err = run_json(
        monkeypatch, capsys, work, "commit", "--email", "dev@example.com", "--level", "standard",
        env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert data["notes_pushed"] is True and data["notes_push_reason"] is None
    assert data["notes_merged_remote"] is False  # first notes push ever: nothing to merge
    remote_notes = git(work, "ls-remote", "origin", "refs/notes/signoff").stdout.split()
    assert remote_notes and remote_notes[0] == git(work, "rev-parse", "refs/notes/signoff").stdout.strip()
    # the branch itself is not pushed by the helper
    assert git(work, "ls-remote", "origin", "refs/heads/feature").stdout.strip() == ""


def test_commit_reports_refused_notes_push_and_exits_zero(repo_with_origin, tmp_path, monkeypatch, capsys):
    work, origin = repo_with_origin
    _prepared(work, None)
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'remote: notes refs are not accepted here (403)' >&2\nexit 1\n")
    hook.chmod(0o755)
    t = _transcript(tmp_path, work)
    code, data, err = run_json(
        monkeypatch, capsys, work, "commit", "--email", "dev@example.com", "--level", "standard",
        env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert data["notes_pushed"] is False
    assert "notes push refused" in data["notes_push_reason"]
    assert data["attestation_sha"] == _head(work)  # the attestation commit stands
    assert git(work, "notes", "--ref=signoff", "show", data["noted_shas"][0]).returncode == 0


def test_commit_merges_diverged_remote_notes_before_push(repo_with_origin, tmp_path, monkeypatch, capsys):
    work, origin = repo_with_origin
    _prepared(work, None)
    reviewed = _head(work)
    # a colleague already pushed a note on the same reviewed commit
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(origin), "other")
    git(other, "config", "user.email", "o@example.com")
    git(other, "config", "user.name", "O")
    git(other, "fetch", "-q", "origin", "refs/heads/main")
    git(other, "notes", "--ref=signoff", "add", "-m", "Signoff-Conversation-ID: colleague", git(other, "rev-parse", "origin/main").stdout.strip())
    git(other, "push", "-q", "origin", "refs/notes/signoff")
    # our own local notes ref already exists and diverges: a direct fetch would be rejected
    git(work, "notes", "--ref=signoff", "add", "-m", "Signoff-Conversation-ID: earlier-local", git(work, "rev-parse", "main").stdout.strip())
    t = _transcript(tmp_path, work)
    code, data, err = run_json(
        monkeypatch, capsys, work, "commit", "--email", "dev@example.com", "--level", "standard",
        env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert data["notes_pushed"] is True and data["notes_merged_remote"] is True
    merged = git(work, "notes", "--ref=signoff", "show", git(work, "rev-parse", "main").stdout.strip()).stdout
    assert "colleague" in merged and "earlier-local" in merged
    assert git(work, "notes", "--ref=signoff", "show", reviewed).returncode == 0
    assert git(work, "ls-remote", "origin", "refs/notes/signoff").stdout.split()[0] == git(
        work, "rev-parse", "refs/notes/signoff"
    ).stdout.strip()


def test_commit_without_origin_reports_push_failure(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    t = _transcript(tmp_path, scratch_repo)
    code, data, err = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert data["notes_pushed"] is False and "refused" in data["notes_push_reason"]


# --- signing ----------------------------------------------------------------------


def test_commit_no_sign_flag_suppresses_signing(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    git(scratch_repo, "config", "user.signingkey", "DEADBEEF")
    git(scratch_repo, "config", "gpg.program", "/nonexistent/gpg")
    t = _transcript(tmp_path, scratch_repo)
    code, data, err = run_json(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", "--no-sign", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert data["signed"] is False


def test_commit_signing_failure_is_a_git_failure_with_nothing_written(scratch_repo, tmp_path, monkeypatch, capsys):
    _prepared(scratch_repo)
    head = _head(scratch_repo)
    git(scratch_repo, "config", "user.signingkey", "DEADBEEF")
    git(scratch_repo, "config", "gpg.program", "/nonexistent/gpg")
    t = _transcript(tmp_path, scratch_repo)
    code, _, err = run(
        monkeypatch, capsys, scratch_repo, "commit", "--email", "dev@example.com", "--level", "standard",
        "--reference", "main", "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 6 and "git commit" in err
    assert _head(scratch_repo) == head
    assert git(scratch_repo, "notes", "--ref=signoff", "list", check=False).stdout.strip() == ""


# --- CLI surface ----------------------------------------------------------------------


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        attest.main(["--version"])
    assert exc.value.code == 0
    assert "attest.py 0.5.0" in capsys.readouterr().out


def test_no_subcommand_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        attest.main([])
    assert exc.value.code == 2


def test_attest_exits_loudly_below_python_floor(tmp_path):
    script = os.path.join(SKILL_DIR, "attest.py")
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import runpy, sys\n"
        "sys.version_info = (3, 9, 18, 'final', 0)\n"
        "sys.argv = ['attest.py', 'prepare']\n"
        f"runpy.run_path({script!r}, run_name='__main__')\n"
    )
    proc = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True)
    assert proc.returncode == 1
    assert "needs Python 3.10 or newer" in proc.stderr and "3.9" in proc.stderr


# --- end to end through the vendored copy ---------------------------------------


def test_end_to_end_vendored_by_init_then_attested_and_verified(tmp_path):
    """init.py vendors skills/git-signoff/ into a scratch repo; attest.py runs
    from the vendored copy; the verifier passes on the result (head mode on the
    attestation tip, history mode, and the tree-note lookup after a squash)."""
    sys.path.insert(0, REPO_ROOT)
    try:
        import init as init_mod
    except ImportError:
        pytest.skip("init.py not present in this repository (leaf initializer test)")
    finally:
        sys.path.pop(0)

    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "-q", "--bare", "-b", "main")
    repo = init_repo(tmp_path / "adopter")
    (repo / "CLAUDE.md").write_text("# project\n")
    git(repo, "add", "CLAUDE.md")
    commit_file(repo, "README.md", "# Adopter\n", "initial")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "-u", "origin", "main")

    result = init_mod.run_init(
        repo_root=repo, profile_id="software-general", skip_ruleset=True, non_interactive=True,
        skill_source=SKILL_DIR, skill_target="claude",
    )
    assert result.success and result.branch == "git-signoff/init"
    vendored = repo / ".claude" / "skills" / "git-signoff"
    assert (vendored / "attest.py").is_file() and (vendored / "verify_signoff.py").is_file()
    assert not (vendored / "__pycache__").exists()
    assert (repo / ".github" / "workflows" / "git-signoff.yml").is_file()
    assert (repo / ".git-signoff" / "profile.md").is_file()

    env = {**os.environ, "GIT_SIGNOFF_NO_UPDATE_CHECK": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    for var in ("CLAUDE_CODE_SESSION_ID", "GIT_SIGNOFF_TRANSCRIPT_FILE", "ANTHROPIC_MODEL", "CLAUDE_CODE_VERSION", "CLAUDE_EFFORT"):
        env.pop(var, None)

    # red before the attestation
    proc = subprocess.run([sys.executable, str(vendored / "verify_signoff.py"), "--mode", "head"], cwd=repo, capture_output=True, text=True, env=env)
    assert proc.returncode == 1 and "FAIL" in proc.stdout

    proc = subprocess.run([sys.executable, str(vendored / "attest.py"), "prepare", "--reference", "main", "--json"], cwd=repo, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    prepared = json.loads(proc.stdout)
    assert prepared["profile"]["source"] == "repo-local" and prepared["profile"]["id"] == "software-general"
    transcript = tmp_path / "session.jsonl"
    transcript.write_bytes(b'{"model":"m-1"}\n' + f"agent: {prepared['marker']}\n".encode())
    env["GIT_SIGNOFF_TRANSCRIPT_FILE"] = str(transcript)

    proc = subprocess.run(
        [sys.executable, str(vendored / "attest.py"), "commit", "--email", "dev@example.com", "--level", "standard",
         "--tradeoff", "scaffold only", "--reference", "main", "--json"],
        cwd=repo, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    committed = json.loads(proc.stdout)
    assert committed["status"] == "VERIFIED_BY_HUMAN" and committed["notes_pushed"] is True
    assert f"sha256:{prepared['profile']['digest']}" in committed["message"]

    proc = subprocess.run([sys.executable, str(vendored / "verify_signoff.py"), "--mode", "head"], cwd=repo, capture_output=True, text=True, env=env)
    assert proc.returncode == 0 and "PASS" in proc.stdout, proc.stdout
    proc = subprocess.run([sys.executable, str(vendored / "verify_signoff.py"), "--mode", "history", "--target", "HEAD"], cwd=repo, capture_output=True, text=True, env=env)
    assert proc.returncode == 0 and "1 valid attestation" in proc.stdout, proc.stdout

    # simulated squash merge onto an unchanged main: the tree-note lookup carries the attestation
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--squash", result.branch)
    git(repo, "commit", "-q", "-m", "squash: scaffold git signoff attestation")
    proc = subprocess.run([sys.executable, str(vendored / "verify_signoff.py"), "--mode", "head"], cwd=repo, capture_output=True, text=True, env=env)
    assert proc.returncode == 0 and "note on tree" in proc.stdout, proc.stdout


# --- target mode: attest any branch from anywhere (docs/attest-any-target.md §2) ----


@pytest.fixture
def lab(tmp_path):
    """origin (default dev) + reviewer clone sitting on dev with the config +
    author clone that pushed `feature` (two commits ahead of dev)."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "-q", "--bare", "-b", "dev")
    author = init_repo(tmp_path / "author", branch="dev")
    commit_file(author, "base.txt", "base\n", "base commit")
    (author / ".git-signoff").mkdir()
    (author / ".git-signoff" / "config.json").write_text(json.dumps({"integration_branch": "dev"}) + "\n")
    git(author, "add", ".git-signoff")
    git(author, "commit", "-q", "-m", "config: integration branch dev")
    git(author, "remote", "add", "origin", str(origin))
    git(author, "push", "-q", "-u", "origin", "dev")
    git(author, "checkout", "-q", "-b", "feature")
    commit_file(author, "feat.py", "x = 1\n", "feature: first")
    commit_file(author, "feat.py", "x = 2\n", "feature: second")
    git(author, "push", "-q", "-u", "origin", "feature")
    reviewer = tmp_path / "reviewer"
    git(tmp_path, "clone", "-q", str(origin), "reviewer")
    git(reviewer, "config", "user.email", "pi@example.com")
    git(reviewer, "config", "user.name", "PI")
    git(reviewer, "config", "commit.gpgsign", "false")
    git(reviewer, "remote", "set-head", "origin", "dev")
    return origin, author, reviewer


def _origin_tip(origin, branch):
    return git(origin, "rev-parse", f"refs/heads/{branch}").stdout.strip()


def test_prepare_target_reviews_the_remote_tip_from_the_integration_branch(lab, monkeypatch, capsys):
    origin, author, reviewer = lab
    feature_tip = _origin_tip(origin, "feature")
    (reviewer / "scratch.txt").write_text("the reviewer's own uncommitted work\n")  # target mode ignores the checkout
    code, data, err = run_json(monkeypatch, capsys, reviewer, "prepare", "--target", "feature")
    assert code == 0, err
    assert data["target"] == "feature" and data["target_ref"] == "refs/remotes/origin/feature"
    assert data["reviewed_commit_sha"] == feature_tip
    assert data["reference"] == "origin/dev" and data["base_sha"] == _origin_tip(origin, "dev")
    assert data["hints"]["executable_files"] == 1 and len(data["name_status"]) == 1
    assert data["marker"].startswith(f"GSA-APPROVAL {feature_tip} ")
    rec = json.loads(_record(reviewer).read_text())
    assert rec["target"] == "feature" and rec["integration_branch"] == "dev"
    assert git(reviewer, "branch", "--show-current").stdout.strip() == "dev"  # never switched
    code, out, _ = run(monkeypatch, capsys, reviewer, "prepare", "--target", "feature")
    assert "target: origin/feature" in out


@pytest.mark.parametrize("spelling", ["feature", "origin/feature", "refs/heads/feature", "refs/remotes/origin/feature"])
def test_prepare_target_spellings_resolve_to_the_remote_branch(lab, monkeypatch, capsys, spelling):
    origin, _, reviewer = lab
    code, data, err = run_json(monkeypatch, capsys, reviewer, "prepare", "--target", spelling)
    assert code == 0, err
    assert data["target"] == "feature" and data["reviewed_commit_sha"] == _origin_tip(origin, "feature")


def test_prepare_target_refuses_the_integration_branch_and_unknown_branches(lab, monkeypatch, capsys):
    _, _, reviewer = lab
    code, _, err = run(monkeypatch, capsys, reviewer, "prepare", "--target", "dev")
    assert code == 2 and "is the integration branch" in err
    code, _, err = run(monkeypatch, capsys, reviewer, "prepare", "--target", "nope")
    assert code == 2 and "does not exist on origin" in err
    code, _, err = run(monkeypatch, capsys, reviewer, "prepare", "--target", "bad name")
    assert code == 2 and "not a branch name" in err


def test_prepare_target_refuses_a_tip_that_is_already_an_attestation(lab, tmp_path, monkeypatch, capsys):
    origin, author, reviewer = lab
    _prepared(author, None)  # author attests on their own branch the usual way
    t = _transcript(tmp_path, author)
    code, _, err = run(monkeypatch, capsys, author, "commit", "--email", "a@example.com", "--level", "standard",
                       env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)})
    assert code == 0, err
    git(author, "push", "-q", "origin", "feature")
    code, _, err = run(monkeypatch, capsys, reviewer, "prepare", "--target", "feature")
    assert code == 3 and "already ends in an attestation" in err


def test_commit_target_pushes_the_attestation_to_the_branch_and_nothing_else_moves(lab, tmp_path, monkeypatch, capsys):
    origin, author, reviewer = lab
    feature_tip = _origin_tip(origin, "feature")
    dev_tip = _origin_tip(origin, "dev")
    git(reviewer, "branch", "feature", "origin/feature~1")  # a stale local copy, must not move
    stale_local = git(reviewer, "rev-parse", "feature").stdout.strip()
    code, data, err = run_json(monkeypatch, capsys, reviewer, "prepare", "--target", "feature")
    assert code == 0, err
    t = _transcript(tmp_path, reviewer, sha=feature_tip)
    code, data, err = run_json(
        monkeypatch, capsys, reviewer, "commit", "--email", "pi@example.com", "--level", "skeptical",
        "--tradeoff", "reviewed from dev", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)},
    )
    assert code == 0, err
    assert data["target"] == "feature" and data["branch_pushed"] is True
    attestation = data["attestation_sha"]
    # origin/feature now ends in the attestation, parented on the reviewed tip, empty
    assert _origin_tip(origin, "feature") == attestation
    assert git(origin, "rev-parse", f"{attestation}~1").stdout.strip() == feature_tip
    assert git(origin, "rev-parse", f"{attestation}^{{tree}}").stdout.strip() == git(origin, "rev-parse", f"{feature_tip}^{{tree}}").stdout.strip()
    trailers = attest.parse_trailers(git(origin, "log", "-1", "--format=%B", attestation).stdout)
    assert trailers["Signoff-Reviewed-Commit-SHA"] == [feature_tip]
    assert trailers["Signoff-Base-SHA"] == [dev_tip]
    assert trailers["Signoff-Verified-By"] == ["pi@example.com"]
    assert trailers["Signoff-Tradeoff"] == ["reviewed from dev"]
    # notes were published on the reviewed commit and its tree
    assert data["notes_pushed"] is True and data["noted_shas"] == [feature_tip, trailers["Signoff-Reviewed-Tree-SHA"][0]]
    assert git(origin, "rev-parse", "-q", "--verify", "refs/notes/signoff").returncode == 0
    # nothing else moved: dev, the reviewer's HEAD, the stale local branch
    assert _origin_tip(origin, "dev") == dev_tip
    assert git(reviewer, "branch", "--show-current").stdout.strip() == "dev"
    assert git(reviewer, "rev-parse", "HEAD").stdout.strip() == dev_tip
    assert git(reviewer, "rev-parse", "feature").stdout.strip() == stale_local
    assert git(reviewer, "rev-parse", "origin/feature").stdout.strip() == attestation  # remote-tracking ref refreshed
    assert not _record(reviewer).exists()
    # the PR check passes on the pushed branch, from any clone
    git(author, "fetch", "-q", "origin")
    ok, lines = verify_signoff.check_head(str(author), "origin/feature")
    assert ok, lines


def test_commit_target_human_output_and_dry_run(lab, tmp_path, monkeypatch, capsys):
    origin, _, reviewer = lab
    feature_tip = _origin_tip(origin, "feature")
    assert run(monkeypatch, capsys, reviewer, "prepare", "--target", "feature")[0] == 0
    t = _transcript(tmp_path, reviewer, sha=feature_tip, with_marker=False)
    code, out, err = run(monkeypatch, capsys, reviewer, "commit", "--email", "pi@example.com", "--level", "standard",
                         "--dry-run", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)})
    assert code == 0, err
    assert out.startswith(f"[SIGNOFF {feature_tip[:7]}]") and "dry run: nothing committed" in out
    assert _origin_tip(origin, "feature") == feature_tip and _record(reviewer).exists()
    t = _transcript(tmp_path, reviewer, sha=feature_tip)
    code, out, err = run(monkeypatch, capsys, reviewer, "commit", "--email", "pi@example.com", "--level", "standard",
                         env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)})
    assert code == 0, err
    assert "pushed to: origin/feature" in out and "no local ref moved" in out


def test_commit_target_race_leaves_the_branch_untouched_and_the_notes_published(lab, tmp_path, monkeypatch, capsys):
    """The author pushes during the interview: the lease rejects the push; the
    branch is theirs; the notes describe the reviewed commit and tree, which
    is true, and the message says so (§2.5 failure contract)."""
    origin, author, reviewer = lab
    reviewed = _origin_tip(origin, "feature")
    assert run(monkeypatch, capsys, reviewer, "prepare", "--target", "feature")[0] == 0
    commit_file(author, "feat.py", "x = 3\n", "feature: third, mid-interview")
    git(author, "push", "-q", "origin", "feature")
    moved = _origin_tip(origin, "feature")
    t = _transcript(tmp_path, reviewer, sha=reviewed)
    code, _, err = run(monkeypatch, capsys, reviewer, "commit", "--email", "pi@example.com", "--level", "standard",
                       env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)})
    assert code == 3 and "stale" in err and reviewed in err and moved in err
    assert _origin_tip(origin, "feature") == moved  # untouched
    assert git(origin, "rev-parse", "-q", "--verify", "refs/notes/signoff", check=False).returncode != 0  # refused before anything was published
    assert _record(reviewer).exists()  # a refusal keeps the record; prepare --target starts over


def test_commit_target_lease_rejection_after_notes_is_reported_truthfully(lab, tmp_path, monkeypatch):
    """Force the narrowest race: the branch moves between the pre-push fetch and
    the lease push. Notes are already published; the message must say so."""
    origin, author, reviewer = lab
    reviewed = _origin_tip(origin, "feature")
    attest.prepare(str(reviewer), target="feature")
    t = _transcript(tmp_path, reviewer, sha=reviewed)
    real_git = attest.GitRepo.git

    def racing_git(self, *args, check=True):
        if args[:2] == ("push", "-q") and any(a.startswith("--force-with-lease") for a in args):
            commit_file(author, "feat.py", "x = 9\n", "feature: sneaks in")
            git(author, "push", "-q", "origin", "feature")
        return real_git(self, *args, check=check)

    monkeypatch.setattr(attest.GitRepo, "git", racing_git)
    opts = attest.CommitOptions(email="pi@example.com", level="standard")
    with pytest.raises(attest.AttestError) as exc:
        attest.commit(str(reviewer), opts, env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)})
    msg = str(exc.value)
    assert exc.value.code == 3 and "rejected" in msg and "were published" in msg and "untouched" in msg
    assert git(origin, "log", "-1", "--format=%s", "feature").stdout.strip() == "feature: sneaks in"
    note = git(origin, "notes", "--ref=signoff", "show", reviewed, check=False)
    assert note.returncode == 0 and f"Signoff-Reviewed-Commit-SHA: {reviewed}" in note.stdout


def test_commit_target_refuses_no_push(lab, tmp_path, monkeypatch, capsys):
    origin, _, reviewer = lab
    assert run(monkeypatch, capsys, reviewer, "prepare", "--target", "feature")[0] == 0
    t = _transcript(tmp_path, reviewer, sha=_origin_tip(origin, "feature"))
    code, _, err = run(monkeypatch, capsys, reviewer, "commit", "--email", "pi@example.com", "--level", "standard",
                       "--no-push", env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)})
    assert code == 2 and "--no-push is not available" in err
    assert _origin_tip(origin, "feature") != ""  # unchanged, no attestation


def test_marker_works_from_a_target_record(lab, monkeypatch, capsys):
    origin, _, reviewer = lab
    code, data, _ = run_json(monkeypatch, capsys, reviewer, "prepare", "--target", "feature")
    assert code == 0
    code, out, _ = run(monkeypatch, capsys, reviewer, "marker")
    assert code == 0 and out.strip() == data["marker"]


def test_targets_lists_unmerged_remote_branches_most_recent_first(lab, tmp_path, monkeypatch, capsys):
    origin, author, reviewer = lab
    # a merged branch, an attested branch, and an older unmerged branch
    git(author, "checkout", "-q", "-b", "merged", "dev")
    commit_file(author, "m.txt", "m\n", "merged work")
    git(author, "push", "-q", "origin", "merged")
    git(author, "checkout", "-q", "dev")
    git(author, "merge", "-q", "--ff-only", "merged")
    git(author, "push", "-q", "origin", "dev")
    git(author, "checkout", "-q", "-b", "older", "dev")
    (author / "o.txt").write_text("o\n")
    git(author, "add", "o.txt")
    subprocess.run(  # the listing orders by committer date; make this one old
        ["git", "commit", "-q", "-m", "older work"], cwd=author, check=True,
        env={**os.environ, "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z"},
    )
    git(author, "push", "-q", "origin", "older")
    git(author, "checkout", "-q", "-b", "done", "dev")
    commit_file(author, "d.txt", "d\n", "done work")
    _prepared(author, None)
    t = _transcript(tmp_path, author)
    assert run(monkeypatch, capsys, author, "commit", "--email", "a@example.com", "--level", "standard",
               env={"GIT_SIGNOFF_TRANSCRIPT_FILE": str(t)})[0] == 0
    git(author, "push", "-q", "origin", "done")
    code, data, err = run_json(monkeypatch, capsys, reviewer, "targets")
    assert code == 0, err
    names = [c["branch"] for c in data["candidates"]]
    assert names == ["feature", "older"], names  # merged excluded, attested excluded, dev excluded, recency order
    assert data["base"] == "origin/dev" and data["integration_branch"] == "dev"
    assert data["skipped"] == {"integration": 1, "merged": 1, "attested": 1}
    assert data["candidates"][0]["ahead"] == 2 and data["candidates"][0]["date"]
    code, out, _ = run(monkeypatch, capsys, reviewer, "targets")
    assert "feature" in out and "older" in out and "prepare --target" in out
    code, data, _ = run_json(monkeypatch, capsys, reviewer, "targets", "--limit", "1")
    assert [c["branch"] for c in data["candidates"]] == ["feature"] and data["truncated"] and data["total"] == 2
    code, data, _ = run_json(monkeypatch, capsys, reviewer, "targets", "--all")
    assert data["total"] == 2 and not data["truncated"]


def test_targets_empty_list_says_why(lab, monkeypatch, capsys):
    origin, author, reviewer = lab
    git(author, "checkout", "-q", "dev")
    git(author, "merge", "-q", "--ff-only", "feature")
    git(author, "push", "-q", "origin", "dev")
    code, out, _ = run(monkeypatch, capsys, reviewer, "targets")
    assert code == 0 and "no branches awaiting review" in out and "merged (1)" in out


def test_targets_requires_a_base(scratch_repo, monkeypatch, capsys):
    git(scratch_repo, "remote", "add", "origin", str(scratch_repo))  # a remote with no default branch and no config
    code, _, err = run(monkeypatch, capsys, scratch_repo, "targets")
    assert code == 2 and "no base to list against" in err
    code, data, err = run_json(monkeypatch, capsys, scratch_repo, "targets", "--reference", "main")
    assert code == 0, err
    assert data["base"] == "main" and data["base_source"] == "reference"
