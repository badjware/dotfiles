alias svim="sudo -e"
alias vissh="$EDITOR ~/.ssh/config"
alias vihosts="sudo -e /etc/hosts"

alias vim="nvim"
alias top="htop"
alias http-server="python -m http.server"
alias rename="perl-rename"
alias userctl="systemctl --user"
alias lock="swaylock"
alias etckeeper="sudo etckeeper"

# ls
alias ls='lsd --group-dirs=first'
alias l='ls -l'
alias la='ls -a'
alias lla='ls -la'
alias lt='ls --tree'

# network stuff must always be run with sudo anyway
alias wifi-menu="sudo wifi-menu -o"
alias netctl="sudo netctl"

# docker
alias minicom="docker run --device=/dev/ttyUSB0 -it registry.massaki.ca/minicom"
alias browsh="docker run --rm -it browsh/browsh"

alias convert-doc="libreoffice --headless --invisible --norestore --convert-to "
