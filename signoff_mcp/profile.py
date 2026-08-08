"""Interview-profile resolution and science-signal detection (spec §4.1, Phase 3e).

Deterministic server-side mirror of skills/signoff/SKILL.md Section 1 step 5
(profile resolution: SIGNOFF_PROFILE_FILE env override → <repo>/.signoff/profile.md
→ embedded default) and the science-detection escalation guard. Informative
only: the skill layer remains authoritative for interview conduct; these
results let signoff_prepare report which question set will run, its
provenance digest, and the science signals present in the range diff.

Pure stdlib, no MCP dependency.
"""

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Mapping

PROFILE_ENV_VAR = "SIGNOFF_PROFILE_FILE"
REPO_PROFILE_RELPATH = os.path.join(".signoff", "profile.md")
EMBEDDED_PROFILE_ID = "software-general"

SOURCE_ENV_OVERRIDE = "env-override"
SOURCE_REPO_LOCAL = "repo-local"
SOURCE_EMBEDDED = "embedded-default"

_BEGIN_MARKER = b"INTERVIEW-PROFILE:BEGIN"
_END_MARKER = b"INTERVIEW-PROFILE:END"
_PROFILE_ID_RE = re.compile(rb"^Profile-ID:[ \t]*([a-z0-9-]+)[ \t]*$", re.MULTILINE)


class ProfileOverrideError(Exception):
    """SIGNOFF_PROFILE_FILE is set but unreadable — abort, never fall back (SKILL.md §1.5)."""


@dataclass
class ProfileResolution:
    """Outcome of profile resolution.

    ``digest`` is the 12-hex prefix the skill layer writes as
    ``/sha256:<digest>`` in the ``interview=`` token ($PROFILE_DIGEST); it is
    None exactly when the embedded default is active, matching GSA §2.3.
    ``fallback_reason`` is set only when a file-sourced profile was malformed
    and therefore announced-and-ignored in favor of the embedded default.
    """

    source: str
    path: str | None
    profile_id: str
    digest: str | None
    fallback_reason: str | None = None


def profile_block_digest(data: bytes) -> str:
    """12-hex digest prefix of the delimited profile block.

    Byte-equivalent to the SKILL.md pipeline
    ``sed -n '/INTERVIEW-PROFILE:BEGIN/,/INTERVIEW-PROFILE:END/p' | sha256sum | cut -c1-12``,
    including sed's range semantics (the end pattern is not tested on the
    line that opened the range, and an unclosed range runs to EOF).
    """
    selected = []
    in_range = False
    for line in data.splitlines(keepends=True):
        if in_range:
            selected.append(line)
            if _END_MARKER in line:
                in_range = False
        elif _BEGIN_MARKER in line:
            selected.append(line)
            in_range = True
    return hashlib.sha256(b"".join(selected)).hexdigest()[:12]


def _validate_profile(data: bytes) -> tuple[str | None, str | None]:
    """Return (profile_id, None) for a valid file-sourced profile, else (None, reason)."""
    begins = data.count(_BEGIN_MARKER)
    ends = data.count(_END_MARKER)
    if begins != 1 or ends != 1:
        return None, (
            f"expected exactly one delimited INTERVIEW-PROFILE block, "
            f"found {begins} BEGIN / {ends} END marker(s)"
        )
    start = data.index(_BEGIN_MARKER)
    end = data.index(_END_MARKER)
    if end < start:
        return None, "INTERVIEW-PROFILE:END marker precedes BEGIN marker"
    m = _PROFILE_ID_RE.search(data, start, end)
    if not m:
        return None, "missing or malformed Profile-ID line inside the profile block"
    return m.group(1).decode("ascii"), None


def _embedded(fallback_reason: str | None = None) -> ProfileResolution:
    return ProfileResolution(
        source=SOURCE_EMBEDDED,
        path=None,
        profile_id=EMBEDDED_PROFILE_ID,
        digest=None,
        fallback_reason=fallback_reason,
    )


def _resolve_file(path: str, source: str) -> ProfileResolution:
    with open(path, "rb") as f:
        data = f.read()
    profile_id, reason = _validate_profile(data)
    if profile_id is None:
        return _embedded(f"malformed profile at {path} ({reason}); using embedded default")
    return ProfileResolution(
        source=source,
        path=path,
        profile_id=profile_id,
        digest=profile_block_digest(data),
    )


def resolve_profile(repo_root: str, env: Mapping[str, str] | None = None) -> ProfileResolution:
    """Resolve the active interview profile for a target repository.

    Resolution order mirrors SKILL.md Section 1 step 5: SIGNOFF_PROFILE_FILE
    env override (unreadable → ProfileOverrideError, never a fallback) →
    <repo_root>/.signoff/profile.md → embedded default. A malformed
    file-sourced profile falls back to the embedded default with
    ``fallback_reason`` set, so callers can announce it.
    """
    environ = os.environ if env is None else env
    override = (environ.get(PROFILE_ENV_VAR) or "").strip()
    if override:
        expanded = os.path.expanduser(override)
        if not (os.path.isfile(expanded) and os.access(expanded, os.R_OK)):
            raise ProfileOverrideError(
                f"{PROFILE_ENV_VAR} is set but unreadable: {override}. Aborting signoff."
            )
        return _resolve_file(expanded, SOURCE_ENV_OVERRIDE)

    repo_local = os.path.join(repo_root, REPO_PROFILE_RELPATH)
    if os.path.isfile(repo_local) and os.access(repo_local, os.R_OK):
        return _resolve_file(repo_local, SOURCE_REPO_LOCAL)

    return _embedded()


# Science-detection signal categories, mirroring the SKILL.md guard list:
# scientific-stack imports, notebooks, RNG seeding, physical constants or
# unit-bearing quantities, numerical solvers/integrators, dataset/model-config
# files. Content signals only match added (+) diff lines; file signals also
# match diff headers, so renames and deletions of e.g. notebooks still count.
SCIENCE_SIGNAL_PATTERNS: dict[str, re.Pattern] = {
    "scientific-imports": re.compile(
        r"^\+\s*(?:import|from)\s+(?:numpy|scipy|jax|torch|astropy|pandas|xarray)\b", re.MULTILINE
    ),
    "notebooks": re.compile(r"^(?:diff --git|\+\+\+|---) .*\.ipynb\b", re.MULTILINE),
    "rng-seeding": re.compile(
        r"^\+.*(?:\bseed\s*=|\.seed\(|default_rng|random_state\s*=|manual_seed)", re.MULTILINE
    ),
    "units-or-constants": re.compile(
        r"^\+.*(?:\bhPa\b|\bkPa\b|\bkg/kg\b|\bkg[ /]?m(?:\^?-?[23]|²|³)?\b|\bm\s?s\^?-2\b|\bW[ /]?m-?2\b"
        r"|9\.80665|6\.674\d*e-11|1\.380649e-23|6\.02214)",
        re.MULTILINE,
    ),
    "solvers-integrators": re.compile(
        r"^\+.*(?:solve_ivp|odeint|scipy\.integrate|np\.linalg|scipy\.linalg|trapezoid\(|cumulative_trapezoid"
        r"|runge.?kutta|newton_krylov)",
        re.MULTILINE | re.IGNORECASE,
    ),
    "datasets-model-config": re.compile(
        r"^(?:diff --git|\+\+\+|---|\+).*(?:\.nc4?\b|netcdf|\.grib2?\b|\.zarr\b|to_zarr|open_zarr)",
        re.MULTILINE | re.IGNORECASE,
    ),
}


def detect_science_signals(diff: str) -> list[str]:
    """Names of science-guard signal categories present in a range diff, sorted."""
    return sorted(name for name, pattern in SCIENCE_SIGNAL_PATTERNS.items() if pattern.search(diff))
