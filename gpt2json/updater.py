from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

GITHUB_OWNER = "AyeSt0"
GITHUB_REPO = "gpt2json"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"


@dataclass(frozen=True)
class ReleaseInfo:
    current_version: str
    latest_version: str = ""
    tag_name: str = ""
    name: str = ""
    html_url: str = RELEASES_PAGE_URL
    published_at: str = ""
    update_available: bool = False
    has_release: bool = False
    assets: tuple[str, ...] = ()
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_version(value: str) -> str:
    version = str(value or "").strip()
    version = version[1:] if version.lower().startswith("v") else version
    return version.strip()


def _version_key(value: str) -> tuple[tuple[int, ...], bool]:
    version = normalize_version(value)
    main = re.split(r"[-+]", version, maxsplit=1)[0]
    numbers = tuple(int(part) for part in re.findall(r"\d+", main))
    is_prerelease = "-" in version
    return numbers, is_prerelease


def is_newer_version(latest: str, current: str) -> bool:
    latest_nums, latest_pre = _version_key(latest)
    current_nums, current_pre = _version_key(current)
    width = max(len(latest_nums), len(current_nums), 1)
    latest_nums = latest_nums + (0,) * (width - len(latest_nums))
    current_nums = current_nums + (0,) * (width - len(current_nums))
    if latest_nums != current_nums:
        return latest_nums > current_nums
    return current_pre and not latest_pre


def check_latest_release(current_version: str, *, timeout: int = 6) -> ReleaseInfo:
    req = urllib.request.Request(
        RELEASES_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"GPT2JSON/{normalize_version(current_version)}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ReleaseInfo(current_version=current_version, error="GitHub 上暂时还没有可用 Release。")
        return ReleaseInfo(current_version=current_version, error=f"GitHub API 返回 {exc.code}。")
    except Exception as exc:
        return ReleaseInfo(current_version=current_version, error=f"{type(exc).__name__}: {exc}")

    tag_name = str(payload.get("tag_name") or "").strip()
    latest_version = normalize_version(tag_name)
    assets = tuple(str(asset.get("name") or "") for asset in payload.get("assets") or [] if asset.get("name"))
    return ReleaseInfo(
        current_version=normalize_version(current_version),
        latest_version=latest_version,
        tag_name=tag_name,
        name=str(payload.get("name") or tag_name or latest_version),
        html_url=str(payload.get("html_url") or RELEASES_PAGE_URL),
        published_at=str(payload.get("published_at") or ""),
        update_available=is_newer_version(latest_version, current_version) if latest_version else False,
        has_release=bool(tag_name),
        assets=assets,
    )
