#!/bin/bash

# run units
systemctl --user daemon-reload
systemctl --user enable --now redshift.service
systemctl --user enable --now swayidle.service
systemctl --user enable --now wob.service
systemctl --user enable --now mako.service

# install tmux plugins
tmux run-shell ~/.tmux/plugins/tpm/bin/install_plugins
tmux run-shell ~/.tmux/plugins/tpm/bin/clean_plugins

# install vim plugins
vim -E +"call dein#update()" +"qall!" /dev/null &>/dev/null 

