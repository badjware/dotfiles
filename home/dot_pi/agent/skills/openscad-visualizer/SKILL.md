---
name: openscad-visualizer
description: Creates parametric OpenSCAD models that explain mechanical mechanisms and spatial assemblies with color-coded parts, adjustable dimensions, motion states, animation, motion envelopes, and individual-part views. Use when a user needs a 3D visualization to understand pivots, cams, linkages, sliders, gears, enclosures, clearances, or how moving components interact before detailed production CAD.
version: 1
updated: "2026-09-01"
compatibility: "Requires python3 for structural validation. OpenSCAD is optional for rendered validation."
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

// Output and visualization
part = "assembly";
animate = false;
preview_position = 0;
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
```

Use descriptive parameter names and units in comments. Keep dimensions in millimeters and angles in degrees unless the user specifies otherwise.

Use modules for physical components, for example:

```scad
module stationary_frame() { }
module rotating_carrier() { }
module follower() { }
module output_link() { }
module assembly() { }
```

Do not create a single monolithic module when parts move relative to one another.

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

If it is available, render the model to a temporary file and inspect errors:

```bash
openscad -o /tmp/openscad-visualizer-check.stl path/to/model.scad
```

Render representative motion states when command-line parameter overrides are practical. Do not treat one successful state as proof that all states are collision-free.

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
6. Whether OpenSCAD rendered it or only the structural checker passed.

When explaining the result to a beginner, describe what remains stationary, what moves with the input, and how each stage transfers motion. Keep the model and explanation consistent.
