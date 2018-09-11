#!/bin/bash

if which rfkill &>/dev/null && [[ -f /dev/rfkill ]]; then
    if rfkill list bluetooth | grep "yes" >/dev/null; then
	    if [[ "$1" == "toggle"  ]]; then
		    rfkill unblock bluetooth
	    fi
	    echo "$ICO_BLU_OFF"
    else
	    if [[ "$1" == "toggle"  ]]; then
		    rfkill block bluetooth
	    fi
	    echo "$ICO_BLU_ON"
    fi
fi

