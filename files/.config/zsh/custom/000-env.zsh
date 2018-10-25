# make word splitting behave like bash
setopt SH_WORD_SPLIT

# Evaluate if root user
if uname -s | egrep -q '^(CYGWIN)|(MINGW)|(MSYS)'; then
    #windows
    if id -G | grep -q 544; then
        IS_ROOT=true
    else
        IS_ROOT=false
    fi
else
    #'nix
    if [[ $UID -eq 0 ]]; then
        IS_ROOT=true
    else
        IS_ROOT=false
    fi
fi
export IS_ROOT

# gpg-agent
export GPG_TTY=$(tty)
gpg-connect-agent updatestartuptty /bye >/dev/null

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
export ZSH_THEME_HOSTNAME_COLOR="$(get_hostname_color)"
unset -f get_hostname_color
