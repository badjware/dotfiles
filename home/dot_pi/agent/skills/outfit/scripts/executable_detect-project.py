#!/usr/bin/env python3
"""Detect whether the cwd is a greenfield project, an existing project, or an
in-progress outfit run.

Output (text to stdout):
  kind: greenfield | existing | in-progress
  signals:
    - <signal>
    - ...

Detection rules (deterministic):
  1. If `.plan/` exists in the target dir, kind = in-progress.
  2. Else, scan for existing-project markers (see EXISTING_FILES, EXISTING_DIRS,
     and the README.md non-triviality check). Any match → kind = existing.
  3. Otherwise → kind = greenfield.

`.git/` alone is *not* a signal (the user may have inited from a remote).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Manifest / build files that strongly suggest an existing project.
EXISTING_FILES = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "mix.exs",
    "Package.swift",
    "Makefile",
    "CMakeLists.txt",
    "meson.build",
]

# Source directories considered a signal only if they contain at least one file.
EXISTING_DIRS = ["src", "lib", "app", "cmd", "pkg", "internal"]

README_MIN_CHARS = 200
README_MIN_NONBLANK_LINES = 10


def has_content(d: Path) -> bool:
    if not d.is_dir():
        return False
    for _ in d.rglob("*"):
        if _.is_file():
            return True
    return False


def readme_is_nontrivial(root: Path) -> bool:
    for name in ("README.md", "README.rst", "README.txt", "README"):
        p = root / name
        if not p.is_file():
            continue
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        if len(text) >= README_MIN_CHARS:
            return True
        nonblank = sum(1 for line in text.splitlines() if line.strip())
        if nonblank >= README_MIN_NONBLANK_LINES:
            return True
    return False


def detect(root: Path) -> tuple[str, list[str]]:
    signals: list[str] = []
    if (root / ".plan").is_dir():
        signals.append(".plan/")
        return "in-progress", signals
    for f in EXISTING_FILES:
        if (root / f).is_file():
            signals.append(f)
    for d in EXISTING_DIRS:
        if has_content(root / d):
            signals.append(f"{d}/ (non-empty)")
    if readme_is_nontrivial(root):
        signals.append("README (non-trivial)")
    if signals:
        return "existing", signals
    return "greenfield", []


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dir", default=".", help="project directory (default: cwd)")
    args = ap.parse_args()

    root = Path(args.dir).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 1

    kind, signals = detect(root)
    print(f"kind: {kind}")
    if signals:
        print("signals:")
        for s in signals:
            print(f"  - {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
