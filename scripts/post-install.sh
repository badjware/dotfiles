#!/bin/bash

# install vim plugins
vim -E +"call dein#update()" +"qall!" /dev/null &>/dev/null 

systemctl --user enable mpv.service

