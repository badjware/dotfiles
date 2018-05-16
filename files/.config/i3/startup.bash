#!/bin/bash

# Set wallpaper
#wal -i "$(< "${HOME}/.cache/wal/wal")"

# Initial workspace and startup app
i3-msg "workspace 2"
uxterm -e "center-float && $SHELL -l" &

# sleep a bit to allow polybar to fully load
sleep 3
nextcloud &
remmina --icon &
slack &
discord &

