import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Add scripts directory to sys.path
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts"))
AUDIT_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../codebase-audit/scripts"))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, AUDIT_SCRIPT_DIR)

import map_codebase


@pytest.fixture
def sample_polyglot_repo(tmp_path):
    """Create a sample multi-language repository with various entrypoints and modules."""
    repo = tmp_path / "polyglot_repo"
    repo.mkdir()

    # 1. Python CLI & API
    cli_dir = repo / "src" / "cli"
    cli_dir.mkdir(parents=True)
    (cli_dir / "main_cli.py").write_text(
        "import argparse\n"
        "parser = argparse.ArgumentParser(description='Test CLI')\n"
        "parser.add_argument('--count', type=int)\n"
        "if __name__ == '__main__':\n"
        "    parser.parse_args()\n"
    )

    api_dir = repo / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "routes.py").write_text(
        "from fastapi import FastAPI, APIRouter\n"
        "app = FastAPI()\n"
        "router = APIRouter()\n"
        "@app.get('/health')\n"
        "def health_check():\n"
        "    return {'status': 'ok'}\n"
    )

    # 2. Python Worker & Data pipeline
    worker_dir = repo / "src" / "worker"
    worker_dir.mkdir(parents=True)
    (worker_dir / "tasks.py").write_text(
        "from celery import Celery\n"
        "celery_app = Celery('tasks')\n"
        "@celery_app.task\n"
        "def process_item(item_id: int):\n"
        "    pass\n"
    )

    # 3. TypeScript / JS
    frontend_dir = repo / "web"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "server.ts").write_text(
        "import express from 'express';\n"
        "const app = express();\n"
        "app.listen(3000);\n"
    )
    (frontend_dir / "package.json").write_text(
        json.dumps({
            "name": "web-client",
            "version": "1.0.0",
            "bin": {"mycli": "./bin/mycli.js"},
            "scripts": {"start": "node server.js"}
        })
    )

    # 4. Go service
    go_dir = repo / "cmd" / "server"
    go_dir.mkdir(parents=True)
    (go_dir / "main.go").write_text(
        "package main\n\n"
        "import \"fmt\"\n\n"
        "func main() {\n"
        "    fmt.Println(\"Starting Go Server\")\n"
        "}\n"
    )

    # 5. Rust crate
    rust_dir = repo / "crates" / "engine" / "src"
    rust_dir.mkdir(parents=True)
    (rust_dir / "main.rs").write_text(
        "fn main() {\n"
        "    println!(\"Rust Engine\");\n"
        "}\n"
    )

    # 6. Core domain models
    models_dir = repo / "src" / "models"
    models_dir.mkdir(parents=True)
    (models_dir / "user.py").write_text(
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class User:\n"
        "    id: int\n"
        "    name: str\n"
    )

    return repo


def test_empty_repo(tmp_path):
    """Empty repository returns 0 files/lines, clean exit and is_small_repo True."""
    empty_dir = tmp_path / "empty_repo"
    empty_dir.mkdir()

    payload = map_codebase.map_repository(str(empty_dir))
    assert payload["total_files"] == 0
    assert payload["total_lines"] == 0
    assert payload["clusters"] == []
    assert payload["entrypoints"] == []
    assert payload["is_small_repo"] is True


def test_small_repo_fast_path(tmp_path):
    """Small repository (<=3 files, <300 lines) emits is_small_repo: True."""
    small = tmp_path / "small_repo"
    small.mkdir()
    (small / "app.py").write_text("print('hello')\n" * 10)
    (small / "utils.py").write_text("def add(a, b): return a + b\n")

    payload = map_codebase.map_repository(str(small))
    assert payload["total_files"] == 2
    assert payload["total_lines"] < 300
    assert payload["is_small_repo"] is True


def test_path_scoping(sample_polyglot_repo):
    """Path scoping restricts discovered files and clusters to specified subdirectory."""
    payload = map_codebase.map_repository(str(sample_polyglot_repo), scope="src/cli")
    assert payload["total_files"] >= 1
    for cluster in payload["clusters"]:
        for f in cluster["files"]:
            assert f.startswith("src/cli") or "src/cli" in f


def test_intent_scoping_with_import_expansion(tmp_path):
    """Intent scoping with --goal identifies relevant keyword files and expands direct imports."""
    repo = tmp_path / "intent_repo"
    repo.mkdir()

    auth_dir = repo / "src" / "auth"
    auth_dir.mkdir(parents=True)
    (auth_dir / "jwt_session.py").write_text(
        "from src.db.session_store import SessionStore\n"
        "def authenticate_token(token: str):\n"
        "    store = SessionStore()\n"
        "    return store.get_user(token)\n"
    )

    db_dir = repo / "src" / "db"
    db_dir.mkdir(parents=True)
    (db_dir / "session_store.py").write_text(
        "class SessionStore:\n"
        "    def get_user(self, token: str):\n"
        "        return {'uid': 123}\n"
    )

    unrelated_dir = repo / "src" / "analytics"
    unrelated_dir.mkdir(parents=True)
    (unrelated_dir / "metrics.py").write_text(
        "def record_metric(event: str):\n"
        "    pass\n"
    )

    payload = map_codebase.map_repository(str(repo), goal="session token authentication")
    all_scoped_files = [f for c in payload["clusters"] for f in c["files"]]
    
    # Must include jwt_session.py (keyword match) and session_store.py (import expansion)
    assert any("jwt_session.py" in f for f in all_scoped_files)
    assert any("session_store.py" in f for f in all_scoped_files)
    # Must exclude unrelated analytics
    assert not any("metrics.py" in f for f in all_scoped_files)


def test_polyglot_entrypoint_detection(sample_polyglot_repo):
    """Detects entrypoints across Python (CLI, Web, Worker, main), JS/TS, Go, and Rust."""
    payload = map_codebase.map_repository(str(sample_polyglot_repo))
    entrypoints = payload["entrypoints"]

    entry_types = {ep["type"] for ep in entrypoints}
    assert "python_cli" in entry_types or "python_main" in entry_types
    assert "web_route" in entry_types or "api_app" in entry_types
    assert "worker_task" in entry_types or "celery" in entry_types
    assert "go_main" in entry_types or "executable_main" in entry_types
    assert "rust_main" in entry_types or "executable_main" in entry_types


def test_library_fallback(tmp_path):
    """When no explicit entrypoints exist, falls back to Library/SDK mode and __init__.py exports."""
    repo = tmp_path / "lib_repo"
    repo.mkdir()

    src = repo / "src" / "mylib"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("from .tensor import Tensor\n__all__ = ['Tensor']\n")
    (src / "tensor.py").write_text("class Tensor:\n    pass\n")

    payload = map_codebase.map_repository(str(repo))
    assert payload["architecture_mode"] == "library_sdk"
    assert any("__init__.py" in ep["path"] for ep in payload.get("entrypoints", [])) or payload.get("entrypoints") == []


def test_cli_output_json_schema(sample_polyglot_repo):
    """CLI prints valid JSON conforming to the expected schema."""
    cmd = [
        sys.executable,
        os.path.join(SCRIPT_DIR, "map_codebase.py"),
        "--repo",
        str(sample_polyglot_repo),
        "--goal",
        "API health routing",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)

    assert "total_files" in data
    assert "total_lines" in data
    assert "clusters" in data
    assert "entrypoints" in data
    assert "is_small_repo" in data
    assert "goal" in data
    assert data["goal"] == "API health routing"


def test_template_sections_exist():
    """Verify resources/codebase_map_template.md exists and contains required sections."""
    template_path = Path(__file__).parent.parent / "resources" / "codebase_map_template.md"
    assert template_path.exists(), f"Missing template at {template_path}"
    content = template_path.read_text(encoding="utf-8")

    assert "# Codebase Architecture Map" in content
    assert "## 1. System Topology & High-Level Architecture" in content
    assert "## 2. Domain & Module Breakdown" in content
    assert "## 3. End-to-End Dataflows & Execution Lifecycles" in content
    assert "## 4. Developer Cookbook (\"How-To\" Recipes)" in content
    assert "## 5. Global Invariants, Contracts & Gotchas" in content


def test_skill_doc_syntax():
    """Verify SKILL.md exists, has valid YAML frontmatter, and specifies /codebase-map."""
    skill_path = Path(__file__).parent.parent / "SKILL.md"
    assert skill_path.exists(), f"Missing SKILL.md at {skill_path}"
    content = skill_path.read_text(encoding="utf-8")

    assert content.startswith("---")
    assert "name: codebase-map" in content
    assert "/codebase-map" in content
    assert "Stage 1: Cluster & Entrypoint Discovery" in content
    assert "Stage 2: Parallel Subagent Dispatch" in content
    assert "Stage 3: Orchestrator Architecture Synthesis" in content


def test_agents_md_registration():
    """Verify AGENTS.md and GEMINI.md register codebase-map in the global skills list."""
    repo_root = Path(__file__).parent.parent.parent.parent
    agents_md = repo_root / "AGENTS.md"
    gemini_md = repo_root / "GEMINI.md"

    assert agents_md.exists()
    assert "skills/codebase-map/SKILL.md" in agents_md.read_text(encoding="utf-8")

    assert gemini_md.exists()
    assert "skills/codebase-map/SKILL.md" in gemini_md.read_text(encoding="utf-8")


def test_relative_dot_import_expansion(tmp_path):
    """Verify relative dot imports (e.g. from .helpers import foo, from ..db import bar) resolve properly."""
    repo = tmp_path / "dot_imports_repo"
    repo.mkdir()

    sub = repo / "src" / "sub" / "pkg"
    sub.mkdir(parents=True)
    (sub / "worker.py").write_text(
        "from .local_helper import do_work\n"
        "from ..sibling import db_call\n"
        "def run():\n"
        "    do_work()\n"
        "    db_call()\n"
    )
    (sub / "local_helper.py").write_text("def do_work(): pass\n")

    sibling_dir = repo / "src" / "sub"
    (sibling_dir / "sibling.py").write_text("def db_call(): pass\n")

    imports = map_codebase.extract_internal_imports(sub / "worker.py", repo)
    assert "src/sub/pkg/local_helper.py" in imports
    assert "src/sub/sibling.py" in imports


def test_max_clusters_consolidation(tmp_path):
    """Verify domains exceeding max_clusters consolidate into shared_utils."""
    repo = tmp_path / "multi_domain_repo"
    repo.mkdir()

    for i in range(8):
        dom = repo / f"domain_{i}"
        dom.mkdir()
        (dom / f"mod_{i}.py").write_text(f"# Domain {i}\n" * (10 + i * 5))

    payload = map_codebase.map_repository(str(repo), max_clusters=3)
    assert len(payload["clusters"]) <= 3
    cluster_domains = {c["domain"] for c in payload["clusters"]}
    assert "shared_utils" in cluster_domains

