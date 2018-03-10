if [ "$IS_ROOT" = false ]; then
    neofetch --config "$ZSH_CUSTOM/config/neofetch-splash.bash"
	echo -e "\e[2A"

	# Updates
    #update_count="$(pacman -Qu | wc -l)"
    #[[ $update_count -ne 1 ]] && s="s"
    #[[ $update_count -ne 0 ]] && echo "$update_count package$s to update"
	#unset s update_count

	# Check tmux
	if tmux info &>/dev/null; then
    	tmux ls
    	echo " "
	fi
fi

