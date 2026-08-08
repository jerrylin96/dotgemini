"""Profile resolution + science-signal detection (Phase 3e mirror of SKILL.md §1 step 5)."""

import shutil
import subprocess

import pytest

from signoff_mcp import core, profile
from signoff_mcp.tests.helpers import git

VALID_PROFILE = """# Repo-local profile
<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
### Interview Profile: atmos-column-test
Profile-ID: atmos-column-test

Domain emphases — weight probes within the universal axes:
- **Unit discipline:** hPa vs. Pa on every pressure-level quantity.
<!-- INTERVIEW-PROFILE:END -->
"""


def _write_repo_profile(scratch_repo, content=VALID_PROFILE):
    d = scratch_repo / ".signoff"
    d.mkdir()
    (d / "profile.md").write_text(content, encoding="utf-8")
    return d / "profile.md"


# --- resolve_profile: the three sources -------------------------------------


def test_embedded_default_when_no_file(scratch_repo):
    res = profile.resolve_profile(str(scratch_repo), env={})
    assert res.source == profile.SOURCE_EMBEDDED
    assert res.path is None
    assert res.profile_id == "software-general"
    assert res.digest is None
    assert res.fallback_reason is None


def test_repo_local_profile_resolves_with_digest(scratch_repo):
    path = _write_repo_profile(scratch_repo)
    res = profile.resolve_profile(str(scratch_repo), env={})
    assert res.source == profile.SOURCE_REPO_LOCAL
    assert res.path == str(path)
    assert res.profile_id == "atmos-column-test"
    assert res.fallback_reason is None
    assert res.digest and len(res.digest) == 12
    int(res.digest, 16)  # 12-hex prefix


def test_env_override_takes_precedence(scratch_repo, tmp_path):
    _write_repo_profile(scratch_repo)
    override = tmp_path / "override.md"
    override.write_text(VALID_PROFILE.replace("atmos-column-test", "override-id"), encoding="utf-8")
    res = profile.resolve_profile(str(scratch_repo), env={"SIGNOFF_PROFILE_FILE": str(override)})
    assert res.source == profile.SOURCE_ENV_OVERRIDE
    assert res.path == str(override)
    assert res.profile_id == "override-id"


def test_unreadable_env_override_aborts_not_falls_back(scratch_repo, tmp_path):
    _write_repo_profile(scratch_repo)  # a valid fallback exists — must still abort
    with pytest.raises(profile.ProfileOverrideError, match="Aborting signoff"):
        profile.resolve_profile(
            str(scratch_repo), env={"SIGNOFF_PROFILE_FILE": str(tmp_path / "missing.md")}
        )


# --- malformed profiles fall back, announced --------------------------------


@pytest.mark.parametrize(
    "mangle, reason_match",
    [
        (lambda t: t.replace("INTERVIEW-PROFILE:BEGIN", "BROKEN"), "0 BEGIN"),
        (lambda t: t.replace("INTERVIEW-PROFILE:END", "BROKEN"), "1 BEGIN / 0 END"),
        (lambda t: t + t, "2 BEGIN"),
        (lambda t: t.replace("Profile-ID: atmos-column-test\n", ""), "Profile-ID"),
        (lambda t: t.replace("Profile-ID: atmos-column-test", "Profile-ID: Bad_ID!"), "Profile-ID"),
    ],
)
def test_malformed_repo_profile_falls_back_to_embedded(scratch_repo, mangle, reason_match):
    _write_repo_profile(scratch_repo, mangle(VALID_PROFILE))
    res = profile.resolve_profile(str(scratch_repo), env={})
    assert res.source == profile.SOURCE_EMBEDDED
    assert res.profile_id == "software-general"
    assert res.digest is None
    assert res.fallback_reason and reason_match in res.fallback_reason


# --- digest parity with the SKILL.md sed pipeline ---------------------------


@pytest.mark.skipif(
    not (shutil.which("sed") and shutil.which("sha256sum")),
    reason="sed/sha256sum unavailable",
)
@pytest.mark.parametrize(
    "content",
    [
        VALID_PROFILE,
        VALID_PROFILE.rstrip("\n"),  # no trailing newline
        "no markers at all\n",  # empty sed selection
        VALID_PROFILE.replace("INTERVIEW-PROFILE:END", "NOT-THE-END"),  # unclosed range to EOF
    ],
)
def test_digest_matches_sed_sha256sum_pipeline(tmp_path, content):
    f = tmp_path / "p.md"
    f.write_text(content, encoding="utf-8")
    expected = subprocess.run(
        f"sed -n '/INTERVIEW-PROFILE:BEGIN/,/INTERVIEW-PROFILE:END/p' {f} | sha256sum | cut -c1-12",
        shell=True,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert profile.profile_block_digest(content.encode("utf-8")) == expected


# --- science-signal detection ------------------------------------------------


def _added(*lines):
    return "\n".join(f"+{line}" for line in lines) + "\n"


def test_detects_scientific_imports_and_seeding():
    diff = _added("import numpy as np", "rng = np.random.default_rng(seed=42)")
    assert profile.detect_science_signals(diff) == ["rng-seeding", "scientific-imports"]


def test_detects_notebooks_and_datasets_from_headers():
    diff = "diff --git a/analysis.ipynb b/analysis.ipynb\n--- a/analysis.ipynb\n+++ b/analysis.ipynb\n"
    diff += _added('ds = open_dataset("era5.nc")')
    assert profile.detect_science_signals(diff) == ["datasets-model-config", "notebooks"]


def test_detects_units_and_constants():
    diff = _added("G0 = 9.80665  # m s-2", "p_hpa = levels  # hPa")
    assert "units-or-constants" in profile.detect_science_signals(diff)


def test_ignores_science_terms_on_unchanged_or_removed_lines():
    diff = " import numpy as np\n-rng = np.random.default_rng(seed=1)\n+print('docs')\n"
    assert profile.detect_science_signals(diff) == []


def test_docs_only_diff_has_no_signals():
    diff = _added("# README", "This tool verifies human comprehension before merge.")
    assert profile.detect_science_signals(diff) == []


# --- prepare() integration ----------------------------------------------------


def test_prepare_reports_profile_and_science_signals(scratch_repo):
    _write_repo_profile(scratch_repo)
    (scratch_repo / "ciwv.py").write_text(
        "import numpy as np\nG0 = 9.80665\nrng = np.random.default_rng(seed=7)\n", encoding="utf-8"
    )
    git(scratch_repo, "add", ".")
    git(scratch_repo, "commit", "-q", "-m", "science change")

    state = core.prepare(core.GitRepo(str(scratch_repo)), "HEAD", reference_ref="main")
    assert state.profile_source == profile.SOURCE_REPO_LOCAL
    assert state.profile_id == "atmos-column-test"
    assert state.profile_digest and len(state.profile_digest) == 12
    assert state.profile_fallback_reason is None
    assert set(state.science_signals) >= {"scientific-imports", "rng-seeding", "units-or-constants"}


def test_prepare_defaults_to_embedded_profile(scratch_repo):
    state = core.prepare(core.GitRepo(str(scratch_repo)), "HEAD", reference_ref="main")
    assert state.profile_source == profile.SOURCE_EMBEDDED
    assert state.profile_id == "software-general"
    assert state.profile_digest is None
    assert state.science_signals == []


def test_prepare_aborts_on_unreadable_override(scratch_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNOFF_PROFILE_FILE", str(tmp_path / "missing.md"))
    with pytest.raises(core.SignoffError, match="Aborting signoff"):
        core.prepare(core.GitRepo(str(scratch_repo)), "HEAD", reference_ref="main")
