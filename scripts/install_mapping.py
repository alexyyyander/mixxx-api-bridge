"""Compatibility wrapper for source-checkout installs."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mixxx_api_bridge.mapping_installer import (  # noqa: E402
    MAPPING_FILES as FILES,
    install,
    main,
    user_mapping_dir,
)

__all__ = ["FILES", "install", "main", "user_mapping_dir"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
