#!/bin/bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

git clone  https://github.com/zdharma-continuum/fast-syntax-highlighting $HOME/.config/zsh/custom/plugins/fast-syntax-highlighting
