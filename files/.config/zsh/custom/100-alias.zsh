alias svim="sudo -e"
alias vissh="$EDITOR ~/.ssh/config"
alias vihosts="sudo -e /etc/hosts"

alias vim="nvim"
alias top="htop"
alias http-server="python -m http.server"
alias rename="perl-rename"
alias userctl="systemctl --user"

# ls
alias ls="lsd --group-dirs first"
alias l='lsd --group-dirs -l'
alias la='lsd --group-dirs -a'
alias lla='lsd --group-dirs -la'
alias lt='lsd --group-dirs --tree'

# powershell seems to have trouble with xterm-256color
alias pwsh="TERM=xterm pwsh"
alias powershell="TERM=xterm pwsh"

# remote often does not have the correct terminfo for termite
alias ssh="TERM=xterm-256color ssh"

# network stuff must always be run with sudo anyway
alias wifi-menu="sudo wifi-menu -o"
alias netctl="sudo netctl"

# docker
alias minicom="docker run --device=/dev/ttyUSB0 -it registry.massaki.ca/minicom"
alias browsh="docker run --rm -it browsh/browsh"

# open-sourced build of vscode is named code-oss
alias code="code-oss"

