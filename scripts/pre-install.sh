#!/bin/bash

fix_permissions() {
    chown -R "$(id --name -u):$(id --name -g)" "$1"
    find "$1" -type d -exec chmod 700 {} \;
    find "$1" -type f -exec chmod 600 {} \;
}

for d in "$HOME/.ssh" "$HOME/.gnupg"; do
    mkdir -p "$d"
    fix_permissions "$d"
done

