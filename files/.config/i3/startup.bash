#!/bin/bash

# Set wallpaper
$HOME/.fehbg || feh --bg-fill --no-xinerama /usr/share/pixmaps/wallpaper.jpg

# Initial workspace and startup app
i3-msg "workspace 2"
i3-sensible-terminal

