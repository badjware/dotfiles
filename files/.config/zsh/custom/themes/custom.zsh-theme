setopt prompt_subst # enable command substitution in prompt

PROMPT='$(prompt_cmd)'
RPROMPT=''

ZSH_THEME_GIT_PROMPT_PREFIX="%{$FG[008]%} on %{$fg[cyan]%}"
ZSH_THEME_GIT_PROMPT_SUFFIX=""

ZSH_THEME_GIT_PROMPT_ADDED="%{$fg_bold[green]%}+"
ZSH_THEME_GIT_PROMPT_MODIFIED="%{$fg_bold[blue]%}!"
ZSH_THEME_GIT_PROMPT_DELETED="%{$fg_bold[red]%}-"
ZSH_THEME_GIT_PROMPT_RENAMED="%{$fg_bold[magenta]%}>"
ZSH_THEME_GIT_PROMPT_UNMERGED="%{$fg_bold[yellow]%}#"
ZSH_THEME_GIT_PROMPT_UNTRACKED="%{$fg_bold[cyan]%}?"
ZSH_THEME_GIT_PROMPT_AHEAD="%{$fg_bold[white]%}↑"
ZSH_THEME_GIT_PROMPT_BEHIND="%{$fg_bold[white]%}↓"


# Evaluate if root user
__is_root() {
    if uname -s | egrep '^(CYGWIN)|(MINGW)|(MSYS)' 2>&1 >/dev/null; then
        id -G | grep 544 2>&1 >/dev/null
    else
        [ $UID -eq 0 ]
    fi
}

# Get the tmp directory
function __get_runtime_dir() {
    if [[ -n "$XDG_RUNTIME_DIR" ]]; then
        echo -n "$XDG_RUNTIME_DIR"
    else
        echo -n "/tmp/"
    fi
}

prompt_cmd() {
    # exit code
    local exit_code=$?
    local exit_code_hex=$(printf '(%02x)' $exit_code)

    if [[ exit_code -eq 0 ]]; then
        exit_code_hex="%{$FG[008]%}$exit_code_hex"
    else
        exit_code_hex="%{$fg[red]%}$exit_code_hex"
    fi

    # name@hostname
    local default_color="green"
    local user_color="$default_color"
    if __is_root; then
        local user_color="red"
    fi
    local name_hostname="%{$fg[$user_color]%}$USER%{$fg[$default_color]%}@%m"

    # working directory
    local wd_base="${PWD/$HOME/~}"
    local wd_post=$(echo "$wd_base" | grep -Eo '(^~|/[^/]+){1,4}$')
    local wd_pre=$(echo "${wd_base/$wd_post/}" | grep -Eo '^~|/[^/]{2}' | tr -d '\n' )
    local wd="%{$fg[yellow]%}$wd_pre$wd_post"

    # prompt
    if __is_root; then
        # #
        local prompt="%{$fg[red]%}#"
    else
        # $
        local prompt="%{$FG[008]%}$"
    fi

    printf "%s %s %s\n%s %s" "$exit_code_hex" "$name_hostname" "$wd" "$prompt" "%{$reset_color%}"
}

rprompt_cmd() {
    # git
    if git rev-parse --git-dir >/dev/null 2>&1; then
        local prompt_info="$(git_prompt_info)"
        if [[ -z "$prompt_info" ]]; then
            local git_rev="$(git_prompt_short_sha)"
        else
            local git_rev="$prompt_info"
        fi

        local prompt_status="$(git_prompt_status)"
        if [[ -n "$prompt_status" ]]; then
            local git_status="$(printf "%s[%s%s]" "%{$FG[008]%}" "$prompt_status" "%{$reset_color%}%{$FG[008]%}")"
        fi
    fi

    printf "%s %s%s" "$git_rev" "$git_status" "%{$reset_color%}"
}

# Based on http://www.anishathalye.com/2015/02/07/an-asynchronous-shell-prompt/
ASYNC_PROC=0
function precmd() {
    function async() {
        # save to temp file
        printf "%s" "$(rprompt_cmd)" > "$(__get_runtime_dir)/zsh_prompt_$$"

        # signal parent
        kill -s USR1 $$
    }

    # do not clear RPROMPT, let it persist

    # kill child if necessary
    if [[ "${ASYNC_PROC}" != 0 ]]; then
        kill -s HUP $ASYNC_PROC >/dev/null 2>&1 || :
    fi

    # start background computation
    async &!
    ASYNC_PROC=$!
}

function TRAPUSR1() {
    # read from tmp file
    RPROMPT="$(cat $(__get_runtime_dir)/zsh_prompt_$$)"
    rm "/tmp/zsh_prompt_$$" &>/dev/null

    # reset proc number
    ASYNC_PROC=0

    # redisplay
    zle && zle reset-prompt
}

# vim: syn=zsh
