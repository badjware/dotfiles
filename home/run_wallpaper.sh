#!/bin/bash
if [[ ! -e "$HOME/.local/share/wallpaper" ]]; then
    curl -o $HOME/.local/share/wallpaper https://badjware.dev/public/wallpaper
fi