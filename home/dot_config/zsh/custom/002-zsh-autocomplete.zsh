# cycle completions
bindkey              '^I'         menu-complete
bindkey "$terminfo[kcbt]" reverse-menu-complete

# wait for x input before autocompletion kicks in
zstyle ':autocomplete:*' min-input 3

# wait for x seconds before showing autocomplete
zstyle ':autocomplete:*' delay 0.5  # seconds (float)

# insert common substring first
# all Tab widgets
zstyle ':autocomplete:*complete*:*' insert-unambiguous yes
# all history widgets
zstyle ':autocomplete:*history*:*' insert-unambiguous yes
# ^S
zstyle ':autocomplete:menu-search:*' insert-unambiguous yes

# use fzf
zstyle ':autocomplete:*' fzf-completion yes