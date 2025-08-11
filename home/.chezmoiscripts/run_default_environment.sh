#!/bin/bash

import-gsettings

xdg-settings set default-web-browser firefox.desktop

xdg-mime default thunar.desktop inode/directory