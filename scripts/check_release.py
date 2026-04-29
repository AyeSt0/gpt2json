"""Release sanity checks for GPT2JSON.

This script intentionally avoids importing GUI modules so it can run in headless
CI and on developer machines before tagging a release.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "gpt2json" / "__init__.py"
INNO_FILE = ROOT / "packaging" / "windows" / "GPT2JSON.iss"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
RELEASE_DIR = ROOT / "release"

EXPECTED_RELEASE_PATTERNS = (
    "GPT2JSON-Setup-v{version}.exe",
    "GPT2JSON-v{version}-windows-x64.zip",
)


def read_package_version(path: Path = INIT_FILE) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    raise ValueError(f"Could not find string __version__ in {path}")


def read_inno_version(path: Path = INNO_FILE) -> str:
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(r'^\s*#define\s+MyAppVersion\s+"([^"]+)"\s*$', text, re.MULTILINE)
    if not match:
        raise ValueError(f"Could not find #define MyAppVersion in {path}")
    return match.group(1)


def changelog_has_version(version: str, path: Path = CHANGELOG_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    pattern = rf"^##\s+\[{re.escape(version)}\](?:\s+-\s+\d{{4}}-\d{{2}}-\d{{2}})?\s*$"
    return re.search(pattern, text, re.MULTILINE) is not None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_release_assets(version: str, release_dir: Path = RELEASE_DIR) -> list[Path]:
    return [release_dir / pattern.format(version=version) for pattern in EXPECTED_RELEASE_PATTERNS]


def matching_release_assets(version: str, release_dir: Path = RELEASE_DIR) -> list[Path]:
    if not release_dir.exists():
        return []
    patterns = (
        f"*{version}*",
        f"*v{version}*",
    )
    seen: dict[Path, None] = {}
    for pattern in patterns:
        for path in release_dir.glob(pattern):
            if path.is_file():
                seen[path] = None
    return sorted(seen)


def run_checks(require_assets: bool = False) -> int:
    failures: list[str] = []

    package_version = read_package_version()
    inno_version = read_inno_version()
    print(f"package version: {package_version}")
    print(f"installer version: {inno_version}")

    if package_version != inno_version:
        failures.append(
            f"Version mismatch: gpt2json.__version__={package_version!r}, "
            f"packaging/windows/GPT2JSON.iss MyAppVersion={inno_version!r}"
        )
    else:
        print("OK: package and installer versions match")

    if changelog_has_version(package_version):
        print(f"OK: CHANGELOG.md contains heading for [{package_version}]")
    else:
        failures.append(f"CHANGELOG.md does not contain a heading for [{package_version}]")

    expected_assets = expected_release_assets(package_version)
    existing_expected = [path for path in expected_assets if path.exists()]
    missing_expected = [path.name for path in expected_assets if not path.exists()]
    assets_to_hash = existing_expected or matching_release_assets(package_version)

    if assets_to_hash:
        print("SHA256 release assets:")
        for path in assets_to_hash:
            print(f"  {sha256_file(path)}  {path.relative_to(ROOT).as_posix()}")
    else:
        print(f"WARN: no release assets found for version {package_version} in {RELEASE_DIR.relative_to(ROOT)}")

    if missing_expected:
        message = "Missing expected release assets: " + ", ".join(missing_expected)
        if require_assets:
            failures.append(message)
        else:
            print("WARN: " + message)

    if failures:
        print("\nRelease check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("OK: release metadata checks passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GPT2JSON release metadata and print asset SHA256 sums.")
    parser.add_argument(
        "--require-assets",
        action="store_true",
        help="fail if any expected release asset for the current version is missing",
    )
    args = parser.parse_args(argv)
    return run_checks(require_assets=args.require_assets)


if __name__ == "__main__":
    raise SystemExit(main())
