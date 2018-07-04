alias svim="sudo -e"
alias vissh="$EDITOR ~/.ssh/config"
alias vihosts="sudo -e /etc/hosts"

alias vim="nvim"
alias top="htop"
alias http-server="python -m http.server"
alias rename="perl-rename"
alias userctl="systemctl --user"

# powershell seems to have trouble with xterm-256colors
alias pwsh="TERM=xterm pwsh"
alias powershell="TERM=xterm pwsh"

# network stuff must always be run with sudo anyway
alias wifi-menu="sudo wifi-menu -o"
alias netctl="sudo netctl"

# serial
alias minicom="docker run --device=/dev/ttyUSB0 -it registry.massaki.ca/minicom"

# open-sourced build of vscode is named code-oss
alias code="code-oss"

