ZSH_HIGHLIGHT_STYLES[default]="none"
ZSH_HIGHLIGHT_STYLES[unknown-token]="fg=red,bold"
ZSH_HIGHLIGHT_STYLES[reserved-word]="fg=yellow"
ZSH_HIGHLIGHT_STYLES[alias]="fg=white,bold"
ZSH_HIGHLIGHT_STYLES[builtin]="fg=magenta,bold"
ZSH_HIGHLIGHT_STYLES[function]="fg=white,bold"
ZSH_HIGHLIGHT_STYLES[command]="fg=white,bold"
ZSH_HIGHLIGHT_STYLES[precommand]="fg=yellow,bold"
ZSH_HIGHLIGHT_STYLES[commandseparator]="none"
ZSH_HIGHLIGHT_STYLES[hashed-command]="none"
ZSH_HIGHLIGHT_STYLES[path]="none"
ZSH_HIGHLIGHT_STYLES[globbing]="none"
ZSH_HIGHLIGHT_STYLES[history-expansion]="fg=blue"
ZSH_HIGHLIGHT_STYLES[single-hyphen-option]="fg=cyan"
ZSH_HIGHLIGHT_STYLES[double-hyphen-option]="fg=cyan,bold"
ZSH_HIGHLIGHT_STYLES[single-quoted-argument]="fg=green"
ZSH_HIGHLIGHT_STYLES[single-quoted-argument-unclosed]="fg=red,bold"
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]="fg=green"
ZSH_HIGHLIGHT_STYLES[double-quoted-argument-unclosed]="fg=red,bold"
ZSH_HIGHLIGHT_STYLES[dollar-double-quoted-argument]="fg=yellow"
ZSH_HIGHLIGHT_STYLES[back-double-quoted-argument]="fg=yellow"
#ZSH_HIGHLIGHT_STYLES[assign]="none"

HSMW_HIGHLIGHT_STYLES=("${(@kvf)ZSH_HIGHLIGHT_STYLES}")
FAST_HIGHLIGHT_STYLES=("${(@kvf)ZSH_HIGHLIGHT_STYLES}")

