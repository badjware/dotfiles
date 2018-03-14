alias svim="sudo -e"
alias vissh="$EDITOR ~/.ssh/config"
alias vihosts="sudo -e /etc/hosts"

if type htop >/dev/null; then
    alias top="htop"
fi

alias http-server="python -m http.server"
alias nmap-libvirt="nmap 192.168.122.0/24"
alias xsel="xsel -b"
alias rename="perl-rename"

alias drun-it="docker run -it"
alias dexec-it="docker exec -it"

# network stuff must always be run with sudo anyway
alias wifi-menu="sudo wifi-menu -o"
alias netctl="sudo netctl"

# serial
alias minicom="docker run --device=/dev/ttyUSB0 -it minicom"

# open-sourced build of vs code is named code-oss
alias code="code-oss"
