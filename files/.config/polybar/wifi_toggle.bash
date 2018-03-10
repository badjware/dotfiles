#!/bin/bash

if rfkill list wifi | grep "yes" >/dev/null; then
    rfkill unblock wifi
else
    rfkill block wifi
fi

