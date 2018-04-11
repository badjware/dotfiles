alias svim="sudo -e"
alias vissh="$EDITOR ~/.ssh/config"
alias vihosts="sudo -e /etc/hosts"

alias top="htop"
alias http-server="python -m http.server"
alias rename="perl-rename"

alias drun-it="docker run -it"
alias dexec-it="docker exec -it"

# network stuff must always be run with sudo anyway
alias wifi-menu="sudo wifi-menu -o"
alias netctl="sudo netctl"

# serial
alias minicom="docker run --device=/dev/ttyUSB0 -it registry.massaki.ca/minicom"

# open-sourced build of vs code is named code-oss
alias code="code-oss"
