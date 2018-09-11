#!/bin/bash

if which openvpn &>/dev/null; then
    if ! pgrep "openvpn" &>/dev/null || ! ip link | grep -q tun; then
	    echo "$ICO_VPN_OFF "
    else
	    echo "$ICO_VPN_ON "
    fi
fi

