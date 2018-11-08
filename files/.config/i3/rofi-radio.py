#!/usr/bin/env python3
import json
import os
from subprocess import Popen, PIPE, check_output, check_call

import yaml


station_name_file = '/run/user/%s/rofi-radio-name' % os.getuid()

def mpv_ipc(*args):
    try:
        j = json.loads(check_output(['mpv-ipc'] + list(args)))
        if j:
            return j['data']
    except:
        pass
    return ''

with open(os.path.expanduser("~/.local/share/rofi-radio/playlists.yaml")) as f:
    stations = yaml.load(f)

rofi_command = ['rofi', '-i', '-selected-row', '0', '-dmenu', '-p', 'mpv']

current_song = mpv_ipc('get_property_string', 'media-title')
if current_song:
    try:
        with open(station_name_file) as f:
            station_name = f.readline()
    except:
        station_name = ''
    rofi_command += ['-mesg', station_name]
    commands = b"Play/Pause\nStop\nShuffle\nNext\nPrevious"

else:
    commands = bytes('\n'.join([s["name"] for s in stations]), 'utf8')

rofi = Popen(rofi_command, stdout=PIPE, stdin=PIPE)
choice = rofi.communicate(input=commands)[0].decode('utf8').rstrip()

if current_song:
    if choice == "Play/Pause":
        mpv_ipc('cycle', 'pause')
    elif choice == "Stop":
        mpv_ipc('stop')
    elif choice == "Shuffle":
        mpv_ipc('playlist-shuffle')
    elif choice == "Next":
        mpv_ipc('playlist-next')
    elif choice == "Previous":
        mpv_ipc('playlist-prev')
else:
    s = [s for s in stations if s["name"] == choice]
    if s:
        # Load the selected playlist
        loc = s[0]["loc"]
        station_name = s[0]["name"]
        if loc.startswith('http') or loc.startswith('ytdl'):
            # Load the url
            mpv_ipc('loadfile', loc)
        else:
            # Load the file
            workdir = mpv_ipc('get_property_string', 'working-directory')
            mpv_ipc('loadfile', os.path.expanduser(loc))
            station_name = loc
        with open(station_name_file, 'w') as f:
            f.write(station_name)
    else:
        # Try to load the user input
        mpv_ipc('loadfile', choice)
    mpv_ipc('set_property_string', 'pause', 'no')


# force update of i3status
check_call(['killall', '-USR1', 'i3status'])
