#/bin/bash

# Autostart sway if we are on tty1
if [ -z "$WAYLAND_DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    # setup logging
    log_stdout="$XDG_RUNTIME_DIR/sway_stdout.log"
    log_stderr="$XDG_RUNTIME_DIR/sway_stderr.log"
    echo "Redirecting stdout to $log_stdout"
    echo "Redirecting stderr to $log_stderr"

    exec ~/.local/bin/sway 2>"$log_stderr" >"$log_stdout"
fi

