#!/usr/bin/env python3
"""Perform lightweight structural checks on an OpenSCAD source file."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PAIRS = {")": "(", "]": "[", "}": "{"}
OPENERS = set(PAIRS.values())


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_delimiters(source: str) -> None:
    stack: list[tuple[str, int]] = []
    in_string = False
    escaped = False
    index = 0

    while index < len(source):
        char = source[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            index += 1
            continue

        if source.startswith("//", index):
            newline = source.find("\n", index)
            index = len(source) if newline < 0 else newline
            continue

        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                fail(f"unterminated block comment at byte {index}")
            index = end + 2
            continue

        if char in OPENERS:
            stack.append((char, index))
        elif char in PAIRS:
            if not stack:
                fail(f"unexpected '{char}' at byte {index}")
            opener, opener_index = stack.pop()
            if opener != PAIRS[char]:
                fail(
                    f"'{opener}' at byte {opener_index} is closed by "
                    f"'{char}' at byte {index}"
                )

        index += 1

    if in_string:
        fail("unterminated string")
    if stack:
        opener, opener_index = stack[-1]
        fail(f"unclosed '{opener}' at byte {opener_index}")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: check_scad.py path/to/model.scad")

    path = Path(sys.argv[1])
    if path.suffix.lower() != ".scad":
        fail(f"expected an .scad file: {path}")
    if not path.is_file():
        fail(f"file not found: {path}")

    source = path.read_text(encoding="utf-8")
    check_delimiters(source)

    warnings: list[str] = []
    if not re.search(r"\bmodule\s+[A-Za-z_][A-Za-z0-9_]*\s*\(", source):
        warnings.append("no module declarations found")
    if "assembly" not in source.lower():
        warnings.append("no assembly view appears to be defined")
    if "$t" not in source:
        warnings.append("no $t animation control found")
    if "assert(" not in source:
        warnings.append("no parameter assertions found")

    print(f"Structural check passed: {path} ({len(source.splitlines())} lines)")
    for warning in warnings:
        print(f"WARNING: {warning}")
    print("This is not an OpenSCAD syntax, render, or manifold check.")


if __name__ == "__main__":
    main()
