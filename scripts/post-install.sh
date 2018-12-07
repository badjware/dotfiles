#!/bin/bash

# run units
systemctl --user daemon-reload
systemctl --user enable --now tmux.service
systemctl --user enable --now mpv.service

# install tmux plugins
tmux run-shell ~/.tmux/plugins/tpm/bin/install_plugins
tmux run-shell ~/.tmux/plugins/tpm/bin/clean_plugins

# install vim plugins
vim -E +"call dein#update()" +"qall!" /dev/null &>/dev/null 

