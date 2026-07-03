#!/usr/bin/env python3
"""Regenerate the default_config: requirements block in requirements.txt.

`configuration.yaml` uses `default_config:`, which loads ~55 Home Assistant
integrations (frontend, ffmpeg, usb, dhcp, bluetooth, matter, tts, camera...).
None of their Python dependencies are installed by `pip install homeassistant`
itself, so they must be tracked here manually. This script walks the
manifests of every integration reachable from default_config (following
dependencies and after_dependencies), collects their `requirements`, and
rewrites the generated block at the bottom of requirements.txt.

Run it whenever homeassistant is upgraded, then run scripts/setup to install
the result.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any

import homeassistant

Manifest = dict[str, Any]

MARKER = "# Requirements of default_config: integrations (frontend, ffmpeg, usb, dhcp, etc.)"

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"

# Components that default_config loads dynamically at runtime (e.g. via
# bluetooth adapter discovery) rather than declaring as a static manifest
# dependency. Their manifests aren't reachable by walking dependencies, so
# they're listed here explicitly.
EXTRA_COMPONENTS = {
    "esphome",  # pulled in by bluetooth for ESPHome bluetooth proxies
}


def find_components_dir() -> Path:
    """Locate the installed homeassistant.components package directory."""
    return Path(homeassistant.__file__).parent / "components"


def load_manifest(components_dir: Path, component: str) -> Manifest | None:
    """Load a component's manifest.json, or None if it has no manifest."""
    manifest_path = components_dir / component / "manifest.json"
    if not manifest_path.is_file():
        return None
    return json.loads(manifest_path.read_text())


def collect_components(components_dir: Path) -> set[str]:
    """Return every component reachable from default_config's dependency tree."""
    default_config_manifest = load_manifest(components_dir, "default_config")
    if default_config_manifest is None:
        msg = "Could not find homeassistant.components.default_config manifest"
        raise RuntimeError(msg)

    seen: set[str] = set()

    def expand(component: str) -> None:
        if component in seen:
            return
        seen.add(component)
        manifest = load_manifest(components_dir, component)
        if manifest is None:
            return
        for dep in manifest.get("dependencies", []) + manifest.get("after_dependencies", []):
            expand(dep)

    for dep in default_config_manifest.get("dependencies", []):
        expand(dep)
    for component in EXTRA_COMPONENTS:
        expand(component)

    return seen


def collect_requirements(components_dir: Path, components: set[str]) -> dict[str, str]:
    """Map each dependency's lowercased package name to its pinned requirement string."""
    requirements: dict[str, str] = {}
    for component in sorted(components):
        manifest = load_manifest(components_dir, component)
        if manifest is None:
            continue
        for req in manifest.get("requirements", []):
            pkg = re.split(r"[=<>!]", req, maxsplit=1)[0]
            requirements[pkg.lower()] = req
    return requirements


def rewrite_requirements_file(new_requirements: dict[str, str]) -> None:
    """Replace the generated requirements block, keeping the pinned base requirements above it."""
    text = REQUIREMENTS_FILE.read_text()
    marker_index = text.find(MARKER)
    base = text[:marker_index].rstrip("\n") if marker_index != -1 else text.rstrip("\n")

    block_lines = [MARKER] + [new_requirements[pkg] for pkg in sorted(new_requirements)]
    new_text = base + "\n\n" + "\n".join(block_lines) + "\n"
    REQUIREMENTS_FILE.write_text(new_text)


def main() -> int:
    """Regenerate requirements.txt's default_config requirements block."""
    components_dir = find_components_dir()
    components = collect_components(components_dir)
    requirements = collect_requirements(components_dir, components)
    rewrite_requirements_file(requirements)
    print(f"Updated {REQUIREMENTS_FILE} with {len(requirements)} default_config requirements.")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
