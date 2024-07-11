#!/usr/bin/env sh
typeit=0
action=show
while
	case $1 in
	"--type") typeit=1 ;;
	"--action"|"-a") action="$2" ;;
	esac
	[ $# -ne 0 ]
do shift; done

prefix=${PASSWORD_STORE_DIR:-~/.password-store}

password=$(
	find "$prefix" -iname '*.gpg' |
		sed -e "s:^${prefix}/::" -e "s/....$//" |
		rofi -p "pass $action" -dmenu -i "$@"
)

[ -n "${password:-}" ] || exit

case "$typeit${WAYLAND_DISPLAY+w}" in
	0) pass "$action" -c "$password" 2>/dev/null ;;
	0w) pass "$action" "$password" | tr '\n' '\0' |
		wl-copy;;
	1) pass "$action" "$password" | tr '\n' '\0' |
		xdotool type --clearmodifiers --file - ;;
	1w) pass "$action" "$password" | tr '\n' '\0' |
		ydotool type --file - ;;
esac
