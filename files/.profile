# PATH
export PATH="$HOME/.local/bin:$HOME/bin:$PATH"

# applications
export TERMINAL=termite
export BROWSER=firefox
export VISUAL=nvim
export EDITOR=nvim
export PAGER=less
export DIFFPROG=meld

# motd
export MOTD_SERVICES="$MOTD_SERVICES docker.socket sshd.service"

# java
export _JAVA_OPTIONS="-Dawt.useSystemAAFontSettings=on -Dswing.aatext=true -Dswing.defaultlaf=com.sun.java.swing.plaf.gtk.GTKLookAndFeel -Dsun.java2d.opengl=true"
export JAVA_FONTS=/usr/share/fonts/TTF

source ~/.local/profile.d/*
