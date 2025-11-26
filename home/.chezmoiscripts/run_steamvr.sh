#!/bin/bash

VRCOMPOSITOR_LAUNCHER="./.local/share/Steam/steamapps/common/SteamVR/bin/linux64/vrcompositor-launcher"


if [[ -f "$VRCOMPOSITOR_LAUNCHER" ]]; then
    sudo setcap CAP_SYS_NICE+ep "$VRCOMPOSITOR_LAUNCHER"
fi
