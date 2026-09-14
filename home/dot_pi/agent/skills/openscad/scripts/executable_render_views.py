#!/usr/bin/env python3
"""Render OpenSCAD motion states or part views to PNG for visual validation.

Usage:
    render_views.py MODEL.scad OUT_DIR [options]

Options:
    --param NAME        Parameter varied across states (default: preview_position).
    --states "a,b,c"    Comma-separated values for that parameter (default: none, one render).
    --parts "x,y"       Comma-separated values for the "part" selector (default: none).
    --view NAME         Camera preset: iso (default), front, top, right.
    --size WxH          Image size (default: 900x675).
    -D name=value       Extra OpenSCAD variable override, repeatable.

Renders one PNG per state (and per part) into OUT_DIR, then prints the paths
so the agent can read the images and confirm the geometry and motion.
Renders via a display when present, or headless through EGL surfaceless
offscreen on OpenSCAD 2023+ builds (no X, no Wayland socket). STL export is
always headless; set OPENSCAD_BIN to a newer build if PNG rendering is refused.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

VIEW_ROTATIONS = {
    "iso": "55,0,25",
    "front": "90,0,0",
    "top": "0,0,0",
    "right": "90,0,90",
}

LOG_PATH = Path("/tmp/render_views.log")


def die(message: str, code: int = 1) -> None:
    """Print an error to stderr and exit with the given status code."""
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def split_list(value: str) -> list[str]:
    """Split a comma-separated string, returning [""] when empty.

    The single empty element makes the render loops run exactly once when no
    states or parts are requested.
    """
    if not value:
        return [""]
    return value.split(",")


def links_egl(openscad_path: str) -> bool:
    """Return True if the OpenSCAD binary links libEGL for headless offscreen rendering."""
    try:
        output = subprocess.run(
            ["ldd", openscad_path],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        return False
    return "libegl" in output.lower()


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments into a namespace."""
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument("model", help="path to the .scad model")
    parser.add_argument("out_dir", help="directory for rendered PNGs")
    parser.add_argument("--param", default="preview_position",
                        help="parameter varied across states")
    parser.add_argument("--states", default="",
                        help="comma-separated values for the varied parameter")
    parser.add_argument("--parts", default="",
                        help="comma-separated values for the part selector")
    parser.add_argument("--view", default="iso", choices=sorted(VIEW_ROTATIONS),
                        help="camera preset")
    parser.add_argument("--size", default="900x675", help="image size WxH")
    parser.add_argument("-D", dest="defs", action="append", default=[],
                        metavar="name=value", help="extra OpenSCAD override, repeatable")
    return parser.parse_args(argv)


def render_one(openscad_bin: str, out: Path, camera: str, imgsize: str,
               defs: list[str], model: str) -> bool:
    """Render a single PNG and return True on success.

    OpenSCAD can exit 0 yet leave a 0-byte file when GL init fails silently, so
    a nonempty output file is also required.
    """
    command = [openscad_bin, "-o", str(out), f"--imgsize={imgsize}",
               f"--camera={camera}", "--viewall", "--autocenter"]
    for override in defs:
        command += ["-D", override]
    command.append(model)

    with LOG_PATH.open("w", encoding="utf-8") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        return False
    return out.is_file() and out.stat().st_size > 0


def main() -> None:
    args = parse_args(sys.argv[1:])

    openscad_bin = os.environ.get("OPENSCAD_BIN", "openscad")
    openscad_path = shutil.which(openscad_bin)
    if openscad_path is None:
        die("openscad not found. Install it or set OPENSCAD_BIN.")

    model = args.model
    if not Path(model).is_file():
        die(f"model not found: {model}")
    if Path(model).suffix.lower() != ".scad":
        die(f"expected an .scad file: {model}")

    # Camera presets use the rotation form: transx,transy,transz,rotx,roty,rotz,dist.
    # Distance 0 with --viewall lets OpenSCAD frame the model automatically.
    camera = f"0,0,0,{VIEW_ROTATIONS[args.view]},0"
    imgsize = args.size.replace("x", ",")

    # PNG rendering needs an OpenGL context. With a display, OpenSCAD uses it.
    # Without one, headless rendering requires a build with EGL surfaceless
    # offscreen support (OpenSCAD 2023+). GLX-only builds such as 2021.01 segfault
    # instead of failing cleanly, so detect and refuse them up front.
    if not os.environ.get("DISPLAY") and not links_egl(openscad_path):
        print("ERROR: no display and this OpenSCAD build cannot render headless.", file=sys.stderr)
        print("The binary links GLX/X11 but not EGL, so offscreen rendering needs an X server.", file=sys.stderr)
        print("Install an EGL-capable build (OpenSCAD 2023+ or nightly) and set OPENSCAD_BIN.", file=sys.stderr)
        print("STL export via 'openscad -o out.stl model.scad' still works headless.", file=sys.stderr)
        raise SystemExit(2)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = Path(model).stem

    rendered: list[Path] = []
    failed = False

    for part in split_list(args.parts):
        part_defs = [f'part="{part}"'] if part else []
        part_tag = f"_{part}" if part else ""
        for state in split_list(args.states):
            state_defs = [f"{args.param}={state}"] if state else []
            state_tag = f"_{args.param}{state}" if state else ""
            out = out_dir / f"{base}{part_tag}{state_tag}.png"
            defs = args.defs + part_defs + state_defs
            if not render_one(openscad_bin, out, camera, imgsize, defs, model):
                failed = True
            else:
                rendered.append(out)

    if failed:
        print("WARNING: at least one render failed. Last OpenSCAD output:", file=sys.stderr)
        if LOG_PATH.is_file():
            tail = LOG_PATH.read_text(encoding="utf-8").splitlines()[-5:]
            for line in tail:
                print(line, file=sys.stderr)
        print("PNG rendering needs a display or an EGL-capable OpenSCAD build (2023+).", file=sys.stderr)
        print("STL export via 'openscad -o out.stl model.scad' works without a display.", file=sys.stderr)

    if not rendered:
        die("no images were produced")

    print(f"Rendered {len(rendered)} image(s):")
    for path in rendered:
        print(f"  {path}")
    print("Read each PNG to confirm the geometry and motion look correct.")


if __name__ == "__main__":
    main()
