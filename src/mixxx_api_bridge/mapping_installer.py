"""Install the bundled Mixxx mapping as a user-level extension."""

from __future__ import annotations

import argparse
import importlib.resources as resources
import shutil
import sys
from pathlib import Path


MAPPING_FILES = ("MixxxApiBridge.midi.xml", "MixxxApiBridge-scripts.js")


def user_mapping_dir() -> Path:
    """Return Mixxx's per-user controller mapping directory."""

    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Mixxx" / "controllers"
    if sys.platform == "win32":
        return home / "AppData" / "Local" / "Mixxx" / "controllers"
    return home / ".mixxx" / "controllers"


def _resource_root():
    return resources.files("mixxx_api_bridge.mapping")


def install(
    destination: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> Path:
    """Copy mapping resources without touching the Mixxx application bundle."""

    target = destination or user_mapping_dir()
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
    root = _resource_root()
    for filename in MAPPING_FILES:
        source = root.joinpath(filename)
        target_file = target / filename
        content = source.read_bytes()
        if target_file.exists() and target_file.read_bytes() == content:
            print(f"unchanged {target_file}")
            continue
        if target_file.exists() and not force and not dry_run:
            raise FileExistsError(
                f"mapping already exists: {target_file}; use --force to replace it"
            )
        if dry_run:
            print(f"would copy {filename} -> {target_file}")
        else:
            target_file.write_bytes(content)
            print(f"copied {filename} -> {target_file}")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the Mixxx API Bridge user mapping")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        target = install(args.destination, args.dry_run, args.force)
    except (FileExistsError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"mapping directory: {target}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
