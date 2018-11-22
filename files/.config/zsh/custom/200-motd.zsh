# Color for hostname
function get_hostname_color () {
    local col
    for hash_func in md5sum sha1sum sha256sum; do
        col="$(printf "%03d" "$((16#$(hostname | $hash_func | head -c2)))")"
        if [[ $col -ne 0 ]] \
        && [[ $col -lt 16 || $col -gt 21 ]] \
        && [[ $col -lt 232 || $col -gt 243 ]]; then
            # we found a color that isn't too dark
            echo $col>>~/test.log
            break
        else
            # default color
            col="002"
        fi
    done
    printf "$col"
}
case "$HOST" in
    "devbox")
        ZSH_THEME_HOSTNAME_COLOR="002"
        ;;
    "pallet")
        ZSH_THEME_HOSTNAME_COLOR="004"
        ;;
    "pewter")
        ZSH_THEME_HOSTNAME_COLOR="005"
        ;;
    *)
        ZSH_THEME_HOSTNAME_COLOR="$(get_hostname_color)"
        ;;
esac
unset -f get_hostname_color

# print motd
ZSH_THEME_HOSTNAME_COLOR="$ZSH_THEME_HOSTNAME_COLOR" motd

