"""Safely clean local-only GPT2JSON build artifacts.

Default mode is dry-run.  The script never deletes source-controlled files and
refuses to remove paths outside the repository root.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from gpt2json import __version__

ROOT = Path(__file__).resolve().parents[1]

GENERATED_DIRS = (
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "gpt2json.egg-info",
    "packaging/windows/build",
)

CURRENT_RELEASE_ASSETS = {
    f"GPT2JSON-Setup-v{__version__}.exe",
    f"GPT2JSON-v{__version__}-windows-x64.zip",
    f"v{__version__}-notes.md",
}


def _is_inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return False
    return True


def _remove_path(path: Path, *, dry_run: bool) -> str:
    resolved = path.resolve()
    if not _is_inside_root(resolved):
        raise ValueError(f"refuse to remove path outside repository root: {resolved}")
    if not path.exists():
        return f"skip missing {path.relative_to(ROOT).as_posix()}"
    if dry_run:
        return f"would remove {path.relative_to(ROOT).as_posix()}"
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return f"removed {path.relative_to(ROOT).as_posix()}"


def iter_release_old_files(release_dir: Path | None = None) -> list[Path]:
    release_dir = release_dir or (ROOT / "release")
    if not release_dir.exists():
        return []
    return sorted(path for path in release_dir.iterdir() if path.is_file() and path.name not in CURRENT_RELEASE_ASSETS)


def clean_workspace(*, dry_run: bool = True, release_old: bool = False) -> list[str]:
    messages: list[str] = []
    for rel in GENERATED_DIRS:
        messages.append(_remove_path(ROOT / rel, dry_run=dry_run))
    if release_old:
        for path in iter_release_old_files():
            messages.append(_remove_path(path, dry_run=dry_run))
    return messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean local GPT2JSON build artifacts.")
    parser.add_argument("--apply", action="store_true", help="actually delete files; default is dry-run")
    parser.add_argument("--release-old", action="store_true", help="also remove old release assets, keeping current version only")
    args = parser.parse_args(argv)

    for message in clean_workspace(dry_run=not args.apply, release_old=args.release_old):
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
