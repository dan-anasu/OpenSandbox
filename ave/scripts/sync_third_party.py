#!/usr/bin/env python3
"""
Sync third-party SkillJect material into ave/third_party/skillject/.

Ensures reproducibility by pinning to SkillJect commit 6598997,
verifying a clean source working tree, recording sha256 hashes in
ave/manifest/third_party_manifest.json, and supporting --verify checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

PINNED_COMMIT_PREFIX = "6598997"
SOURCE_REPO_URL = "https://github.com/jiaxiaojunQAQ/SkillJect.git"

# The 12 selected target skills for Chapter Three experimental pipeline
SELECTED_SKILLS = [
    "react-best-practices",
    "backend-migrations-eis-its",
    "sql-to-osc",
    "global-error-handling",
    "global-commenting-eis-its",
    "code-analysis",
    "api-compat-1.0.0",
    "deps-mgmt-1.0.0",
    "testing-test-writing",
    "managing-commits",
    "changelog-generator",
    "technical-decision-record",
]

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

STATIC_SCAN_PATTERNS = [
    "curl",
    "wget",
    "requests",
    "urllib",
    "httpx",
    "socket",
    "http://",
    "https://",
    "pip install",
    "npm install",
    "git clone",
    "subprocess",
    "os.system",
    "eval(",
    "exec(",
]


def compute_sha256(path: Path) -> str:
    """Compute sha256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def check_git_repo(source_dir: Path) -> str:
    """Verify SkillJect is at pinned commit and clean.
    
    If cleanliness check fails, prints offending paths and stops without modifying anything.
    """
    if not (source_dir / ".git").exists():
        raise RuntimeError(f"Source directory {source_dir} is not a git repository")

    # Check commit
    rev_proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    commit = rev_proc.stdout.strip()
    if not commit.startswith(PINNED_COMMIT_PREFIX):
        raise RuntimeError(
            f"SkillJect HEAD is {commit}, expected commit prefix {PINNED_COMMIT_PREFIX}"
        )

    # Check clean working tree
    status_proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=source_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    status_output = status_proc.stdout.strip()
    if status_output:
        lines = [line.strip() for line in status_output.splitlines() if line.strip()]
        print(f"[-] SkillJect cleanliness check failed: working tree at {source_dir} is not clean.", file=sys.stderr)
        print("[-] Offending uncommitted / untracked paths:", file=sys.stderr)
        for line in lines:
            print(f"    {line}", file=sys.stderr)
        raise RuntimeError(
            f"SkillJect working tree is dirty ({len(lines)} offending paths). "
            "Refusing to sync without modifying or cleaning source repo."
        )

    return commit


def check_no_symlinks(folder: Path) -> None:
    """Symlink guard: abort if any file or directory in folder is a symlink."""
    symlinks: list[str] = []
    for root, dirs, files in os.walk(folder, followlinks=False):
        for d in dirs:
            p = Path(root) / d
            if p.is_symlink():
                symlinks.append(str(p))
        for f in files:
            p = Path(root) / f
            if p.is_symlink():
                symlinks.append(str(p))
    if symlinks:
        formatted = "\n".join(f"  - {p}" for p in symlinks)
        raise RuntimeError(
            f"Symlink guard failure in {folder} — refusing to copy symlink targets:\n{formatted}"
        )


def extract_frontmatter_name(skill_md_path: Path) -> str:
    """Extract 'name' field from frontmatter in SKILL.md."""
    content = skill_md_path.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        raise ValueError(f"No frontmatter found in {skill_md_path}")
    fm_text = match.group(1)
    for line in fm_text.splitlines():
        line = line.strip()
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    raise ValueError(f"No 'name:' found in frontmatter of {skill_md_path}")


def validate_copied_skills_with_copied_parser(
    skills_pool_target: Path, parser_target: Path, skill_manifest_info: list[dict[str, str]]
) -> list[tuple[str, int]]:
    """Parse every copied SKILL.md using ONLY the copied UnifiedSkillParser.
    
    Asserts each parsed frontmatter name equals its destination directory name.
    Fails loudly on any mismatch and returns table of (name, desc_len).
    """
    sys.path.insert(0, str(parser_target))
    try:
        from skill_parser import UnifiedSkillParser
        parser = UnifiedSkillParser()
    finally:
        if str(parser_target) in sys.path:
            sys.path.remove(str(parser_target))

    mismatches: list[tuple[str, str]] = []
    table: list[tuple[str, int]] = []

    for item in skill_manifest_info:
        dest_dir_name = item["frontmatter_name"]
        skill_md_path = skills_pool_target / dest_dir_name / "SKILL.md"
        if not skill_md_path.exists():
            raise FileNotFoundError(f"Copied SKILL.md missing: {skill_md_path}")

        parse_res = parser.parse_file(str(skill_md_path))
        parsed_name = parse_res.get_frontmatter_value("name")
        desc = parser.extract_description(parse_res.frontmatter)

        if parsed_name != dest_dir_name:
            mismatches.append((dest_dir_name, str(parsed_name)))

        table.append((dest_dir_name, len(desc)))

    if mismatches:
        err_lines = [
            f"  - Destination dir: '{exp}' != Parsed name: '{got}'"
            for exp, got in mismatches
        ]
        raise AssertionError(
            "Frontmatter name mismatch detected using copied UnifiedSkillParser:\n"
            + "\n".join(err_lines)
        )

    print("\n[+] Verification: All 12 copied SKILL.md files parsed cleanly with copied UnifiedSkillParser:")
    print(f"    {'Frontmatter Name':<32} | {'Description Length':<20}")
    print("    " + "-" * 56)
    for name, d_len in table:
        print(f"    {name:<32} | {d_len:<20}")
    print()

    return table


def run_static_scan(target_root: Path, repo_root: Path) -> list[tuple[str, int, str]]:
    """Scan every copied file in skills_pool/ and tasks_src/ for suspicious patterns."""
    findings: list[tuple[str, int, str]] = []
    scan_dirs = [target_root / "skills_pool", target_root / "tasks_src"]

    for s_dir in scan_dirs:
        if not s_dir.exists():
            continue
        for root, _, files in os.walk(s_dir):
            for f in sorted(files):
                file_path = Path(root) / f
                rel_path = str(file_path.relative_to(repo_root))
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                        for line_no, line in enumerate(fp, start=1):
                            line_clean = line.rstrip("\r\n")
                            line_lower = line_clean.lower()
                            for pat in STATIC_SCAN_PATTERNS:
                                if pat in line_lower:
                                    findings.append((rel_path, line_no, line_clean[:120]))
                                    break
                except Exception as e:
                    findings.append((rel_path, 0, f"<error reading file: {e}>"))

    return findings


def sync(source_dir: Path, repo_root: Path) -> int:
    """Perform one-time synchronization and generate manifest."""
    source_commit = check_git_repo(source_dir)
    print(f"[+] SkillJect source verified: commit {source_commit} (clean working tree)")

    target_root = repo_root / "ave" / "third_party" / "skillject"
    manifest_dir = repo_root / "ave" / "manifest"
    manifest_path = manifest_dir / "third_party_manifest.json"

    skills_pool_target = target_root / "skills_pool"
    tasks_src_target = target_root / "tasks_src"
    parser_target = target_root / "parser"

    # Clean prior sync if present
    if target_root.exists():
        shutil.rmtree(target_root)
    skills_pool_target.mkdir(parents=True, exist_ok=True)
    tasks_src_target.mkdir(parents=True, exist_ok=True)
    parser_target.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    manifest_files: list[dict[str, Any]] = []
    skill_manifest_info: list[dict[str, str]] = []
    frontmatter_names: set[str] = set()

    # 1. Sync skills_pool/ and tasks_src/
    for skill_dir_name in SELECTED_SKILLS:
        skill_src_dir = source_dir / "data" / "skills_sample" / skill_dir_name
        task_src_dir = source_dir / "data" / "instruction" / "skills_sample" / skill_dir_name

        if not skill_src_dir.exists():
            raise FileNotFoundError(f"Skill directory not found: {skill_src_dir}")
        if not task_src_dir.exists():
            raise FileNotFoundError(f"Task directory not found: {task_src_dir}")

        # Symlink guard: check both source directories
        check_no_symlinks(skill_src_dir)
        check_no_symlinks(task_src_dir)

        fm_name = extract_frontmatter_name(skill_src_dir / "SKILL.md")
        if fm_name in frontmatter_names:
            raise ValueError(f"Duplicate frontmatter name detected: {fm_name}")
        frontmatter_names.add(fm_name)

        skill_dst_dir = skills_pool_target / fm_name
        task_dst_dir = tasks_src_target / fm_name
        skill_dst_dir.mkdir(parents=True, exist_ok=True)
        task_dst_dir.mkdir(parents=True, exist_ok=True)

        # Copy skill files
        for root, _, files in os.walk(skill_src_dir, followlinks=False):
            rel_root = Path(root).relative_to(skill_src_dir)
            dst_sub = skill_dst_dir / rel_root
            dst_sub.mkdir(parents=True, exist_ok=True)
            for f in files:
                src_f = Path(root) / f
                dst_f = dst_sub / f
                shutil.copy2(src_f, dst_f, follow_symlinks=False)
                manifest_files.append({
                    "source_path": str(src_f.relative_to(source_dir)),
                    "destination_path": str(dst_f.relative_to(repo_root)),
                    "sha256": compute_sha256(dst_f),
                })

        # Copy task files (unmodified)
        for root, _, files in os.walk(task_src_dir, followlinks=False):
            rel_root = Path(root).relative_to(task_src_dir)
            dst_sub = task_dst_dir / rel_root
            dst_sub.mkdir(parents=True, exist_ok=True)
            for f in files:
                src_f = Path(root) / f
                dst_f = dst_sub / f
                shutil.copy2(src_f, dst_f, follow_symlinks=False)
                manifest_files.append({
                    "source_path": str(src_f.relative_to(source_dir)),
                    "destination_path": str(dst_f.relative_to(repo_root)),
                    "sha256": compute_sha256(dst_f),
                })

        skill_manifest_info.append({
            "source_dir": skill_dir_name,
            "frontmatter_name": fm_name,
            "skills_pool_path": str(skill_dst_dir.relative_to(repo_root)),
            "tasks_src_path": str(task_dst_dir.relative_to(repo_root)),
        })

    # 2. Sync parser/
    # Minimum required files for UnifiedSkillParser
    parser_files_to_copy = [
        (
            source_dir / "src" / "domain" / "generation" / "interfaces" / "i_skill_parser.py",
            parser_target / "i_skill_parser.py",
            "src/domain/generation/interfaces/i_skill_parser.py",
        ),
        (
            source_dir / "src" / "domain" / "generation" / "services" / "parsers" / "skill_parser.py",
            parser_target / "skill_parser.py",
            "src/domain/generation/services/parsers/skill_parser.py",
        ),
    ]

    header_comment = (
        f"# Source: {{source_path}}\n"
        f"# SkillJect commit: {PINNED_COMMIT_PREFIX}\n"
    )

    for src_file, dst_file, rel_src in parser_files_to_copy:
        content = src_file.read_text(encoding="utf-8")
        # Ensure self-contained relative import in skill_parser.py
        if dst_file.name == "skill_parser.py":
            old_import = "from src.domain.generation.interfaces import ISkillParser, SkillParseResult"
            new_import = (
                "try:\n"
                "    from .i_skill_parser import ISkillParser, SkillParseResult\n"
                "except ImportError:\n"
                "    from i_skill_parser import ISkillParser, SkillParseResult"
            )
            if old_import in content:
                content = content.replace(old_import, new_import)
            else:
                raise ValueError("Expected import not found in skill_parser.py")

        full_content = header_comment.format(source_path=rel_src) + content
        dst_file.write_text(full_content, encoding="utf-8")

        manifest_files.append({
            "source_path": rel_src,
            "destination_path": str(dst_file.relative_to(repo_root)),
            "sha256": compute_sha256(dst_file),
            "modified": True,
            "transform": "header comment + import rewrite",
        })

    # Create parser __init__.py for clean module import
    init_file = parser_target / "__init__.py"
    init_content = (
        f"# Source: ave/third_party/skillject/parser/__init__.py\n"
        f"# SkillJect commit: {PINNED_COMMIT_PREFIX}\n\n"
        "try:\n"
        "    from .skill_parser import UnifiedSkillParser, get_skill_parser\n"
        "    from .i_skill_parser import ISkillParser, SkillParseResult\n"
        "except ImportError:\n"
        "    from skill_parser import UnifiedSkillParser, get_skill_parser\n"
        "    from i_skill_parser import ISkillParser, SkillParseResult\n\n"
        "__all__ = ['UnifiedSkillParser', 'ISkillParser', 'SkillParseResult', 'get_skill_parser']\n"
    )
    init_file.write_text(init_content, encoding="utf-8")
    manifest_files.append({
        "generated": True,
        "destination_path": str(init_file.relative_to(repo_root)),
        "sha256": compute_sha256(init_file),
    })

    # Sort manifest entries for reproducibility
    manifest_files.sort(key=lambda x: x["destination_path"])

    manifest_data = {
        "source_repo_url": SOURCE_REPO_URL,
        "source_commit": source_commit,
        "source_commit_prefix": PINNED_COMMIT_PREFIX,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "skills_count": len(skill_manifest_info),
        "total_files_count": len(manifest_files),
        "skills": skill_manifest_info,
        "files": manifest_files,
    }

    manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
    print(f"[+] Synced {len(skill_manifest_info)} skills ({len(manifest_files)} files total)")
    print(f"[+] Manifest written to {manifest_path.relative_to(repo_root)}")

    # 3. Post-sync verification: validate with COPIED parser
    validate_copied_skills_with_copied_parser(
        skills_pool_target, parser_target, skill_manifest_info
    )

    # 4. Post-sync verification: run static scan
    print("[*] Running static security scan on all copied files...")
    findings = run_static_scan(target_root, repo_root)
    print(f"[+] Static scan complete: {len(findings)} match(es) across copied files.\n")

    return 0


def verify(repo_root: Path) -> int:
    """Verify all destination files against third_party_manifest.json, including extra file check."""
    manifest_path = repo_root / "ave" / "manifest" / "third_party_manifest.json"
    if not manifest_path.exists():
        print(f"[-] Manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest_data.get("files", [])
    print(f"[*] Verifying {len(files)} files against manifest {manifest_path.name}...")

    missing = 0
    mismatched = 0

    for item in files:
        dst_rel = item["destination_path"]
        expected_hash = item["sha256"]
        dst_path = repo_root / dst_rel

        if not dst_path.exists():
            print(f"[-] Missing file: {dst_rel}", file=sys.stderr)
            missing += 1
            continue

        actual_hash = compute_sha256(dst_path)
        if actual_hash != expected_hash:
            print(
                f"[-] Checksum mismatch for {dst_rel}:\n"
                f"    expected: {expected_hash}\n"
                f"    actual:   {actual_hash}",
                file=sys.stderr,
            )
            mismatched += 1

    # Check for unexpected extra files under ave/third_party/skillject/
    target_root = repo_root / "ave" / "third_party" / "skillject"
    actual_files: set[str] = set()
    if target_root.exists():
        for root, dirs, files_in_dir in os.walk(target_root):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files_in_dir:
                if f.endswith(".pyc"):
                    continue
                actual_files.add(str((Path(root) / f).relative_to(repo_root)))

    expected_files: set[str] = {item["destination_path"] for item in files}
    unexpected_files = sorted(actual_files - expected_files)
    if unexpected_files:
        print(
            f"[-] Unexpected extra file(s) found under {target_root.relative_to(repo_root)}:",
            file=sys.stderr,
        )
        for uf in unexpected_files:
            print(f"    - {uf}", file=sys.stderr)

    if missing == 0 and mismatched == 0 and len(unexpected_files) == 0:
        print(f"[+] All {len(files)} files verified successfully. Hashes match and no extra files found.")
        return 0
    else:
        print(
            f"[-] Verification failed: {missing} missing, {mismatched} mismatched, {len(unexpected_files)} extra",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    default_source = Path("/home/kali/Downloads/SkillJect")

    parser = argparse.ArgumentParser(description="Sync or verify third-party SkillJect assets.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=default_source,
        help=f"Path to local SkillJect checkout (default: {default_source})",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing synced files against manifest hashes instead of syncing",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Run static security scan on copied third-party files without syncing",
    )

    args = parser.parse_args()

    if args.verify:
        return verify(repo_root)
    elif args.scan:
        target_root = repo_root / "ave" / "third_party" / "skillject"
        findings = run_static_scan(target_root, repo_root)
        print(f"File Path | Line Number | Matching Line")
        print("-" * 80)
        for path, line_no, text in findings:
            print(f"{path}:{line_no}: {text}")
        return 0
    else:
        return sync(args.source_dir, repo_root)


if __name__ == "__main__":
    sys.exit(main())
