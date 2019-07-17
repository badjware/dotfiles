# Make word splitting behave like bash
setopt SH_WORD_SPLIT

# History
HISTSIZE=100000
SAVEHIST=100000
setopt SHARE_HISTORY       # Share history between all sessions.
setopt HIST_REDUCE_BLANKS  # Remove superfluous blanks before recording entry.

# gpg-agent
export GPG_TTY=$(tty)
gpg-connect-agent updatestartuptty /bye >/dev/null

# keychain (for ssh agent)
eval $(keychain --eval --quiet --noask --nogui)
