#!/bin/bash

INSTALL_DIR="$HOME/.vim/bundle/repos/github.com/Shougo/dein.vim"

if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$(dirname $INSTALL_DIR)" || true
    git clone https://github.com/Shougo/dein.vim "$INSTALL_DIR"
fi
