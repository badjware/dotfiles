#!/bin/bash

if which rfkill &>/dev/null && [[ -f /dev/rfkill ]]; then
    if rfkill list wifi | grep "yes" >/dev/null; then
        rfkill unblock wifi
    else
        rfkill block wifi
    fi
fi

