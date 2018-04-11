#!/bin/bash

# Set wallpaper
#wal -i "$(< "${HOME}/.cache/wal/wal")"

# Initial workspace and startup app
i3-msg "workspace 2"
i3-sensible-terminal &

# sleep a bit to allow polybar to fully load
sleep 3
nextcloud &
remmina --icon &
slack &
discord &

