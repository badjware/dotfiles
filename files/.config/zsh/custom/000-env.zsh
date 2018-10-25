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

# Color
export ZSH_THEME_HOSTNAME_COLOR="$(printf "%03d" "$(hostname | md5sum | head -c2)")"
