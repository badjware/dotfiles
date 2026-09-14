---
name: openscad
description: Creates parametric OpenSCAD models that explain mechanical mechanisms and spatial assemblies with color-coded parts, motion states, and animation. Use when a user needs a 3D visualization to understand pivots, cams, linkages, gears, enclosures, or clearances before production CAD.
version: 2
updated: "2026-09-01"
compatibility: "Requires python3 for structural validation. OpenSCAD renders geometry (STL) headless; PNG previews need either a display or an EGL-capable OpenSCAD build (2023+) for surfaceless offscreen rendering."
---

# OpenSCAD Visualizer

Create visualization-first OpenSCAD models that make geometry and motion understandable. Prefer a clear, adjustable conceptual assembly over production detail.

Only write or modify a model when the user explicitly asks to create, generate, or change one. For conceptual questions, explain or propose the model first.

## Workflow

1. Identify the motion or spatial relationship as a short chain, such as `rotation -> cam follower -> translation -> crank -> rotation`.
2. Inspect existing `.scad` files before adding another model. Preserve their parameter and naming conventions when modifying them.
3. Establish a coordinate system. Put the primary rotation axis at the origin when practical and state which axis each joint uses.
4. Separate every mechanically distinct component into a module. Keep stationary and moving components visibly distinct.
5. Define the desired output motion first, then derive follower, cam, and linkage motion from it. Do not shape a cam by visual guesswork when a displacement function can generate it.
6. Add visualization controls, motion states, and export selectors.
7. Validate the file using the process below.
8. Report the file path, important controls, assumptions, and validation status.

## Model structure

Organize generated files in this order:

```scad
$fn = 64;
eps = 0.01;  // boolean overlap so cutters clear their targets

// Output and visualization
part = "assembly";          // [assembly, frame, carrier, follower, output]
animate = false;
preview_position = 0;       // [0:1:2]
show_motion_envelope = false;

// Motion parameters
// Physical dimensions
// Clearances and placeholder dimensions
// Derived dimensions and assertions
// Motion functions
// Assembly module
// Individual component modules
// Reference geometry
// Output selection

echo("Motion chain: rotation -> cam -> lift");
echo("Envelope (mm):", [width, depth, height]);
```

Use descriptive parameter names and units in comments. Keep dimensions in millimeters and angles in degrees unless the user specifies otherwise.

Annotate user-facing parameters with Customizer comments so the values render as sliders and dropdowns and document their own ranges:

- `// [min:max]` numeric range
- `// [min:step:max]` numeric range with step
- `// [option_a, option_b]` dropdown of allowed values

Define `eps` once and reuse it for every `difference()` cutter so subtracted geometry extends past its target instead of leaving a coincident face.

End the file with `echo()` statements that report the motion chain and the key derived dimensions. The agent reads this from the OpenSCAD console during validation, which complements the assertions.

Use modules for physical components, and tag each with `// @feature: name` on the line above so later edits can target one module without disturbing the others:

```scad
// @feature: stationary_frame
module stationary_frame() { }
// @feature: rotating_carrier
module rotating_carrier() { }
// @feature: follower
module follower() { }
// @feature: output_link
module output_link() { }
// @feature: assembly
module assembly() { }
```

Do not create a single monolithic module when parts move relative to one another. Keep one feature per module so an edit stays local.

## Visualization requirements

A mechanism visualization should normally include:

- `part = "assembly"` plus selectors for major components
- `preview_position` or an equivalent manual motion parameter
- `animate` using `$t` when the mechanism has motion
- Distinct assembly colors for stationary structure, input, transmission, and output
- A simplified placeholder for contextual hardware such as a motor or servo
- Optional translucent motion envelopes for collision and range understanding
- Assertions for parameter combinations that would make the geometry impossible
- Comments that explain why a relationship exists, not a history of code changes

Keep colors in the assembly module so individual exported parts remain plain solids.

For a mechanism with meaningful stages, make representative positions easy to enter, such as start, engagement, midpoint, and end.

## Kinematic modeling

Model rigid parts and joints honestly:

- A slider moves only along its guide axis.
- A revolute component rotates around its hinge axis.
- A rigid curved rod cannot slide through a straight guide. Use a pivoted bell crank, pin-and-slot joint, articulated link, or flexible cable instead.
- Parts attached to the same rotating carrier must share the same parent transform.
- A cam and its follower need relative motion. Do not rotate both together unless another relative degree of freedom exists.
- Account for the arc followed by a crank endpoint. Add a slot or link where a linear slider would otherwise bind.

Use transformation hierarchy to express the assembly:

```scad
rotate([0, 0, input_angle]) {
    rotating_carrier();
    translate(slider_position) follower();
    translate(hinge_position)
        rotate([0, output_angle, 0]) output_link();
}
```

For cams, linkages, and staged motion, read [references/mechanism-patterns.md](references/mechanism-patterns.md).

## Parametric design rules

- Put user-facing parameters near the top.
- Calculate dependent dimensions instead of repeating constants.
- Use `assert()` for clearances, minimum link lengths, valid angle ranges, and noninterference constraints that can be expressed analytically.
- Clearly label servo bodies, fastener patterns, springs, bearings, and other unverified geometry as placeholders.
- Use realistic clearances only when the manufacturing method is known. Otherwise expose clearance as a parameter and state the assumption.
- Prefer primitives, `hull()`, `difference()`, `linear_extrude()`, and generated polygons over fragile hand-authored meshes.
- Use enough segments to explain curved motion without making previews unnecessarily slow.

## Scope control

A visualization is not automatically production-ready. Do not imply that it has validated:

- Material strength
- Servo or motor torque
- Fatigue life
- Print orientation or support requirements
- Fastener retention
- Hair, skin, or pinch-point safety
- Manufacturing tolerance stack-up

Include only enough construction detail to explain and test the mechanism. Add production features when the user asks for them.

## Validation

First check whether OpenSCAD is available:

```bash
command -v openscad
```

### Rendered visual validation (preferred)

Seeing the model is the point of a visualization skill. When OpenSCAD is available, render representative motion states to PNG and read each image to confirm the geometry and motion look right:

```bash
python3 scripts/render_views.py path/to/model.scad /tmp/openscad-views \
    --states "0,1,2" --view iso
```

Use the `read` tool on each generated PNG. Check across states for:

- Inverted or inside-out geometry
- Boolean operations that removed the wrong volume
- Parts that float, interpenetrate, or drift out of frame
- Motion that does not match the intended chain

Render the major components separately with `--parts "frame,carrier,follower"` when an assembled view hides a problem. Do not treat one successful state as proof that all states are collision-free.

PNG rendering needs an OpenGL context. With `$DISPLAY` set, the script uses it. Headless (no display, Wayland without Xwayland) requires an OpenSCAD build with EGL surfaceless offscreen support (2023+ or nightly), which renders through GBM with no X server and no Wayland socket. The script detects a GLX-only build (such as 2021.01) and stops with a clear message rather than crashing. Point it at a newer build with `OPENSCAD_BIN=/path/to/openscad`.

When PNG rendering is unavailable, still confirm the model compiles by exporting geometry, which works headless through CGAL:

```bash
openscad -o /tmp/openscad-check.stl path/to/model.scad
```

Read the `echo()` summary OpenSCAD prints during export to confirm the reported dimensions and motion chain match intent.

### Structural fallback (no OpenSCAD)

If OpenSCAD is unavailable, run the bundled structural checker from this skill directory:

```bash
python3 scripts/check_scad.py path/to/model.scad
```

The checker only catches unbalanced delimiters, unterminated strings/comments, and a few structural omissions. State clearly that the model was not rendered and that OpenSCAD syntax and manifold geometry remain unverified.

Never install OpenSCAD or another package. Ask the user to install missing software if rendered validation is required.

## Delivery

After creating a model, report:

1. The `.scad` path.
2. The motion chain represented.
3. The principal preview and animation controls.
4. The available part or view selectors.
5. Important placeholder dimensions or assumptions.
6. How it was validated: PNG previews read across motion states, a headless geometry export, or only the structural checker.

When explaining the result to a beginner, describe what remains stationary, what moves with the input, and how each stage transfers motion. Keep the model and explanation consistent.
