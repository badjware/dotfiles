#!/bin/bash

source_image="${HOME}/.local/share/wallpaper"
colors_hex_file="/tmp/chezmoi-colors-hex.json"
background_rgb_file="/tmp/chezmoi-background-rgb.json"

background_to_rgb() {
    hex="$(cat "$colors_hex_file" | jq -r '.colors.background.default')"
    rgb_json=$(printf '{"r": %d,"g": %d,"b": %d}' \
        "$((16#${hex:1:2}))" \
        "$((16#${hex:3:2}))" \
        "$((16#${hex:5:2}))")
    echo "$rgb_json" >"$background_rgb_file"
}

if which matugen &>/dev/null; then
    colorscheme_json="$(matugen image --type scheme-fidelity --json hex "$source_image")"
    if [ -n "$colorscheme_json" ]; then
        echo "$colorscheme_json" >"$colors_hex_file"
        background_to_rgb
        exit
    fi
fi

# fallback
cat >"$colors_hex_file" <<EOF
{
  "colors": {
    "background": {
      "dark": "#1a120e",
      "default": "#1a120e",
      "light": "#fff8f6"
    },
    "error": {
      "dark": "#ffb4ab",
      "default": "#ffb4ab",
      "light": "#ba1a1a"
    },
    "error_container": {
      "dark": "#93000a",
      "default": "#93000a",
      "light": "#ffdad6"
    },
    "inverse_on_surface": {
      "dark": "#382e2a",
      "default": "#382e2a",
      "light": "#ffede6"
    },
    "inverse_primary": {
      "dark": "#8d4d2d",
      "default": "#8d4d2d",
      "light": "#ffb693"
    },
    "inverse_surface": {
      "dark": "#f0dfd8",
      "default": "#f0dfd8",
      "light": "#382e2a"
    },
    "on_background": {
      "dark": "#f0dfd8",
      "default": "#f0dfd8",
      "light": "#221a16"
    },
    "on_error": {
      "dark": "#690005",
      "default": "#690005",
      "light": "#ffffff"
    },
    "on_error_container": {
      "dark": "#ffdad6",
      "default": "#ffdad6",
      "light": "#410002"
    },
    "on_primary": {
      "dark": "#542104",
      "default": "#542104",
      "light": "#ffffff"
    },
    "on_primary_container": {
      "dark": "#ffdbcc",
      "default": "#ffdbcc",
      "light": "#351000"
    },
    "on_primary_fixed": {
      "dark": "#351000",
      "default": "#351000",
      "light": "#351000"
    },
    "on_primary_fixed_variant": {
      "dark": "#703718",
      "default": "#703718",
      "light": "#703718"
    },
    "on_secondary": {
      "dark": "#432a1e",
      "default": "#432a1e",
      "light": "#ffffff"
    },
    "on_secondary_container": {
      "dark": "#ffdbcc",
      "default": "#ffdbcc",
      "light": "#2c160b"
    },
    "on_secondary_fixed": {
      "dark": "#2c160b",
      "default": "#2c160b",
      "light": "#2c160b"
    },
    "on_secondary_fixed_variant": {
      "dark": "#5c4033",
      "default": "#5c4033",
      "light": "#5c4033"
    },
    "on_surface": {
      "dark": "#f0dfd8",
      "default": "#f0dfd8",
      "light": "#221a16"
    },
    "on_surface_variant": {
      "dark": "#d7c2b9",
      "default": "#d7c2b9",
      "light": "#52443d"
    },
    "on_tertiary": {
      "dark": "#363107",
      "default": "#363107",
      "light": "#ffffff"
    },
    "on_tertiary_container": {
      "dark": "#ede4a9",
      "default": "#ede4a9",
      "light": "#201c00"
    },
    "on_tertiary_fixed": {
      "dark": "#201c00",
      "default": "#201c00",
      "light": "#201c00"
    },
    "on_tertiary_fixed_variant": {
      "dark": "#4d481c",
      "default": "#4d481c",
      "light": "#4d481c"
    },
    "outline": {
      "dark": "#a08d85",
      "default": "#a08d85",
      "light": "#85736c"
    },
    "outline_variant": {
      "dark": "#52443d",
      "default": "#52443d",
      "light": "#d7c2b9"
    },
    "primary": {
      "dark": "#ffb693",
      "default": "#ffb693",
      "light": "#8d4d2d"
    },
    "primary_container": {
      "dark": "#703718",
      "default": "#703718",
      "light": "#ffdbcc"
    },
    "primary_fixed": {
      "dark": "#ffdbcc",
      "default": "#ffdbcc",
      "light": "#ffdbcc"
    },
    "primary_fixed_dim": {
      "dark": "#ffb693",
      "default": "#ffb693",
      "light": "#ffb693"
    },
    "scrim": {
      "dark": "#000000",
      "default": "#000000",
      "light": "#000000"
    },
    "secondary": {
      "dark": "#e6beac",
      "default": "#e6beac",
      "light": "#765749"
    },
    "secondary_container": {
      "dark": "#5c4033",
      "default": "#5c4033",
      "light": "#ffdbcc"
    },
    "secondary_fixed": {
      "dark": "#ffdbcc",
      "default": "#ffdbcc",
      "light": "#ffdbcc"
    },
    "secondary_fixed_dim": {
      "dark": "#e6beac",
      "default": "#e6beac",
      "light": "#e6beac"
    },
    "shadow": {
      "dark": "#000000",
      "default": "#000000",
      "light": "#000000"
    },
    "source_color": {
      "dark": "#f19c73",
      "default": "#f19c73",
      "light": "#f19c73"
    },
    "surface": {
      "dark": "#1a120e",
      "default": "#1a120e",
      "light": "#fff8f6"
    },
    "surface_bright": {
      "dark": "#423732",
      "default": "#423732",
      "light": "#fff8f6"
    },
    "surface_container": {
      "dark": "#271e1a",
      "default": "#271e1a",
      "light": "#fceae3"
    },
    "surface_container_high": {
      "dark": "#322824",
      "default": "#322824",
      "light": "#f6e5de"
    },
    "surface_container_highest": {
      "dark": "#3d332e",
      "default": "#3d332e",
      "light": "#f0dfd8"
    },
    "surface_container_low": {
      "dark": "#221a16",
      "default": "#221a16",
      "light": "#fff1eb"
    },
    "surface_container_lowest": {
      "dark": "#140c09",
      "default": "#140c09",
      "light": "#ffffff"
    },
    "surface_dim": {
      "dark": "#1a120e",
      "default": "#1a120e",
      "light": "#e8d6d0"
    },
    "surface_tint": {
      "dark": "#ffb693",
      "default": "#ffb693",
      "light": "#8d4d2d"
    },
    "surface_variant": {
      "dark": "#52443d",
      "default": "#52443d",
      "light": "#f4ded5"
    },
    "tertiary": {
      "dark": "#d1c88f",
      "default": "#d1c88f",
      "light": "#655f31"
    },
    "tertiary_container": {
      "dark": "#4d481c",
      "default": "#4d481c",
      "light": "#ede4a9"
    },
    "tertiary_fixed": {
      "dark": "#ede4a9",
      "default": "#ede4a9",
      "light": "#ede4a9"
    },
    "tertiary_fixed_dim": {
      "dark": "#d1c88f",
      "default": "#d1c88f",
      "light": "#d1c88f"
    }
  },
  "image": "",
  "is_dark_mode": true,
  "mode": "Dark",
  "palettes": {
    "error": {
      "0": "#000000",
      "10": "#410002",
      "100": "#ffffff",
      "15": "#540003",
      "20": "#690005",
      "25": "#7e0007",
      "30": "#93000a",
      "35": "#a80710",
      "40": "#ba1a1a",
      "5": "#2d0001",
      "50": "#de3730",
      "60": "#ff5449",
      "70": "#ff897d",
      "80": "#ffb4ab",
      "90": "#ffdad6",
      "95": "#ffedea",
      "98": "#fff8f7",
      "99": "#fffbff"
    },
    "neutral": {
      "0": "#000000",
      "10": "#201a18",
      "100": "#ffffff",
      "15": "#2b2422",
      "20": "#362f2c",
      "25": "#413a37",
      "30": "#4d4542",
      "35": "#59514d",
      "40": "#655d59",
      "5": "#15100d",
      "50": "#7f7571",
      "60": "#998f8b",
      "70": "#b4a9a5",
      "80": "#d0c4c0",
      "90": "#ede0db",
      "95": "#fbeee9",
      "98": "#fff8f6",
      "99": "#fffbff"
    },
    "neutral_variant": {
      "0": "#000000",
      "10": "#251914",
      "100": "#ffffff",
      "15": "#2f231d",
      "20": "#3b2e28",
      "25": "#463832",
      "30": "#52443d",
      "35": "#5f4f48",
      "40": "#6b5b54",
      "5": "#190e0a",
      "50": "#85736c",
      "60": "#a08d85",
      "70": "#bba79f",
      "80": "#d7c2b9",
      "90": "#f4ded5",
      "95": "#ffede6",
      "98": "#fff8f6",
      "99": "#fffbff"
    },
    "primary": {
      "0": "#000000",
      "10": "#351000",
      "100": "#ffffff",
      "15": "#451800",
      "20": "#561f00",
      "25": "#682700",
      "30": "#7a3001",
      "35": "#893b0d",
      "40": "#994719",
      "5": "#240900",
      "50": "#b85e2f",
      "60": "#d77746",
      "70": "#f8905d",
      "80": "#ffb693",
      "90": "#ffdbcc",
      "95": "#ffede6",
      "98": "#fff8f6",
      "99": "#fffbff"
    },
    "secondary": {
      "0": "#000000",
      "10": "#2c160b",
      "100": "#ffffff",
      "15": "#372015",
      "20": "#432a1e",
      "25": "#503529",
      "30": "#5c4033",
      "35": "#694c3e",
      "40": "#765749",
      "5": "#1f0c04",
      "50": "#917061",
      "60": "#ad8979",
      "70": "#c9a392",
      "80": "#e6beac",
      "90": "#ffdbcc",
      "95": "#ffede6",
      "98": "#fff8f6",
      "99": "#fffbff"
    },
    "tertiary": {
      "0": "#000000",
      "10": "#201c00",
      "100": "#ffffff",
      "15": "#2b2600",
      "20": "#363107",
      "25": "#413c11",
      "30": "#4d481c",
      "35": "#595326",
      "40": "#655f31",
      "5": "#141100",
      "50": "#7f7847",
      "60": "#99925e",
      "70": "#b5ac76",
      "80": "#d1c88f",
      "90": "#ede4a9",
      "95": "#fcf2b6",
      "98": "#fff9e8",
      "99": "#fffbff"
    }
  }
}
EOF
background_to_rgb