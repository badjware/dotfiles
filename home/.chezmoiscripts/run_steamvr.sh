#!/bin/bash

VRCOMPOSITOR_LAUNCHER="$HOME/.local/share/Steam/steamapps/common/SteamVR/bin/linux64/vrcompositor-launcher"

# SteamVR updates replace the binary and drop the capability, so check on every apply
if [[ -f "$VRCOMPOSITOR_LAUNCHER" ]] && ! getcap "$VRCOMPOSITOR_LAUNCHER" | grep -q cap_sys_nice; then
    sudo setcap CAP_SYS_NICE+ep "$VRCOMPOSITOR_LAUNCHER"
fi
