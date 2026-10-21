#!/usr/bin/env python
"""静态扫描指定 Django App，保存 Ruff/Bandit 原始结果与 manifest。

用法（仓库根目录执行）：
    python doc/week7-8/tools/scan_app.py accounts baseline
    python doc/week7-8/tools/scan_app.py accounts after

驱动只读取源码文本并调用 Ruff/Bandit，不导入 Django、不启动项目。
"""

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[2]
APP_ROOT = REPO_ROOT / "src" / "DjangoBlog"
RUFF_CONFIG = TOOLS_DIR / "ruff.toml"
MEMBER = "YFY"
RAW_DIR = REPO_ROOT / "doc" / "week7-8" / "成员成果" / MEMBER / "原始工具结果"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_git(*args):
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return completed.stdout.strip()
    except OSError:
        return ""


def is_excluded(relative_path: Path) -> bool:
    parts = relative_path.parts
    if "migrations" in parts or "tests" in parts or "__pycache__" in parts:
        return True
    name = relative_path.name
    return name == "tests.py" or name.startswith("test") and name.endswith(".py")


def collect_files(app: str):
    app_dir = APP_ROOT / app
    if not app_dir.is_dir():
        raise SystemExit(f"App 目录不存在：{app_dir}")
    selected, excluded = [], []
    for path in sorted(app_dir.rglob("*.py")):
        relative = path.relative_to(app_dir)
        if is_excluded(relative):
            excluded.append(str(relative).replace("\\", "/"))
        else:
            selected.append(path)
    return app_dir, selected, excluded


def file_metrics(path: Path):
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    code_lines = sum(
        1 for line in lines if line.strip() and not line.lstrip().startswith("#")
    )
    try:
        tree = ast.parse(text)
        classes = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
        functions = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )
    except SyntaxError:
        classes = functions = -1
    return {
        "physical_lines": len(lines),
        "code_lines": code_lines,
        "classes": classes,
        "functions": functions,
        "sha256": sha256_bytes(raw),
    }


def run(command):
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed


def version_of(module: str) -> str:
    completed = run([sys.executable, "-m", module, "--version"])
    output = (completed.stdout or completed.stderr).strip().splitlines()
    return output[0] if output else "unknown"


def main():
    parser = argparse.ArgumentParser(description="Ruff + Bandit 静态扫描驱动")
    parser.add_argument("app", help="Django App 名称，例如 accounts")
    parser.add_argument("phase", choices=["baseline", "after"], help="扫描阶段")
    parser.add_argument("--member", default=MEMBER, help="成员成果目录名")
    args = parser.parse_args()

    global RAW_DIR
    RAW_DIR = REPO_ROOT / "doc" / "week7-8" / "成员成果" / args.member / "原始工具结果"
    out_dir = RAW_DIR / args.phase
    if out_dir.exists():
        raise SystemExit(f"证据目录已存在，拒绝覆盖：{out_dir}")

    app_dir, files, excluded = collect_files(args.app)
    if not files:
        raise SystemExit("没有可扫描的业务 Python 文件")

    rel_files = [str(path.relative_to(REPO_ROOT)).replace("\\", "/") for path in files]
    out_dir.mkdir(parents=True)

    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    head_sha = run_git("rev-parse", "HEAD")
    branch = run_git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = run_git("status", "--porcelain=v1")

    ruff_command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--no-cache",
        "--output-format",
        "json",
        "--config",
        str(RUFF_CONFIG),
        *rel_files,
    ]
    bandit_command = [
        sys.executable,
        "-m",
        "bandit",
        "-q",
        "-f",
        "json",
        "--ignore-nosec",
        *rel_files,
    ]

    ruff_result = run(ruff_command)
    bandit_result = run(bandit_command)

    (out_dir / "ruff.json").write_text(ruff_result.stdout, encoding="utf-8")
    (out_dir / "bandit.json").write_text(bandit_result.stdout, encoding="utf-8")
    (out_dir / "ruff.stderr.txt").write_text(ruff_result.stderr, encoding="utf-8")
    (out_dir / "bandit.stderr.txt").write_text(bandit_result.stderr, encoding="utf-8")

    try:
        ruff_findings = json.loads(ruff_result.stdout or "[]")
    except json.JSONDecodeError:
        ruff_findings = []
    try:
        bandit_payload = json.loads(bandit_result.stdout or "{}")
        bandit_findings = bandit_payload.get("results", [])
    except json.JSONDecodeError:
        bandit_findings = []

    manifest = {
        "app": args.app,
        "phase": args.phase,
        "member": args.member,
        "started_at": started_at,
        "repo_root": str(REPO_ROOT),
        "app_dir": str(app_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
        "branch": branch,
        "head_sha": head_sha,
        "working_tree_dirty": bool(dirty),
        "working_tree_status": dirty.splitlines(),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "ruff_version": version_of("ruff"),
        "bandit_version": version_of("bandit"),
        "config_files": {
            "ruff": "doc/week7-8/tools/ruff.toml",
            "driver": "doc/week7-8/tools/scan_app.py",
        },
        "config_sha256": sha256_bytes(
            RUFF_CONFIG.read_bytes() + Path(__file__).read_bytes()
        ),
        "selection": {
            "include": "App 下全部业务 Python（含 commands、templatetags、__init__.py）",
            "exclude": ["migrations/", "tests/", "test*.py", "tests.py", "__pycache__"],
        },
        "excluded_files": excluded,
        "files": [],
        "commands": {
            "ruff": " ".join(ruff_command),
            "bandit": " ".join(bandit_command),
        },
        "exit_codes": {"ruff": ruff_result.returncode, "bandit": bandit_result.returncode},
        "finding_counts": {"ruff": len(ruff_findings), "bandit": len(bandit_findings)},
        "outputs": ["ruff.json", "bandit.json", "ruff.stderr.txt", "bandit.stderr.txt"],
        "metrics_note": "code_lines 为非空且不以 # 开头的物理行；类/函数含嵌套定义。",
    }
    for path in files:
        relative = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        manifest["files"].append({"path": relative, **file_metrics(path)})

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"扫描完成：{args.app} / {args.phase}")
    print(f"工作区基线 SHA：{head_sha}（{branch}，dirty={bool(dirty)}）")
    print(f"Ruff：{manifest['ruff_version']} 退出码 {ruff_result.returncode}，"
          f"{len(ruff_findings)} 条")
    print(f"Bandit：{manifest['bandit_version']} 退出码 {bandit_result.returncode}，"
          f"{len(bandit_findings)} 条")
    print(f"原始结果：{out_dir}")


if __name__ == "__main__":
    main()
