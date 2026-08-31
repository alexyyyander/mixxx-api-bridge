"""Read-only Mixxx process discovery for the sidecar."""

from __future__ import annotations

import plistlib
import csv
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MixxxProcessInfo:
    running: bool
    pid: int | None = None
    executable: str | None = None
    bundle_path: str | None = None
    version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class MixxxDiscovery:
    """Detect Mixxx without using UI automation or changing app state."""

    def detect(self) -> MixxxProcessInfo:
        if os.name == "nt":
            return self._detect_windows()
        return self._detect_posix()

    def _detect_posix(self) -> MixxxProcessInfo:
        try:
            result = subprocess.run(
                ["ps", "-axo", "pid=,command="],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return MixxxProcessInfo(False)

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            pid_text, _, command = line.partition(" ")
            if not pid_text.isdigit():
                continue
            try:
                executable = shlex.split(command)[0]
            except (IndexError, ValueError):
                continue
            if Path(executable).name.lower() != "mixxx":
                continue
            bundle_path = self._bundle_path(executable)
            return MixxxProcessInfo(
                running=True,
                pid=int(pid_text),
                executable=executable,
                bundle_path=str(bundle_path) if bundle_path else None,
                version=self._read_version(bundle_path) if bundle_path else None,
            )
        return MixxxProcessInfo(False)

    def _detect_windows(self) -> MixxxProcessInfo:
        try:
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return MixxxProcessInfo(False)

        for row in csv.reader(result.stdout.splitlines()):
            if len(row) < 2 or row[0].lower() != "mixxx.exe" or not row[1].isdigit():
                continue
            return MixxxProcessInfo(
                running=True,
                pid=int(row[1]),
                executable="Mixxx.exe",
            )
        return MixxxProcessInfo(False)

    @staticmethod
    def _bundle_path(executable: str) -> Path | None:
        marker = "/Contents/MacOS/Mixxx"
        if marker in executable:
            return Path(executable.split(marker, 1)[0])
        return None

    @staticmethod
    def _read_version(bundle_path: Path) -> str | None:
        plist_path = bundle_path / "Contents" / "Info.plist"
        try:
            with plist_path.open("rb") as handle:
                data = plistlib.load(handle)
        except (OSError, plistlib.InvalidFileException, ValueError):
            return None
        value = data.get("CFBundleShortVersionString") or data.get("CFBundleVersion")
        return str(value) if value is not None else None
