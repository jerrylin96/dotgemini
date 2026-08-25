#!/usr/bin/env python3
"""Deterministic Codebase Clustering Engine for Multi-Agent Adversarial Audits.

Partitions git diffs or entire repositories into orthogonal functional clusters
with associated test targets, volume metrics, and robust git error handling.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    ".eggs",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".rs", ".go", ".rb", ".php", ".sh", ".bash", ".zsh", ".md", ".tex", ".json",
    ".yaml", ".yml", ".toml", ".sql", ".html", ".css", ".scss"
}


def run_git(args: List[str], cwd: str = ".") -> Tuple[int, str, str]:
    """Execute a git command and return (returncode, stdout, stderr)."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def get_base_ref_candidates(base_ref: Optional[str] = None) -> List[str]:
    """Get list of base ref candidates in priority order."""
    candidates: List[str] = []
    if base_ref:
        candidates.extend([f"origin/{base_ref}", base_ref])

    candidates.extend([
        "origin/main",
        "main",
        "origin/master",
        "master",
        "HEAD~1",
    ])
    return candidates


def resolve_git_base_ref(base_ref: Optional[str] = None, cwd: str = ".") -> Optional[str]:
    """Resolve a valid git base ref using a fallback cascade.
    
    Returns None if no candidate resolves cleanly.
    """
    candidates = get_base_ref_candidates(base_ref)
    for cand in candidates:
        code, _, _ = run_git(["rev-parse", "--verify", cand], cwd=cwd)
        if code == 0:
            return cand

    return None


def is_test_path(rel_path: str) -> bool:
    """Check if a path corresponds to a test file or test directory."""
    p = Path(rel_path)
    for part in p.parts:
        if part.lower() in ("tests", "test", "testing"):
            return True
    name = p.name.lower()
    if name.startswith("test_") or name.endswith("_test.py") or name.endswith(".test.js") or name.endswith(".test.ts"):
        return True
    return False


def is_reviewable_source(rel_path: str) -> bool:
    """Determine if a file is a reviewable source file (not a test, binary, or cache)."""
    p = Path(rel_path)
    for part in p.parts:
        if part in EXCLUDE_DIRS or part.startswith("."):
            return False
    if is_test_path(rel_path):
        return False
    return p.suffix.lower() in TEXT_EXTENSIONS


def parse_numstat_path(raw_path: str) -> str:
    """Parse git numstat paths handling rename notations like 'a/{b => c}/d' or 'old => new'."""
    clean_path = raw_path.strip().strip('"')

    # Pattern 1: prefix/{old => new}/suffix
    m = re.search(r"^(.*?)\{(?:.*?) => (.*?)\}(.*?)$", clean_path)
    if m:
        prefix, new_mid, suffix = m.group(1), m.group(2), m.group(3)
        return f"{prefix}{new_mid}{suffix}".replace("//", "/").strip('"')

    # Pattern 2: old => new (join all parts after first arrow to preserve any subsequent arrows)
    if " => " in clean_path:
        parts = clean_path.split(" => ", 1)
        return parts[1].strip().strip('"')

    return clean_path


def count_file_lines(file_path: Path) -> int:
    """Count lines in a file safely."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def discover_associated_tests(repo_path: str, source_files: List[str]) -> List[str]:
    """Match test files associated with a given list of source files across root and nested test dirs."""
    repo_root = Path(repo_path).resolve()
    discovered: Set[str] = set()

    source_stems = {Path(sf).stem.lower() for sf in source_files}
    source_parent_dirs = {Path(sf).parts[-2].lower() for sf in source_files if len(Path(sf).parts) > 1}

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in files:
            p = Path(root) / f
            rel_test = str(p.relative_to(repo_root))
            if not is_test_path(rel_test) or p.suffix.lower() not in (".py", ".js", ".ts", ".jsx", ".tsx"):
                continue

            f_stem = p.stem.lower()
            matched = False
            for stem in source_stems:
                if f_stem in (f"test_{stem}", f"{stem}_test", stem):
                    discovered.add(rel_test)
                    matched = True
                    break
            if not matched:
                rel_parts = [part.lower() for part in Path(rel_test).parts]
                for pdir in source_parent_dirs:
                    if f_stem in (f"test_{pdir}", f"{pdir}_test", pdir) or pdir in rel_parts:
                        discovered.add(rel_test)
                        break

    return sorted(discovered)


def get_domain_key(rel_path: str) -> str:
    """Determine top-level domain key for clustering."""
    parts = Path(rel_path).parts
    if len(parts) >= 3 and parts[0] in ("src", "lib", "app", "pkg"):
        return parts[1]
    if len(parts) >= 2 and parts[0] in ("src", "lib", "app", "pkg"):
        return parts[0]
    if len(parts) >= 2:
        return parts[0]
    return "root"


def sanitize_id(raw_str: str) -> str:
    """Sanitize string to valid identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw_str).strip("_")


def _consolidate_clusters(
    domain_buckets: Dict[str, List[Tuple[str, int]]],
    monolithic_clusters: List[Dict[str, Any]],
    repo_root: Path,
    max_clusters: int = 5,
) -> List[Dict[str, Any]]:
    """Consolidate domain buckets into clusters, respecting max_clusters budget."""
    clusters: List[Dict[str, Any]] = list(monolithic_clusters)
    used_ids: Set[str] = {c["id"] for c in clusters}

    num_mono = len(monolithic_clusters)
    available_slots = max(0, max_clusters - num_mono)

    sorted_domains = sorted(
        domain_buckets.items(),
        key=lambda item: sum(lines for _, lines in item[1]),
        reverse=True,
    )

    if not sorted_domains:
        return clusters

    # If monolithic files already exhaust the budget, merge all remaining non-monolithic files into shared_utils
    if available_slots == 0:
        all_remaining_files: List[Tuple[str, int]] = []
        for _, file_entries in sorted_domains:
            all_remaining_files.extend(file_entries)

        if all_remaining_files:
            files_list = [f for f, _ in all_remaining_files]
            total_small_lines = sum(lines for _, lines in all_remaining_files)
            tests = discover_associated_tests(str(repo_root), files_list)
            base_id = "cluster_shared_utils"
            cluster_id = base_id
            counter = 1
            while cluster_id in used_ids:
                cluster_id = f"{base_id}_{counter}"
                counter += 1
            used_ids.add(cluster_id)

            clusters.append({
                "id": cluster_id,
                "name": "Domain: Utilities & Shared",
                "domain": "shared_utils",
                "files": files_list,
                "total_lines": total_small_lines,
                "is_monolithic": False,
                "tests": tests,
            })
        return clusters

    needs_shared_utils = len(sorted_domains) > available_slots or any(
        sum(lines for _, lines in item[1]) < 20 for item in sorted_domains
    )

    if needs_shared_utils:
        if available_slots == 1:
            primary_slot_count = 0
        else:
            primary_slot_count = available_slots - 1
    else:
        primary_slot_count = min(len(sorted_domains), available_slots)

    primary_domains = sorted_domains[:primary_slot_count]
    overflow_domains = sorted_domains[primary_slot_count:]

    kept_domains = []
    merged_files: List[Tuple[str, int]] = []

    for domain, file_entries in primary_domains:
        domain_lines = sum(lines for _, lines in file_entries)
        if domain_lines < 20 and (len(primary_domains) > 1 or overflow_domains):
            merged_files.extend(file_entries)
        else:
            kept_domains.append((domain, file_entries))

    for _, file_entries in overflow_domains:
        merged_files.extend(file_entries)

    for domain, file_entries in kept_domains:
        files_list = [f for f, _ in file_entries]
        total_domain_lines = sum(lines for _, lines in file_entries)
        tests = discover_associated_tests(str(repo_root), files_list)
        base_id = f"cluster_{sanitize_id(domain)}"
        cluster_id = base_id
        counter = 1
        while cluster_id in used_ids:
            cluster_id = f"{base_id}_{counter}"
            counter += 1
        used_ids.add(cluster_id)

        clusters.append({
            "id": cluster_id,
            "name": f"Domain: {domain.title()}",
            "domain": domain,
            "files": files_list,
            "total_lines": total_domain_lines,
            "is_monolithic": False,
            "tests": tests,
        })

    if merged_files:
        files_list = [f for f, _ in merged_files]
        total_small_lines = sum(lines for _, lines in merged_files)
        tests = discover_associated_tests(str(repo_root), files_list)
        base_id = "cluster_shared_utils"
        cluster_id = base_id
        counter = 1
        while cluster_id in used_ids:
            cluster_id = f"{base_id}_{counter}"
            counter += 1
        used_ids.add(cluster_id)

        clusters.append({
            "id": cluster_id,
            "name": "Domain: Utilities & Shared",
            "domain": "shared_utils",
            "files": files_list,
            "total_lines": total_small_lines,
            "is_monolithic": False,
            "tests": tests,
        })

    return clusters


def cluster_repo(repo_path: str, max_clusters: int = 5, max_lines: int = 3000) -> List[Dict[str, Any]]:
    """Cluster all source files in a repository by domain and volume."""
    repo_root = Path(repo_path).resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise FileNotFoundError(f"Repository directory does not exist: {repo_path}")

    domain_buckets: Dict[str, List[Tuple[str, int]]] = collections.defaultdict(list)
    monolithic_clusters: List[Dict[str, Any]] = []
    used_ids: Set[str] = set()

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

        for f in files:
            p = Path(root) / f
            rel_path = str(p.relative_to(repo_root))
            if not is_reviewable_source(rel_path):
                continue

            lines = count_file_lines(p)

            if lines >= max_lines:
                tests = discover_associated_tests(str(repo_root), [rel_path])
                base_id = f"cluster_mono_{sanitize_id(rel_path)}"
                cluster_id = base_id
                counter = 1
                while cluster_id in used_ids:
                    cluster_id = f"{base_id}_{counter}"
                    counter += 1
                used_ids.add(cluster_id)

                monolithic_clusters.append({
                    "id": cluster_id,
                    "name": f"Monolithic File: {p.name}",
                    "domain": "monolithic",
                    "files": [rel_path],
                    "total_lines": lines,
                    "is_monolithic": True,
                    "tests": tests,
                })
            else:
                domain = get_domain_key(rel_path)
                domain_buckets[domain].append((rel_path, lines))

    return _consolidate_clusters(domain_buckets, monolithic_clusters, repo_root, max_clusters)


def cluster_diff(
    base_ref: str,
    head_ref: str = "HEAD",
    repo_path: str = ".",
    max_clusters: int = 5,
    max_lines: int = 3000,
) -> Tuple[List[Dict[str, Any]], int, int, Optional[str]]:
    """Cluster modified files from git diff between base_ref and head_ref.
    
    Returns (clusters, total_lines, total_files, warning).
    Raises RuntimeError if both three-dot and two-dot diffs fail.
    """
    repo_root = Path(repo_path).resolve()
    warning: Optional[str] = None

    code, output, err = run_git(["diff", "--numstat", f"{base_ref}...{head_ref}"], cwd=str(repo_root))
    if code == 0:
        if not output:
            return [], 0, 0, None
    else:
        # Fallback only when three-dot fails (e.g. shallow clone / no merge base)
        fallback_code, fallback_output, fallback_err = run_git(
            ["diff", "--numstat", f"{base_ref}..{head_ref}"], cwd=str(repo_root)
        )
        if fallback_code == 0:
            warning = "three-dot diff unavailable (shallow history?); used two-dot tree diff"
            output = fallback_output
            if not output:
                return [], 0, 0, warning
        else:
            raise RuntimeError(
                f"Git diff failed for '{base_ref}...{head_ref}' ({err}) and fallback '{base_ref}..{head_ref}' ({fallback_err})"
            )

    domain_buckets: Dict[str, List[Tuple[str, int]]] = collections.defaultdict(list)
    monolithic_clusters: List[Dict[str, Any]] = []
    used_ids: Set[str] = set()
    total_diff_lines = 0
    total_files = 0

    for line in output.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_str, del_str, raw_rel_path = parts[0], parts[1], parts[2]
        if add_str == "-" or del_str == "-":
            continue  # Binary file

        rel_path = parse_numstat_path(raw_rel_path)
        if not is_reviewable_source(rel_path):
            continue

        added = int(add_str) if add_str.isdigit() else 0
        deleted = int(del_str) if del_str.isdigit() else 0
        file_diff_lines = added + deleted

        total_diff_lines += file_diff_lines
        total_files += 1

        if file_diff_lines >= max_lines:
            tests = discover_associated_tests(str(repo_root), [rel_path])
            base_id = f"cluster_mono_{sanitize_id(rel_path)}"
            cluster_id = base_id
            counter = 1
            while cluster_id in used_ids:
                cluster_id = f"{base_id}_{counter}"
                counter += 1
            used_ids.add(cluster_id)

            monolithic_clusters.append({
                "id": cluster_id,
                "name": f"Monolithic Diff: {Path(rel_path).name}",
                "domain": "monolithic",
                "files": [rel_path],
                "total_lines": file_diff_lines,
                "is_monolithic": True,
                "tests": tests,
            })
        else:
            domain = get_domain_key(rel_path)
            domain_buckets[domain].append((rel_path, file_diff_lines))

    clusters = _consolidate_clusters(domain_buckets, monolithic_clusters, repo_root, max_clusters)
    return clusters, total_diff_lines, total_files, warning


def format_cluster_payload(
    clusters: List[Dict[str, Any]],
    total_lines: int,
    total_files: int,
    base_ref: Optional[str] = None,
    is_diff: bool = True,
    warning: Optional[str] = None,
) -> Dict[str, Any]:
    """Format clusters into standard JSON output schema."""
    if is_diff:
        is_small = total_lines < 300 and total_files <= 3
        recommended = "single-agent-adversarial-review" if is_small else "multi-agent-audit"
    else:
        is_small = False
        recommended = "multi-agent-audit"

    payload: Dict[str, Any] = {
        "base_ref": base_ref,
        "total_files": total_files,
        "total_lines": total_lines,
        "is_small_diff": is_small,
        "recommended_mode": recommended,
        "clusters": clusters,
    }
    if warning:
        payload["warning"] = warning

    return payload


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Codebase Clustering Engine for Multi-Agent Adversarial Audits.")
    parser.add_argument("--repo", type=str, default=None, help="Directory path for whole-repo sweep.")
    parser.add_argument("--diff", type=str, nargs="?", const="AUTO", default=None, help="Base git ref to diff against.")
    parser.add_argument("--max-clusters", type=int, default=5, help="Maximum number of clusters.")
    parser.add_argument(
        "--max-lines",
        type=int,
        default=3000,
        help="Per-file line threshold above which a file is isolated into a standalone monolithic cluster (default: 3000).",
    )

    args = parser.parse_args()

    if args.repo:
        repo_path = os.path.abspath(args.repo)
        try:
            clusters = cluster_repo(repo_path, max_clusters=args.max_clusters, max_lines=args.max_lines)
            total_lines = sum(c["total_lines"] for c in clusters)
            total_files = sum(len(c["files"]) for c in clusters)
            payload = format_cluster_payload(clusters, total_lines=total_lines, total_files=total_files, is_diff=False)
            print(json.dumps(payload, indent=2))
            return
        except Exception as e:
            err_payload = {"error": str(e), "is_small_diff": False, "recommended_mode": None, "clusters": []}
            print(json.dumps(err_payload, indent=2), file=sys.stderr)
            sys.exit(1)

    # Diff mode
    cwd = os.getcwd()
    base_ref_arg = None if args.diff == "AUTO" else args.diff
    base_ref = resolve_git_base_ref(base_ref_arg, cwd=cwd)

    if base_ref is None:
        candidates = get_base_ref_candidates(base_ref_arg)
        err_payload = {
            "error": f"Could not resolve a valid git base ref (tried: {', '.join(candidates)}).",
            "is_small_diff": False,
            "recommended_mode": None,
            "clusters": [],
        }
        print(json.dumps(err_payload, indent=2), file=sys.stderr)
        sys.exit(1)

    try:
        clusters, total_lines, total_files, warning = cluster_diff(
            base_ref=base_ref,
            head_ref="HEAD",
            repo_path=cwd,
            max_clusters=args.max_clusters,
            max_lines=args.max_lines,
        )
        payload = format_cluster_payload(
            clusters,
            total_lines=total_lines,
            total_files=total_files,
            base_ref=base_ref,
            is_diff=True,
            warning=warning,
        )
        print(json.dumps(payload, indent=2))
    except Exception as e:
        err_payload = {"error": str(e), "is_small_diff": False, "recommended_mode": None, "clusters": []}
        print(json.dumps(err_payload, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
