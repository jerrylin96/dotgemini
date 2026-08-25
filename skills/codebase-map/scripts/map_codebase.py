#!/usr/bin/env python3
"""Multi-Agent Codebase Discovery and Mapping Engine.

Partitions unfamiliar codebases into orthogonal functional clusters, detects polyglot
entrypoints across web, CLI, workers, and services, and supports natural-language
intent scoping with dependency expansion.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Import shared clustering utilities from codebase-audit
AUDIT_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../codebase-audit/scripts"))
if AUDIT_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, AUDIT_SCRIPT_DIR)

try:
    from cluster_files import (
        EXCLUDE_DIRS,
        TEXT_EXTENSIONS,
        cluster_repo,
        count_file_lines,
        get_domain_key,
        is_reviewable_source,
        sanitize_id,
    )
except ImportError:
    # Standalone fallback if cluster_files is not on path
    EXCLUDE_DIRS = {
        ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
        "node_modules", "venv", ".venv", "dist", "build", ".eggs",
    }
    TEXT_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
        ".rs", ".go", ".rb", ".php", ".sh", ".bash", ".zsh", ".md", ".tex", ".json",
        ".yaml", ".yml", ".toml", ".sql", ".html", ".css", ".scss"
    }

    def count_file_lines(file_path: Path) -> int:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def is_reviewable_source(rel_path: str) -> bool:
        p = Path(rel_path)
        for part in p.parts:
            if part in EXCLUDE_DIRS or part.startswith("."):
                return False
        return p.suffix.lower() in TEXT_EXTENSIONS

    def get_domain_key(rel_path: str) -> str:
        parts = Path(rel_path).parts
        if not parts:
            return "root"
        if parts[0].lower() in ("src", "lib", "app", "pkg") and len(parts) > 1:
            return parts[1]
        return parts[0]

    def sanitize_id(val: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", val).strip("_").lower()

    def cluster_repo(repo_path: str, max_clusters: int = 5, max_lines: int = 3000) -> List[Dict[str, Any]]:
        repo_root = Path(repo_path).resolve()
        domain_buckets: Dict[str, List[Tuple[str, int]]] = collections.defaultdict(list)
        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for f in files:
                p = Path(root) / f
                rel = str(p.relative_to(repo_root))
                if is_reviewable_source(rel):
                    lines = count_file_lines(p)
                    domain = get_domain_key(rel)
                    domain_buckets[domain].append((rel, lines))
        clusters = []
        for domain, items in domain_buckets.items():
            clusters.append({
                "id": f"cluster_{sanitize_id(domain)}",
                "name": domain.capitalize(),
                "domain": domain,
                "files": [f for f, _ in items],
                "total_lines": sum(num_lines for _, num_lines in items),
                "is_monolithic": False,
                "tests": [],
            })
        return clusters


# Polyglot Entrypoint Heuristics
PYTHON_CLI_PATTERNS = [
    re.compile(r"argparse\.ArgumentParser"),
    re.compile(r"@click\.command"),
    re.compile(r"@click\.group"),
    re.compile(r"@app\.command"),
    re.compile(r"typer\.Typer"),
    re.compile(r"fire\.Fire"),
]

PYTHON_WEB_PATTERNS = [
    re.compile(r"FastAPI\s*\("),
    re.compile(r"Flask\s*\("),
    re.compile(r"@(?:app|router)\.(?:get|post|put|delete|patch|options)\s*\("),
    re.compile(r"urlpatterns\s*="),
]

PYTHON_WORKER_PATTERNS = [
    re.compile(r"@(?:celery_app|celery|app)\.task"),
    re.compile(r"@beam\.ptransform"),
    re.compile(r"DAG\s*\("),
]

PYTHON_MAIN_PATTERN = re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:")


def detect_polyglot_entrypoints(repo_root: Path, file_paths: List[str]) -> List[Dict[str, Any]]:
    """Scan candidate files for polyglot entrypoints (CLI, Web/API, Workers, Executable mains)."""
    entrypoints: List[Dict[str, Any]] = []

    for rel_path in file_paths:
        p = repo_root / rel_path
        if not p.is_file():
            continue

        suffix = p.suffix.lower()
        name = p.name.lower()

        # 1. Python Entrypoints
        if suffix == ".py":
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for pat in PYTHON_CLI_PATTERNS:
                if pat.search(content):
                    entrypoints.append({
                        "path": rel_path,
                        "type": "python_cli",
                        "framework": pat.pattern,
                        "description": f"CLI Entrypoint detected in {p.name}",
                    })
                    break

            for pat in PYTHON_WEB_PATTERNS:
                if pat.search(content):
                    entrypoints.append({
                        "path": rel_path,
                        "type": "web_route",
                        "framework": "Web/API Framework",
                        "description": f"HTTP API Route/App in {p.name}",
                    })
                    break

            for pat in PYTHON_WORKER_PATTERNS:
                if pat.search(content):
                    entrypoints.append({
                        "path": rel_path,
                        "type": "worker_task",
                        "framework": "Celery/Beam/Airflow Worker",
                        "description": f"Background Worker Task in {p.name}",
                    })
                    break

            if PYTHON_MAIN_PATTERN.search(content) and not any(e["path"] == rel_path for e in entrypoints):
                entrypoints.append({
                    "path": rel_path,
                    "type": "python_main",
                    "framework": "__main__ guard",
                    "description": f"Executable Python Script {p.name}",
                })

        # 2. JavaScript / TypeScript Entrypoints
        elif suffix in (".js", ".ts", ".jsx", ".tsx"):
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            if "express(" in content or "fastify(" in content or "createServer(" in content:
                entrypoints.append({
                    "path": rel_path,
                    "type": "web_route",
                    "framework": "Node.js Server",
                    "description": f"Node HTTP Server in {p.name}",
                })
            elif "export async function GET" in content or "export async function POST" in content or name in ("route.ts", "route.js"):
                entrypoints.append({
                    "path": rel_path,
                    "type": "web_route",
                    "framework": "Next.js / Web Route",
                    "description": f"API Handler in {p.name}",
                })

        elif name == "package.json":
            try:
                pkg_data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                if "bin" in pkg_data:
                    entrypoints.append({
                        "path": rel_path,
                        "type": "js_cli",
                        "framework": "npm bin",
                        "description": f"Node CLI Binary definition in {p.name}",
                    })
            except Exception:
                pass

        # 3. Go Entrypoints
        elif suffix == ".go":
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            if "package main" in content and "func main()" in content:
                entrypoints.append({
                    "path": rel_path,
                    "type": "go_main",
                    "framework": "Go Executable",
                    "description": f"Go main executable in {rel_path}",
                })
            elif "http.HandleFunc" in content or "gin.Default" in content or "fiber.New" in content:
                entrypoints.append({
                    "path": rel_path,
                    "type": "web_route",
                    "framework": "Go HTTP Router",
                    "description": f"Go HTTP routing in {rel_path}",
                })

        # 4. Rust Entrypoints
        elif suffix == ".rs":
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            if "fn main()" in content:
                entrypoints.append({
                    "path": rel_path,
                    "type": "rust_main",
                    "framework": "Rust Binary",
                    "description": f"Rust main binary in {rel_path}",
                })

    return entrypoints


def extract_internal_imports(file_path: Path, repo_root: Path) -> Set[str]:
    """Extract direct internal imports referenced inside a Python or JS/TS file."""
    referenced_files: Set[str] = set()
    suffix = file_path.suffix.lower()

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return referenced_files

    if suffix == ".py":
        # Match 'from foo.bar import baz' or 'import foo.bar'
        py_import_patterns = [
            re.compile(r"^\s*from\s+([a-zA-Z0-9_\.]+)\s+import", re.MULTILINE),
            re.compile(r"^\s*import\s+([a-zA-Z0-9_\.]+)", re.MULTILINE),
        ]
        for pat in py_import_patterns:
            for match in pat.finditer(content):
                module_path = match.group(1)
                # Convert module path to relative file path candidates
                rel_candidate_py = module_path.replace(".", "/") + ".py"
                rel_candidate_init = module_path.replace(".", "/") + "/__init__.py"

                for candidate in (rel_candidate_py, rel_candidate_init):
                    if (repo_root / candidate).is_file():
                        referenced_files.add(candidate)
                    # Check if candidate exists relative to file's directory
                    file_dir = file_path.parent
                    rel_to_dir = (file_dir / candidate).resolve()
                    if rel_to_dir.is_file() and rel_to_dir.is_relative_to(repo_root):
                        referenced_files.add(str(rel_to_dir.relative_to(repo_root)))

    elif suffix in (".js", ".ts", ".jsx", ".tsx"):
        js_import_patterns = [
            re.compile(r"import\s+.*?\s+from\s+['\"](\./[^\'\"]+|\.\./[^\'\"]+)['\"]"),
            re.compile(r"require\(['\"](\./[^\'\"]+|\.\./[^\'\"]+)['\"]\)"),
        ]
        for pat in js_import_patterns:
            for match in pat.finditer(content):
                raw_rel = match.group(1)
                resolved = (file_path.parent / raw_rel).resolve()
                for ext in ("", ".ts", ".js", ".tsx", ".jsx", "/index.ts", "/index.js"):
                    cand = Path(str(resolved) + ext)
                    if cand.is_file() and cand.is_relative_to(repo_root):
                        referenced_files.add(str(cand.relative_to(repo_root)))
                        break

    return referenced_files


def filter_files_by_goal(repo_root: Path, all_files: List[str], goal: str) -> List[str]:
    """Filter and expand files based on natural language intent keywords and direct imports."""
    keywords = [w.lower() for w in re.findall(r"[a-zA-Z0-9_]{3,}", goal) if w.lower() not in (
        "how", "the", "and", "for", "with", "what", "where", "from", "does", "want", "work", "works"
    )]
    if not keywords:
        return all_files

    matched_files: Set[str] = set()

    for rel_path in all_files:
        p = repo_root / rel_path
        # Check path name match
        path_lower = rel_path.lower()
        if any(kw in path_lower for kw in keywords):
            matched_files.add(rel_path)
            continue

        # Check content match
        try:
            content = p.read_text(encoding="utf-8", errors="replace").lower()
            if any(kw in content for kw in keywords):
                matched_files.add(rel_path)
        except Exception:
            continue

    if not matched_files:
        return all_files

    # Expand direct 1-hop imports for all matched files
    expanded_files = set(matched_files)
    for rel_path in matched_files:
        p = repo_root / rel_path
        imports = extract_internal_imports(p, repo_root)
        for imp in imports:
            if imp in all_files or (repo_root / imp).is_file():
                expanded_files.add(imp)

    return sorted(expanded_files)


def map_repository(
    repo_path: str,
    scope: Optional[str] = None,
    goal: Optional[str] = None,
    max_clusters: int = 5,
    max_lines: int = 3000,
) -> Dict[str, Any]:
    """Partition codebase, detect entrypoints, and discover architecture."""
    repo_root = Path(repo_path).resolve()

    # Discover all reviewable source files
    all_source_files: List[str] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in files:
            p = Path(root) / f
            rel = str(p.relative_to(repo_root))
            if is_reviewable_source(rel):
                all_source_files.append(rel)

    # Path scoping
    if scope:
        clean_scope = scope.strip("/").lower()
        all_source_files = [f for f in all_source_files if f.lower().startswith(clean_scope) or clean_scope in f.lower()]

    # Goal scoping
    if goal:
        all_source_files = filter_files_by_goal(repo_root, all_source_files, goal)

    total_files = len(all_source_files)
    total_lines = sum(count_file_lines(repo_root / f) for f in all_source_files)

    # Empty repo handling
    if total_files == 0:
        return {
            "total_files": 0,
            "total_lines": 0,
            "clusters": [],
            "entrypoints": [],
            "is_small_repo": True,
            "architecture_mode": "empty",
            "scope": scope,
            "goal": goal,
        }

    # Detect polyglot entrypoints
    entrypoints = detect_polyglot_entrypoints(repo_root, all_source_files)

    # Determine architecture mode (application vs library/SDK)
    if not entrypoints:
        arch_mode = "library_sdk"
        # Extract public package exports if available
        for f in all_source_files:
            if Path(f).name in ("__init__.py", "index.ts", "mod.rs", "lib.go"):
                entrypoints.append({
                    "path": f,
                    "type": "package_export",
                    "framework": "Public Library Interface",
                    "description": f"Public Package Export Interface in {f}",
                })
    else:
        arch_mode = "application_service"

    # Partition files into functional clusters
    domain_buckets: Dict[str, List[str]] = collections.defaultdict(list)
    for rel in all_source_files:
        domain = get_domain_key(rel)
        domain_buckets[domain].append(rel)

    clusters: List[Dict[str, Any]] = []
    for domain, files in sorted(domain_buckets.items()):
        domain_lines = sum(count_file_lines(repo_root / f) for f in files)
        cluster_entrypoints = [ep for ep in entrypoints if ep["path"] in files]
        clusters.append({
            "id": f"cluster_{sanitize_id(domain)}",
            "name": f"{domain.capitalize()} Subsystem",
            "domain": domain,
            "files": sorted(files),
            "total_lines": domain_lines,
            "is_monolithic": any(count_file_lines(repo_root / f) >= max_lines for f in files),
            "entrypoints": cluster_entrypoints,
        })

    is_small = total_lines < 300 and total_files <= 3

    return {
        "repo_path": str(repo_root),
        "scope": scope,
        "goal": goal,
        "architecture_mode": arch_mode,
        "is_small_repo": is_small,
        "total_files": total_files,
        "total_lines": total_lines,
        "clusters": clusters,
        "entrypoints": entrypoints,
    }


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Multi-Agent Codebase Discovery and Mapping Engine.")
    parser.add_argument("--repo", type=str, default=".", help="Directory path of repository to map.")
    parser.add_argument("--scope", type=str, default=None, help="Restrict mapping to a specific directory or path glob.")
    parser.add_argument("--goal", type=str, default=None, help="Plain English intent or feature goal to guide scoped mapping.")
    parser.add_argument("--max-clusters", type=int, default=5, help="Maximum number of clusters.")
    parser.add_argument("--max-lines", type=int, default=3000, help="Monolithic per-file line threshold.")

    args = parser.parse_args()
    repo_path = os.path.abspath(args.repo)

    try:
        payload = map_repository(
            repo_path=repo_path,
            scope=args.scope,
            goal=args.goal,
            max_clusters=args.max_clusters,
            max_lines=args.max_lines,
        )
        print(json.dumps(payload, indent=2))
        sys.exit(0)
    except Exception as e:
        err_payload = {
            "error": str(e),
            "total_files": 0,
            "total_lines": 0,
            "clusters": [],
            "entrypoints": [],
            "is_small_repo": True,
        }
        print(json.dumps(err_payload, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
