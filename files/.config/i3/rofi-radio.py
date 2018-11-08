#!/usr/bin/env python3
import json
import yaml
import os
import sys

from subprocess import Popen, PIPE, check_output, check_call

def mpv_ipc(*args):
    try:
        j = json.loads(check_output(['mpv-ipc'] + list(args)))
        if j:
            return j['data']
    except:
        pass
    return ''

with open(os.path.expanduser("~/.local/share/playlists.yaml")) as y:
    stations = yaml.load(y)

rofi_command = ['rofi', '-i', '-selected-row', '0', '-dmenu', '-p', 'mpv']

current_song = mpv_ipc('get_property_string', 'media-title')
if current_song:
    rofi_command += ['-mesg', current_song]
    commands = b"Play/Pause\nStop\nNext\nPrevious"
else:
    commands = bytes('\n'.join([s["name"] for s in stations]), 'utf8')

rofi = Popen(rofi_command, stdout=PIPE, stdin=PIPE)
choice = rofi.communicate(input=commands)[0].decode('utf8').rstrip()

if current_song:
    if choice == "Play/Pause":
        mpv_ipc('cycle', 'pause')
    elif choice == "Stop":
        mpv_ipc('stop')
else:
    s = [s for s in stations if s["name"] == choice]
    if s:
        mpv_ipc('loadfile', s[0]["loc"])
        mpv_ipc('set_property_string', 'pause', 'no')

# force update of i3status
check_call('killall', '-USR1', 'i3status')

