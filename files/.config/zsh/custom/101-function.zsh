# edit alias
vialias() {
	$EDITOR $ZSH_CUSTOM/100-alias.zsh
	source $ZSH_CUSTOM/100-alias.zsh
}

# edit function
vifunction() {
	$EDITOR $ZSH_CUSTOM/101-function.zsh
	source $ZSH_CUSTOM/101-function.zsh
}

# scan network
nmap-libvirt() {
    __nmap_iface 'virbr[0-9]+' $@
}

nmap-tun() {
    __nmap_iface '(tun|tap)[0-9]+' $@
}

nmap-local() {
    __nmap_iface '(eth|wlan)[0-9]+' $@
}

__nmap_iface() {
    local iface="$1"
    shift
    local opt=${@:--T5}

    for link in $(ip link show up | grep -Eo "$iface"); do
        for addr in $(ip addr show $link | grep -oP '(?<=inet )([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}'); do
            addr_list="$addr_list $addr"
        done
    done

    printf "Scanning %s\n" "$addr"
    nmap $opt $addr_list
}

# calculator
\=() {
   bc -l <<<"$*"
}

# start looking-glass
play-vm() {
    if ! [ -S /tmp/win10.sock ]; then
        echo "Cannot find spice socket! Is the vm started?"
    else
        echo "Setup cpuset cgroup for host"
        sudo cset set -c 0,4 -s system
        sudo cset proc -m -f root -t system
        sudo cset proc -k -f root -t system --force

        echo "Setup cpumask"
        sudo bash -c "echo 5 > /sys/devices/virtual/workqueue/cpumask"

        echo "Starting looking-glass"
        LD_PRELOAD=/usr/\$LIB/libgamemodeauto.so looking-glass-client -p 0 -c /tmp/win10.sock -o opengl:preventBuffer=0 -MF

        echo "Restore system"
        # cpumask
        sudo bash -c "echo f > /sys/devices/virtual/workqueue/cpumask"
        # cpuset
        sudo cset set -d system &>/dev/null
    fi
}
