#!/usr/bin/env python3
"""Create a reproducible, line-wise inventory of reference repositories.

This is deliberately standard-library only.  It reads every tracked file,
hashes its exact bytes, counts every text line, identifies binaries and
classifies generated/vendor material separately from authorial source.  The
result is a compact JSON manifest: enough to prove the audited revision and
coverage without checking tens of thousands of third-party filenames into
Athena.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


CODE_EXTENSIONS = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".h": "C/C++ header",
    ".hpp": "C++ header",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript JSX",
    ".kt": "Kotlin",
    ".lua": "Lua",
    ".mjs": "JavaScript",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sh": "Shell",
    ".sql": "SQL",
    ".svelte": "Svelte",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript TSX",
    ".vue": "Vue",
}

BINARY_EXTENSIONS = {
    ".7z", ".avi", ".bin", ".bmp", ".class", ".dll", ".docx", ".eot",
    ".gif", ".gz", ".ico", ".jar", ".jpeg", ".jpg", ".mkv", ".mov",
    ".mp3", ".mp4", ".onnx", ".otf", ".parquet", ".pdf", ".pickle",
    ".png", ".pt", ".pth", ".pyc", ".safetensors", ".so", ".tar",
    ".tflite", ".ttf", ".wav", ".webm", ".webp", ".woff", ".woff2",
    ".xls", ".xlsx", ".xz", ".zip",
}

GENERATED_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock",
    "uv.lock", "cargo.lock", "composer.lock", "gemfile.lock",
}

VENDOR_PARTS = {
    "node_modules", "vendor", "vendors", "third_party", "third-party",
    "site-packages", ".venv", "venv",
}

GENERATED_PARTS = {
    "dist", "build", "coverage", ".next", "generated", "fixtures",
    "snapshots", "translations", "locales",
}


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def _tracked_files(repo: Path) -> list[Path]:
    raw = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    return [repo / name.decode("utf-8", "surrogateescape") for name in raw.split(b"\0") if name]


def _classification(relative: Path) -> str:
    parts = {part.casefold() for part in relative.parts}
    name = relative.name.casefold()
    suffix = relative.suffix.casefold()
    if parts & VENDOR_PARTS:
        return "vendored_dependency"
    if (
        parts & GENERATED_PARTS
        or name in GENERATED_NAMES
        or name.endswith((".min.js", ".min.css", ".map"))
        or suffix in {".lock", ".sum"}
    ):
        return "generated_or_bulk_data"
    if suffix in CODE_EXTENSIONS:
        return "authorial_code"
    return "documentation_config_or_data"


def audit_repository(repo: Path) -> dict[str, Any]:
    files = _tracked_files(repo)
    classifications: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    extension_files: Counter[str] = Counter()
    extension_lines: Counter[str] = Counter()
    total_bytes = 0
    text_bytes = 0
    text_lines = 0
    binary_files = 0
    gitlink_files = 0
    symlink_files = 0
    duplicate_hashes: Counter[str] = Counter()
    coverage_digest = hashlib.sha256()

    for path in sorted(files, key=lambda item: item.relative_to(repo).as_posix()):
        relative = path.relative_to(repo)
        is_symlink = path.is_symlink()
        if is_symlink:
            data = os.readlink(path).encode("utf-8", "surrogateescape")
            symlink_files += 1
        elif path.is_dir():
            # Mode 160000: Git tracks the referenced commit, not the child
            # repository's worktree contents. Record that exact object ID.
            stage = _git(repo, "ls-files", "--stage", "--", relative.as_posix())
            object_id = stage.split(maxsplit=2)[1] if stage else "unknown"
            digest = hashlib.sha256(f"gitlink:{object_id}".encode("ascii", "replace")).hexdigest()
            gitlink_files += 1
            classifications["gitlink"] += 1
            extension_files["[gitlink]"] += 1
            coverage_digest.update(relative.as_posix().encode("utf-8", "surrogateescape"))
            coverage_digest.update(b"\0gitlink:")
            coverage_digest.update(object_id.encode("ascii", "replace"))
            coverage_digest.update(b"\n")
            duplicate_hashes[digest] += 1
            continue
        else:
            data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        duplicate_hashes[digest] += 1
        total_bytes += len(data)
        coverage_digest.update(relative.as_posix().encode("utf-8", "surrogateescape"))
        coverage_digest.update(b"\0")
        coverage_digest.update(digest.encode("ascii"))
        coverage_digest.update(b"\0")

        suffix = relative.suffix.casefold() or "[no extension]"
        extension_files[suffix] += 1
        is_binary = suffix in BINARY_EXTENSIONS or b"\0" in data[:8192]
        if is_binary:
            binary_files += 1
            coverage_digest.update(b"binary\n")
            continue

        # splitlines() counts the last unterminated line, matching what a
        # human/code reader sees rather than only newline bytes.
        lines = len(data.splitlines())
        text_lines += lines
        text_bytes += len(data)
        extension_lines[suffix] += lines
        classification = "symlink" if is_symlink else _classification(relative)
        classifications[classification] += 1
        coverage_digest.update(str(lines).encode("ascii"))
        coverage_digest.update(b"\n")
        language = CODE_EXTENSIONS.get(relative.suffix.casefold())
        if language:
            languages[language] += lines

    license_files = [
        path.relative_to(repo).as_posix()
        for path in files
        if path.name.casefold().startswith(("license", "copying", "notice"))
    ]
    duplicate_groups = sum(1 for count in duplicate_hashes.values() if count > 1)
    duplicate_files = sum(count - 1 for count in duplicate_hashes.values() if count > 1)
    try:
        origin = _git(repo, "remote", "get-url", "origin")
    except subprocess.CalledProcessError:
        origin = ""

    return {
        "repository": repo.name,
        "origin": origin,
        "revision": _git(repo, "rev-parse", "HEAD"),
        "coverage_sha256": coverage_digest.hexdigest(),
        "tracked_files": len(files),
        "text_files": len(files) - binary_files - gitlink_files,
        "binary_files": binary_files,
        "gitlink_files": gitlink_files,
        "symlink_files": symlink_files,
        "total_bytes": total_bytes,
        "text_bytes": text_bytes,
        "text_lines": text_lines,
        "classifications": dict(classifications.most_common()),
        "languages_by_lines": dict(languages.most_common()),
        "extensions_by_files": dict(extension_files.most_common()),
        "extensions_by_lines": dict(extension_lines.most_common()),
        "license_files": sorted(license_files),
        "exact_duplicate_groups": duplicate_groups,
        "exact_duplicate_files_beyond_first": duplicate_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Directory containing shallow repository clones")
    parser.add_argument("--output", type=Path, required=True, help="JSON manifest destination")
    args = parser.parse_args()

    repositories = sorted(
        path for path in args.root.iterdir()
        if path.is_dir() and (path / ".git").exists()
    )
    results = [audit_repository(repo) for repo in repositories]
    payload = {
        "schema_version": 1,
        "method": (
            "Every git-tracked file was read as bytes and SHA-256 hashed; every non-binary "
            "file was split line-by-line and counted. Generated, vendored and bulk-data "
            "material is classified separately from authorial code."
        ),
        "repositories": results,
        "totals": {
            key: sum(int(item[key]) for item in results)
            for key in ("tracked_files", "text_files", "binary_files", "total_bytes", "text_bytes", "text_lines")
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["totals"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
