#!/usr/bin/env python3
"""Rebuild the source-code delivery package, manifest and zip.

The package contains only files tracked by git, minus the paths that hold
local runtime data, build output, internal planning material or the delivery
directory itself.  The same script then writes PACKAGE_MANIFEST.json, builds
the zip and verifies the extracted archive file by file.

Typical use (from the repository root):

    python3 scripts/build_delivery.py

Defaults match the tunnel-features-v2 / package revision v3 delivery.  Use the
command line options to rebuild another revision without editing the script.
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
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

PACKAGE_NAME = "基于视频感知的隧道交通数字孪生系统源码包"
DELIVERY_DIR = "交付"
DEFAULT_VERSION = "tunnel-features-v2"
DEFAULT_REVISION = "v3"
DEFAULT_DATE = "2026-10-22"
DEFAULT_SOURCE_COMMIT = "c6aa02f"
DEFAULT_SOURCE_BRANCH = "main"

# Top-level directories that are never part of the delivery package.
EXCLUDED_TOP_LEVEL = {".git", "output", "plans", DELIVERY_DIR}

# Directory names excluded at any depth.
EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".playwright-cli",
    "node_modules",
}

# Virtual-environment directory names.  Matches .venv, venv, env,
# virtualenv, pyvenv and names such as .venv-3.12 / project-venv.
VENV_DIR_RE = re.compile(r"^(?:\.?.*venv|virtualenv|env|pyvenv)$", re.IGNORECASE)

# Compiled Python artefacts (normally already covered by __pycache__).
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(repo_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def tracked_files(repo_root: Path) -> list[str]:
    raw = run_git(repo_root, "ls-files", "-z")
    return sorted(path for path in raw.decode("utf-8").split("\0") if path)


def excluded_reason(relative_path: str) -> str | None:
    """Return a human-readable exclusion reason, or None if included."""
    path = PurePosixPath(relative_path)
    parts = path.parts
    if not parts:
        return "empty path"

    if parts[0] in EXCLUDED_TOP_LEVEL:
        return f"top-level directory {parts[0]!r}"

    # frontend/dist is build output, not source.
    if relative_path == "frontend/dist" or relative_path.startswith("frontend/dist/"):
        return "frontend build output"

    for part in parts[:-1]:
        if part in EXCLUDED_DIR_NAMES:
            return f"excluded directory {part!r}"
        if VENV_DIR_RE.match(part):
            return f"virtual environment {part!r}"

    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return "compiled Python file"

    return None


def select_source_files(repo_root: Path) -> list[str]:
    selected: list[str] = []
    skipped: list[tuple[str, str]] = []
    for relative_path in tracked_files(repo_root):
        reason = excluded_reason(relative_path)
        if reason:
            skipped.append((relative_path, reason))
        else:
            selected.append(relative_path)

    if skipped:
        print(f"Excluded {len(skipped)} tracked path(s):")
        for relative_path, reason in skipped:
            print(f"  - {relative_path} ({reason})")
    return selected


def copy_sources(repo_root: Path, package_dir: Path, files: list[str]) -> None:
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    for relative_path in files:
        source = repo_root / relative_path
        target = package_dir / relative_path
        if not source.is_file():
            raise RuntimeError(f"tracked path is not a regular file: {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def build_manifest(
    package_dir: Path,
    files: list[str],
    *,
    version: str,
    revision: str,
    created_date: str,
    source_commit: str,
    source_branch: str,
) -> dict:
    entries = []
    for relative_path in sorted(files):
        target = package_dir / relative_path
        entries.append(
            {
                "path": relative_path,
                "size_bytes": target.stat().st_size,
                "sha256": sha256_file(target),
            }
        )

    manifest = {
        "package": PACKAGE_NAME,
        "version": version,
        "package_revision": revision,
        "created_date": created_date,
        "source_commit": source_commit,
        "source_branch": source_branch,
        "file_count_excluding_manifest": len(entries),
        "files": entries,
    }
    manifest_path = package_dir / "PACKAGE_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_zip(package_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = zip_path.with_name(zip_path.name + ".tmp")
    if temporary.exists():
        temporary.unlink()

    package_root = package_dir.name
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        # Explicit directory entry keeps the archive friendly to extractors
        # that do not create the top-level directory implicitly.
        directory_info = zipfile.ZipInfo(package_root + "/")
        directory_info.external_attr = (0o40755 << 16) | 0x10
        directory_info.compress_type = zipfile.ZIP_STORED
        archive.writestr(directory_info, b"")

        for source in sorted(package_dir.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(package_dir).as_posix()
            archive.write(source, f"{package_root}/{relative}")

    os.replace(temporary, zip_path)


def validate_zip(
    zip_path: Path,
    package_dir: Path,
    expected_files: list[str],
    expected_manifest: dict,
) -> None:
    errors: list[str] = []
    expected = set(expected_files)
    expected_manifest_paths = {
        entry["path"]: entry for entry in expected_manifest["files"]
    }

    with tempfile.TemporaryDirectory(prefix="twin-delivery-verify-") as temporary:
        extraction_root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            bad = archive.testzip()
            if bad is not None:
                errors.append(f"zip CRC failure: {bad}")
            archive.extractall(extraction_root)

        extracted_package = extraction_root / package_dir.name
        if not extracted_package.is_dir():
            raise RuntimeError("zip does not contain the package directory")

        extracted_manifest_path = extracted_package / "PACKAGE_MANIFEST.json"
        if not extracted_manifest_path.is_file():
            raise RuntimeError("zip does not contain PACKAGE_MANIFEST.json")
        extracted_manifest = json.loads(
            extracted_manifest_path.read_text(encoding="utf-8")
        )

        for key in (
            "package",
            "version",
            "package_revision",
            "created_date",
            "source_commit",
            "source_branch",
        ):
            if extracted_manifest.get(key) != expected_manifest.get(key):
                errors.append(
                    f"manifest {key}: expected {expected_manifest.get(key)!r}, "
                    f"got {extracted_manifest.get(key)!r}"
                )

        extracted_files = {
            path.relative_to(extracted_package).as_posix()
            for path in extracted_package.rglob("*")
            if path.is_file()
        }

        manifest_paths = {
            entry.get("path") for entry in extracted_manifest.get("files", [])
        }
        if len(manifest_paths) != len(extracted_manifest.get("files", [])):
            errors.append("manifest contains duplicate paths")
        if manifest_paths != expected:
            missing = sorted(expected - manifest_paths)
            extra = sorted(manifest_paths - expected)
            if missing:
                errors.append(f"manifest missing paths: {missing[:10]}")
            if extra:
                errors.append(f"manifest has unexpected paths: {extra[:10]}")

        if extracted_manifest.get("file_count_excluding_manifest") != len(expected):
            errors.append(
                "file_count_excluding_manifest mismatch: "
                f"expected {len(expected)}, "
                f"got {extracted_manifest.get('file_count_excluding_manifest')}"
            )

        if extracted_files != expected | {"PACKAGE_MANIFEST.json"}:
            missing = sorted((expected | {"PACKAGE_MANIFEST.json"}) - extracted_files)
            extra = sorted(extracted_files - (expected | {"PACKAGE_MANIFEST.json"}))
            if missing:
                errors.append(f"zip missing files: {missing[:10]}")
            if extra:
                errors.append(f"zip has unexpected files: {extra[:10]}")

        for relative_path in sorted(expected):
            reason = excluded_reason(relative_path)
            if reason:
                errors.append(f"excluded path present: {relative_path} ({reason})")
                continue
            entry = expected_manifest_paths.get(relative_path)
            if entry is None:
                errors.append(f"manifest missing entry: {relative_path}")
                continue
            extracted = extracted_package / relative_path
            if not extracted.is_file():
                errors.append(f"missing extracted file: {relative_path}")
                continue
            if extracted.stat().st_size != entry.get("size_bytes"):
                errors.append(
                    f"size mismatch: {relative_path} "
                    f"(expected {entry.get('size_bytes')}, "
                    f"got {extracted.stat().st_size})"
                )
            actual_sha = sha256_file(extracted)
            if actual_sha != entry.get("sha256"):
                errors.append(
                    f"sha256 mismatch: {relative_path} "
                    f"(expected {entry.get('sha256')}, got {actual_sha})"
                )

        for relative_path in sorted(extracted_files):
            if relative_path == "PACKAGE_MANIFEST.json":
                continue
            reason = excluded_reason(relative_path)
            if reason:
                errors.append(f"excluded path present: {relative_path} ({reason})")

    if errors:
        print("Validation FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        raise SystemExit(1)

    print(
        f"Validation passed: {len(expected)} source files + manifest, "
        "SHA-256 and excluded-path checks OK"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root (default: parent of scripts/)",
    )
    parser.add_argument("--package-name", default=PACKAGE_NAME)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--package-revision", default=DEFAULT_REVISION)
    parser.add_argument("--created-date", default=DEFAULT_DATE)
    parser.add_argument(
        "--source-commit",
        default=DEFAULT_SOURCE_COMMIT,
        help="commit-ish to resolve to a full hash for the manifest",
    )
    parser.add_argument("--source-branch", default=DEFAULT_SOURCE_BRANCH)
    parser.add_argument(
        "--skip-zip",
        action="store_true",
        help="only rebuild the directory and manifest",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    if not (repo_root / ".git").exists():
        raise SystemExit(f"not a git repository: {repo_root}")

    delivery_dir = repo_root / DELIVERY_DIR
    package_dir = delivery_dir / args.package_name
    zip_path = delivery_dir / f"{args.package_name}.zip"

    source_commit = run_git(repo_root, "rev-parse", args.source_commit).decode().strip()
    files = select_source_files(repo_root)
    print(f"Tracked source files selected: {len(files)}")

    copy_sources(repo_root, package_dir, files)
    manifest = build_manifest(
        package_dir,
        files,
        version=args.version,
        revision=args.package_revision,
        created_date=args.created_date,
        source_commit=source_commit,
        source_branch=args.source_branch,
    )
    print(f"Package: {package_dir}")
    print(f"Manifest: {manifest['file_count_excluding_manifest']} files")
    print(f"Source commit: {source_commit}")

    if args.skip_zip:
        return

    build_zip(package_dir, zip_path)
    print(f"Zip: {zip_path}")
    validate_zip(zip_path, package_dir, files, manifest)


if __name__ == "__main__":
    main()
