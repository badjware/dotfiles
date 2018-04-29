if [ "$IS_ROOT" = false ]; then
    cat /etc/issue

	# Check tmux
	if tmux info &>/dev/null; then
        printf "\n%s\n\n" "$(tmux ls)"
	fi
fi

