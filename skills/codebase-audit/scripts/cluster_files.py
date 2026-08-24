#!/usr/bin/env python3
"""Deterministic Codebase Clustering Engine for Multi-Agent Adversarial Audits.

Partitions git diffs or entire repositories into orthogonal functional clusters
with associated test targets and volume metrics.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
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


def run_git(args: List[str], cwd: str = ".") -> Tuple[int, str]:
    """Execute a git command and return (returncode, stdout)."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode, res.stdout.strip()
    except Exception as e:
        return 1, str(e)


def resolve_git_base_ref(base_ref: Optional[str] = None, cwd: str = ".") -> str:
    """Resolve a valid git base ref using a robust fallback cascade."""
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

    for cand in candidates:
        code, _ = run_git(["rev-parse", "--verify", cand], cwd=cwd)
        if code == 0:
            return cand

    return "HEAD~1"


def count_file_lines(file_path: Path) -> int:
    """Count lines in a file safely."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def discover_associated_tests(repo_path: str, source_files: List[str]) -> List[str]:
    """Match test files associated with a given list of source files."""
    repo_root = Path(repo_path).resolve()
    tests_dir = repo_root / "tests"
    if not tests_dir.exists() or not tests_dir.is_dir():
        return []

    discovered: Set[str] = set()

    source_stems = set()
    source_parent_dirs = set()
    for sf in source_files:
        p = Path(sf)
        source_stems.add(p.stem.lower())
        if len(p.parts) > 1:
            source_parent_dirs.add(p.parts[-2].lower())

    for root, dirs, files in os.walk(tests_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if not f.endswith(".py"):
                continue
            test_path = Path(root) / f
            rel_test = str(test_path.relative_to(repo_root))
            f_stem = test_path.stem.lower()

            if any(stem in f_stem for stem in source_stems):
                discovered.add(rel_test)
            elif any(pdir in f_stem or pdir in str(test_path).lower() for pdir in source_parent_dirs):
                discovered.add(rel_test)

    return sorted(discovered)


def get_domain_key(rel_path: str) -> str:
    """Determine top-level domain key for clustering."""
    parts = Path(rel_path).parts
    if len(parts) >= 2 and parts[0] in ("src", "lib", "app", "pkg"):
        return parts[1]
    if len(parts) >= 2:
        return parts[0]
    return "root"


def _consolidate_clusters(
    domain_buckets: Dict[str, List[Tuple[str, int]]],
    monolithic_clusters: List[Dict[str, Any]],
    repo_root: Path,
    max_clusters: int = 5,
) -> List[Dict[str, Any]]:
    """Merge domain buckets into at most max_clusters clusters while preserving distinct domains."""
    clusters: List[Dict[str, Any]] = list(monolithic_clusters)
    available_cluster_slots = max(1, max_clusters - len(monolithic_clusters))

    # Sort domains by line count descending
    sorted_domains = sorted(
        domain_buckets.items(),
        key=lambda item: sum(lines for _, lines in item[1]),
        reverse=True,
    )

    primary_domains = sorted_domains[:available_cluster_slots]
    overflow_domains = sorted_domains[available_cluster_slots:]

    # Check if small domains (<20 lines) should be merged into shared_utils if there are multiple domains
    kept_domains = []
    merged_files: List[Tuple[str, int]] = []

    for domain, file_entries in primary_domains:
        domain_lines = sum(lines for _, lines in file_entries)
        if domain_lines < 20 and len(primary_domains) > 1:
            merged_files.extend(file_entries)
        else:
            kept_domains.append((domain, file_entries))

    for _, file_entries in overflow_domains:
        merged_files.extend(file_entries)

    for domain, file_entries in kept_domains:
        files_list = [f for f, _ in file_entries]
        total_domain_lines = sum(lines for _, lines in file_entries)
        tests = discover_associated_tests(str(repo_root), files_list)
        clusters.append({
            "id": f"cluster_{domain.replace('/', '_')}",
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
        clusters.append({
            "id": "cluster_shared_utils",
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
    domain_buckets: Dict[str, List[Tuple[str, int]]] = collections.defaultdict(list)
    monolithic_clusters: List[Dict[str, Any]] = []

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        if "tests" in Path(root).relative_to(repo_root).parts:
            continue

        for f in files:
            p = Path(root) / f
            if p.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            rel_path = str(p.relative_to(repo_root))
            lines = count_file_lines(p)

            if lines >= max_lines:
                tests = discover_associated_tests(str(repo_root), [rel_path])
                monolithic_clusters.append({
                    "id": f"cluster_mono_{Path(rel_path).stem}",
                    "name": f"Monolithic File: {Path(rel_path).name}",
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
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Cluster modified files from git diff between base_ref and head_ref."""
    repo_root = Path(repo_path).resolve()
    code, output = run_git(["diff", "--numstat", f"{base_ref}...{head_ref}"], cwd=str(repo_root))
    if code != 0 or not output:
        code, output = run_git(["diff", "--numstat", f"{base_ref}..{head_ref}"], cwd=str(repo_root))

    if not output:
        return [], 0, 0

    domain_buckets: Dict[str, List[Tuple[str, int]]] = collections.defaultdict(list)
    monolithic_clusters: List[Dict[str, Any]] = []
    total_diff_lines = 0
    total_files = 0

    for line in output.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_str, del_str, rel_path = parts[0], parts[1], parts[2]
        if add_str == "-" or del_str == "-":
            continue

        added = int(add_str) if add_str.isdigit() else 0
        deleted = int(del_str) if del_str.isdigit() else 0
        file_diff_lines = added + deleted

        if rel_path.startswith("tests/"):
            continue

        total_diff_lines += file_diff_lines
        total_files += 1

        if file_diff_lines >= max_lines:
            tests = discover_associated_tests(str(repo_root), [rel_path])
            monolithic_clusters.append({
                "id": f"cluster_mono_{Path(rel_path).stem}",
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
    return clusters, total_diff_lines, total_files


def format_cluster_payload(
    clusters: List[Dict[str, Any]],
    total_lines: int,
    total_files: int,
    base_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Format clusters into standard JSON output schema."""
    is_small = total_lines < 300 and total_files <= 3
    return {
        "base_ref": base_ref,
        "total_files": total_files,
        "total_lines": total_lines,
        "is_small_diff": is_small,
        "recommended_mode": "single-agent-adversarial-review" if is_small else "multi-agent-audit",
        "clusters": clusters,
    }


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Codebase Clustering Engine for Multi-Agent Adversarial Audits.")
    parser.add_argument("--repo", type=str, default=None, help="Directory path for whole-repo sweep.")
    parser.add_argument("--diff", type=str, nargs="?", const="AUTO", default=None, help="Base git ref to diff against.")
    parser.add_argument("--max-clusters", type=int, default=5, help="Maximum number of clusters.")
    parser.add_argument("--max-lines", type=int, default=3000, help="Maximum lines per cluster before splitting.")

    args = parser.parse_args()

    if args.repo:
        repo_path = os.path.abspath(args.repo)
        clusters = cluster_repo(repo_path, max_clusters=args.max_clusters, max_lines=args.max_lines)
        total_lines = sum(c["total_lines"] for c in clusters)
        total_files = sum(len(c["files"]) for c in clusters)
        payload = format_cluster_payload(clusters, total_lines=total_lines, total_files=total_files)
        print(json.dumps(payload, indent=2))
        return

    cwd = os.getcwd()
    base_ref_arg = None if args.diff == "AUTO" else args.diff
    base_ref = resolve_git_base_ref(base_ref_arg, cwd=cwd)
    clusters, total_lines, total_files = cluster_diff(
        base_ref=base_ref,
        head_ref="HEAD",
        repo_path=cwd,
        max_clusters=args.max_clusters,
        max_lines=args.max_lines,
    )
    payload = format_cluster_payload(clusters, total_lines=total_lines, total_files=total_files, base_ref=base_ref)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
