#!/usr/bin/env python3
"""Multi-Agent Codebase Discovery and Mapping Engine.

Partitions unfamiliar codebases into orthogonal functional clusters, detects polyglot
entrypoints across web, CLI, workers, and services, and supports natural-language
intent scoping with dependency expansion.
"""

from __future__ import annotations

import argparse
import collections
import fnmatch
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

def _embedded_get_domain_key(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) >= 3 and parts[0] in ("src", "lib", "app", "pkg"):
        return parts[1]
    if len(parts) >= 2 and parts[0] in ("src", "lib", "app", "pkg"):
        return parts[0]
    if len(parts) >= 2:
        return parts[0]
    return "root"


def _embedded_sanitize_id(raw_str: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw_str).strip("_")


def _embedded_cluster_file_list(
    repo_root: Path,
    file_entries: List[Tuple[str, int]],
    max_clusters: int = 5,
    max_lines: int = 3000,
) -> List[Dict[str, Any]]:
    """Standalone fallback implementation of cluster_file_list when codebase-audit is not available."""
    if max_clusters < 1:
        raise ValueError(f"max_clusters must be >= 1, got {max_clusters}")
    domain_buckets: Dict[str, List[Tuple[str, int]]] = collections.defaultdict(list)
    for rel, lines in file_entries:
        domain = _embedded_get_domain_key(rel)
        domain_buckets[domain].append((rel, lines))
    sorted_domains = sorted(domain_buckets.items(), key=lambda it: sum(num_lines for _, num_lines in it[1]), reverse=True)
    if max_clusters == 1 or len(sorted_domains) > max_clusters:
        primary = dict(sorted_domains[: max(0, max_clusters - 1)])
        overflow = [item for _, items in sorted_domains[max(0, max_clusters - 1):] for item in items]
        if overflow:
            if "shared_utils" in primary:
                primary["shared_utils"].extend(overflow)
            else:
                primary["shared_utils"] = overflow
        domain_buckets = primary
    clusters = []
    for domain, items in domain_buckets.items():
        clusters.append({
            "id": f"cluster_{_embedded_sanitize_id(domain)}",
            "name": f"Domain: {domain.title()}",
            "domain": domain,
            "files": sorted(f for f, _ in items),
            "total_lines": sum(num_lines for _, num_lines in items),
            "is_monolithic": False,
            "tests": [],
        })
    return clusters


# Import shared clustering utilities from codebase-audit
AUDIT_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../codebase-audit/scripts"))
if AUDIT_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, AUDIT_SCRIPT_DIR)

try:
    from cluster_files import (
        EXCLUDE_DIRS,
        TEXT_EXTENSIONS,
        cluster_file_list,
        count_file_lines,
        get_domain_key,
        is_reviewable_source,
        is_test_path,
        sanitize_id,
    )
except ImportError:
    print("WARNING: codebase-audit utilities unavailable; using embedded fallback with reduced semantics", file=sys.stderr)
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

    def is_test_path(rel_path: str) -> bool:
        p = Path(rel_path)
        for part in p.parts:
            if part.lower() in ("tests", "test", "testing"):
                return True
        name = p.name.lower()
        if name.startswith("test_") or name.endswith("_test.py") or name.endswith(".test.js") or name.endswith(".test.ts"):
            return True
        return False

    def is_reviewable_source(rel_path: str) -> bool:
        p = Path(rel_path)
        for part in p.parts:
            if part in EXCLUDE_DIRS or part.startswith("."):
                return False
        if is_test_path(rel_path):
            return False
        return p.suffix.lower() in TEXT_EXTENSIONS

    get_domain_key = _embedded_get_domain_key
    sanitize_id = _embedded_sanitize_id
    cluster_file_list = _embedded_cluster_file_list


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

STOPWORDS = {
    "how", "the", "and", "for", "with", "what", "where", "from", "does", "want",
    "work", "works", "add", "new", "need", "help", "explain", "get", "use", "using",
    "way", "ways", "stuff", "thing", "things", "code", "change", "changes", "make",
    "working", "look", "looks", "into", "that", "this", "our", "about", "your",
}


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


def _clean_imported_names(raw_import_str: str) -> List[str]:
    """Parse comma-separated import list and strip aliases (e.g. 'foo as f, bar' -> ['foo', 'bar'])."""
    names = []
    for item in raw_import_str.split(","):
        cleaned = item.strip()
        if not cleaned:
            continue
        # Strip 'as alias'
        parts = cleaned.split()
        if parts:
            names.append(parts[0])
    return names


def extract_internal_imports(file_path: Path, repo_root: Path) -> Set[str]:
    """Extract direct internal imports referenced inside a Python or JS/TS file."""
    referenced_files: Set[str] = set()
    repo_root = repo_root.resolve()
    file_path = file_path.resolve()
    suffix = file_path.suffix.lower()

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return referenced_files

    if suffix == ".py":
        # 1. Match 'from . import foo as f, bar' or 'from .. import baz'
        py_from_dot_import = re.compile(r"^\s*from\s+(\.+)\s+import\s+([a-zA-Z0-9_,\t ]+)", re.MULTILINE)
        for match in py_from_dot_import.finditer(content):
            dots = match.group(1)
            imported_names = _clean_imported_names(match.group(2))
            num_dots = len(dots)
            base_dir = file_path.parent
            for _ in range(num_dots - 1):
                base_dir = base_dir.parent

            for name in imported_names:
                for cand in (base_dir / f"{name}.py", base_dir / name / "__init__.py"):
                    cand_res = cand.resolve()
                    if cand_res.is_file() and cand_res.is_relative_to(repo_root):
                        referenced_files.add(str(cand_res.relative_to(repo_root)))

        # 2. Match 'from .foo import bar as b' or 'from ..foo.bar import baz' or 'from foo.bar import baz as b'
        py_from_module_import = re.compile(r"^\s*from\s+([\.a-zA-Z0-9_]+)\s+import\s+([a-zA-Z0-9_,\t ]+)", re.MULTILINE)
        for match in py_from_module_import.finditer(content):
            raw_module = match.group(1)
            imported_names = _clean_imported_names(match.group(2))

            if raw_module.startswith("."):
                stripped = raw_module.lstrip(".")
                num_dots = len(raw_module) - len(stripped)
                if stripped:
                    sub_path = stripped.replace(".", "/")
                    base_dir = file_path.parent
                    for _ in range(num_dots - 1):
                        base_dir = base_dir.parent

                    # The module itself
                    for cand in (base_dir / f"{sub_path}.py", base_dir / sub_path / "__init__.py"):
                        cand_res = cand.resolve()
                        if cand_res.is_file() and cand_res.is_relative_to(repo_root):
                            referenced_files.add(str(cand_res.relative_to(repo_root)))

                    # Submodules imported from the module (e.g. from ..shared import helper)
                    mod_dir = base_dir / sub_path
                    for name in imported_names:
                        for cand in (mod_dir / f"{name}.py", mod_dir / name / "__init__.py"):
                            cand_res = cand.resolve()
                            if cand_res.is_file() and cand_res.is_relative_to(repo_root):
                                referenced_files.add(str(cand_res.relative_to(repo_root)))
            else:
                sub_path = raw_module.replace(".", "/")
                for prefix in ("", "src/"):
                    # The module itself
                    for cand in (repo_root / f"{prefix}{sub_path}.py", repo_root / f"{prefix}{sub_path}" / "__init__.py"):
                        cand_res = cand.resolve()
                        if cand_res.is_file() and cand_res.is_relative_to(repo_root):
                            referenced_files.add(str(cand_res.relative_to(repo_root)))

                    # Submodules imported from the package (e.g. from src.db import session_store)
                    pkg_dir = repo_root / f"{prefix}{sub_path}"
                    for name in imported_names:
                        for cand in (pkg_dir / f"{name}.py", pkg_dir / name / "__init__.py"):
                            cand_res = cand.resolve()
                            if cand_res.is_file() and cand_res.is_relative_to(repo_root):
                                referenced_files.add(str(cand_res.relative_to(repo_root)))

        # 3. Match 'import foo.bar'
        py_import = re.compile(r"^\s*import\s+([a-zA-Z0-9_\.]+)", re.MULTILINE)
        for match in py_import.finditer(content):
            raw_module = match.group(1)
            sub_path = raw_module.replace(".", "/")
            for prefix in ("", "src/"):
                for cand in (repo_root / f"{prefix}{sub_path}.py", repo_root / f"{prefix}{sub_path}" / "__init__.py"):
                    cand_res = cand.resolve()
                    if cand_res.is_file() and cand_res.is_relative_to(repo_root):
                        referenced_files.add(str(cand_res.relative_to(repo_root)))

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


def expand_keyword_variants(word: str) -> Set[str]:
    """Generate lightweight singular/plural variants for a keyword without broad fuzzing."""
    w = word.lower()
    variants = {w}

    # 1. Singularization
    if w.endswith("ies") and len(w) > 4:
        variants.add(w[:-3] + "y")  # policies -> policy, entries -> entry
    elif w.endswith(("sses", "shes", "ches", "xes", "zes")):
        variants.add(w[:-2])  # classes -> class, boxes -> box
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        variants.add(w[:-1])  # webhooks -> webhook, sessions -> session, routes -> route

    # 2. Pluralization (only if singular-like)
    if w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
        variants.add(w[:-1] + "ies")  # policy -> policies
    elif w.endswith(("sh", "ch", "x", "z")) or w.endswith("ss"):
        variants.add(w + "es")  # class -> classes, box -> boxes
    elif not w.endswith("s"):
        variants.add(w + "s")  # webhook -> webhooks, session -> sessions

    return variants


def filter_files_by_goal(repo_root: Path, all_files: List[str], goal: str) -> List[str]:
    """Filter and expand files based on natural language intent keywords and direct imports.
    
    A file matches if its path components/stem OR its content matches goal keywords (using boundary matching).
    Then expands direct 1-hop internal imports for all matched files.
    """
    raw_keywords = [
        w.lower() for w in re.findall(r"[a-zA-Z0-9_]{3,}", goal)
        if w.lower() not in STOPWORDS
    ]
    if not raw_keywords:
        return all_files

    keywords: Set[str] = set()
    for raw_kw in raw_keywords:
        for variant in expand_keyword_variants(raw_kw):
            if variant not in STOPWORDS and len(variant) >= 3:
                keywords.add(variant)

    matched_files: Set[str] = set()

    for rel_path in all_files:
        p = Path(rel_path)
        # 1. Check path components and stem with boundary
        segments = list(p.parts[:-1]) + [p.stem]
        is_matched = False
        for seg in segments:
            for kw in keywords:
                if re.search(r"(?:^|[^a-zA-Z0-9])" + re.escape(kw) + r"(?:[^a-zA-Z0-9]|$)", seg, re.IGNORECASE):
                    matched_files.add(rel_path)
                    is_matched = True
                    break
            if is_matched:
                break

        if is_matched:
            continue

        # 2. Check file content with boundary
        file_full_path = repo_root / rel_path
        try:
            content = file_full_path.read_text(encoding="utf-8", errors="replace")
            for kw in keywords:
                if re.search(r"(?:^|[^a-zA-Z0-9])" + re.escape(kw) + r"(?:[^a-zA-Z0-9]|$)", content, re.IGNORECASE):
                    matched_files.add(rel_path)
                    break
        except Exception:
            continue

    if not matched_files:
        return all_files

    # 3. Expand direct 1-hop imports for all matched files
    expanded_files = set(matched_files)
    for rel_path in matched_files:
        p = repo_root / rel_path
        imports = extract_internal_imports(p, repo_root)
        for imp in imports:
            if imp in all_files or (repo_root / imp).is_file():
                expanded_files.add(imp)

    return sorted(expanded_files)


def match_scope(rel_path: str, scope: str) -> bool:
    """Check if relative path satisfies path prefix, directory component, or glob pattern."""
    clean_scope = scope.strip("/\\")
    # Glob match
    if any(c in clean_scope for c in ("*", "?", "[", "]")):
        return fnmatch.fnmatch(rel_path, clean_scope) or fnmatch.fnmatch(rel_path, f"{clean_scope}/*")

    # Directory component prefix match
    parts_rel = Path(rel_path).parts
    parts_scope = Path(clean_scope).parts
    if len(parts_rel) >= len(parts_scope) and parts_rel[:len(parts_scope)] == parts_scope:
        return True

    return rel_path == clean_scope


def map_repository(
    repo_path: str,
    scope: Optional[str] = None,
    goal: Optional[str] = None,
    max_clusters: int = 5,
    max_lines: int = 3000,
) -> Dict[str, Any]:
    """Partition codebase, detect entrypoints, and discover architecture."""
    if max_clusters <= 0:
        raise ValueError(f"max_clusters must be >= 1, got {max_clusters}")

    if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
        raise FileNotFoundError(f"Repository directory does not exist: {repo_path}")

    repo_root = Path(repo_path).resolve()

    # Line count cache for single-read performance
    line_cache: Dict[str, int] = {}

    # Discover all reviewable source files
    all_source_files: List[str] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in files:
            p = Path(root) / f
            rel = str(p.relative_to(repo_root))
            if is_reviewable_source(rel):
                all_source_files.append(rel)
                line_cache[rel] = count_file_lines(p)

    # Path scoping
    if scope:
        all_source_files = [f for f in all_source_files if match_scope(f, scope)]

    # Goal scoping
    if goal:
        all_source_files = filter_files_by_goal(repo_root, all_source_files, goal)

    total_files = len(all_source_files)
    total_lines = sum(line_cache.get(f, 0) for f in all_source_files)

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

    # Partition files using shared clustering engine
    file_entries = [(f, line_cache.get(f, 0)) for f in all_source_files]
    clusters = cluster_file_list(
        repo_root=repo_root,
        file_entries=file_entries,
        max_clusters=max_clusters,
        max_lines=max_lines,
    )

    # Attach detected entrypoints to each cluster
    for cluster in clusters:
        cluster_files_set = set(cluster["files"])
        cluster["entrypoints"] = [ep for ep in entrypoints if ep["path"] in cluster_files_set]

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
    parser.add_argument("--scope", type=str, default=None, help="Restrict mapping to a directory path, prefix, or glob pattern.")
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
            "architecture_mode": "empty",
            "scope": args.scope,
            "goal": args.goal,
        }
        print(json.dumps(err_payload, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
