# OpenSCAD mechanism patterns

Use these patterns when the model contains staged motion, cams, sliders, or cranks.

## Smooth staged motion

For motion that starts at `start_angle` and ends at `end_angle`, normalize the active interval:

```scad
function clamp(x, low, high) = min(max(x, low), high);
function smoothstep(u) = u * u * (3 - 2 * u);

function progress_at(angle) = smoothstep(clamp(
    (angle - start_angle) / (end_angle - start_angle),
    0,
    1
));

function output_angle_at(angle) = maximum_output_angle * progress_at(angle);
```

The cubic smoothstep starts and ends with zero slope, which avoids an abrupt visual impact at engagement and full travel.

## Animation and manual preview

```scad
animate = false;
preview_input_angle = 0;
maximum_input_angle = 120;

shown_input_angle = animate
    ? maximum_input_angle * $t
    : min(max(preview_input_angle, 0), maximum_input_angle);
```

Keep the manual control available even when animation exists. It makes specific states reproducible.

## Horizontal face cam producing vertical lift

For a horizontal cam whose follower moves vertically, define cam height from the required follower displacement:

```scad
function lift_at(angle) = maximum_lift * progress_at(angle);
```

Generate the annular cam from angular segments with top heights at each segment boundary. Use a stationary cam and place the follower under the rotating carrier.

If a fixed vertical follower contacts the underside of a straight crank at horizontal offset `d`, the exact idealized lift is:

```text
lift = d * tan(output_angle)
```

This assumes the contact can slide along the crank. Ensure the crank extends at least:

```text
minimum crank length = d / cos(maximum output angle)
```

## Vertical radial cam producing horizontal travel

For a cam with a vertical outer wall, vary radius instead of height:

```scad
function radial_travel_at(angle) = maximum_travel * progress_at(angle);
function cam_radius_at(angle) = base_radius + radial_travel_at(angle);

function polar_point(radius, angle) =
    [radius * cos(angle), radius * sin(angle)];

linear_extrude(height=cam_height)
    polygon(points=[
        for (i = [0 : cam_segments - 1])
            let(a = i * 360 / cam_segments)
                polar_point(cam_radius_at(a), a)
    ]);
```

Subtract a central bore if a rotating shaft or hub must pass through the stationary cam.

For a fixed-height slider pin in a longitudinal slot on a crank, where `d` is the vertical distance from hinge to pin:

```text
radial travel = d * tan(output angle)
```

The slot must reach at least:

```text
slot distance at maximum tilt = d / cos(maximum output angle)
```

## Articulated crank endpoint

If a connecting link follows the actual endpoint of a crank of length `L`, its displacement components relative to a vertical starting crank are:

```text
horizontal displacement = L * sin(output angle)
vertical displacement   = L * (1 - cos(output angle))
```

A strictly horizontal slider cannot follow both components without a slot, a second pivoting link, or another degree of freedom.

## Cam return sector

A full 360-degree cam should have a continuous profile even if the mechanism operates over only part of it. After the operating sector, return smoothly to the base value:

```scad
function cam_value_at(a) =
    a <= start_angle ? 0 :
    a <= end_angle ? maximum_value * progress_at(a) :
    a <= return_end_angle
        ? maximum_value * (1 - smoothstep(
            (a - end_angle) / (return_end_angle - end_angle)
        )) :
    0;
```

State that the return sector is outside normal operation. Add physical stops when a follower could leave a partial cam sector.

## Motion envelopes

A translucent set of sampled positions can reveal the occupied volume:

```scad
module motion_envelope() {
    color([0.9, 0.2, 0.2, 0.12])
        for (a = [0 : 10 : maximum_input_angle])
            rotate([0, 0, a])
                moving_output_at(a);
}
```

Keep this disabled by default because overlapping transparent geometry can slow preview.

## Exploded views

Use a scalar separation parameter so the same modules produce assembled and exploded states:

```scad
exploded = false;
explode_distance = exploded ? 12 : 0;

stationary_frame();
translate([0, 0, explode_distance]) cam();
translate([0, 0, 2 * explode_distance]) carrier();
```

An exploded view should clarify the stack without changing part orientation.

## Useful assertions

```scad
assert(end_angle > start_angle,
    "end_angle must exceed start_angle");
assert(inner_radius > hub_radius + radial_clearance,
    "stationary cam must clear the rotating hub");
assert(track_width > follower_diameter,
    "cam track must be wider than the follower");
assert(crank_length >= required_contact_distance,
    "crank is too short at maximum output angle");
```

Assertions should explain the violated physical relationship and identify the parameter the user can adjust.
