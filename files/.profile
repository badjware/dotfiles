# PATH
export PATH="$PATH:$HOME/.local/bin:$HOME/bin"

# applications
export TERMINAL=termite
export BROWSER=firefox
export VISUAL=nvim
export EDITOR=nvim
export PAGER=less
export DIFFPROG=meld

# motd
export MOTD_SERVICES="$MOTD_SERVICES docker.socket"

# firefox
export MOZ_USE_XINPUT2=1

# qt5
export DESKTOP_SESSION=gnome
export QT_STYLE_OVERRIDE=gtk
export QT_QPA_PLATFORMTHEME=gtk2
export QT_AUTO_SCREEN_SCALE_FACTOR=0

# java
export _JAVA_AWT_WM_NONREPARENTING=1
export _JAVA_OPTIONS="-Dawt.useSystemAAFontSettings=on -Dswing.aatext=true -Dswing.defaultlaf=com.sun.java.swing.plaf.gtk.GTKLookAndFeel -Dsun.java2d.opengl=true"
export JAVA_FONTS=/usr/share/fonts/TTF

source ~/.local/profile.d/*

