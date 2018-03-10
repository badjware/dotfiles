#!/bin/bash

systemctl --user status redshift >/dev/null
redshift_status=$?

if [[ $1 = "toggle" ]]; then
	if [[ redshift_status -eq 0 ]]; then
		systemctl --user stop redshift &
		redshift_status=1
	else
		systemctl --user start redshift &
		redshift_status=0
	fi
fi

if [[ redshift_status -eq 0 ]]; then
	#temp="$(redshift -p | egrep -o '[0-9]+K$')"
	#echo "$STR_RED_ON $temp"
	echo "$ICO_RED_ON"
else
	#echo "$STR_RED_OFF ----k"
	echo "$ICO_RED_OFF"
fi

