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

# start game mode
gamemode() {
    if ! [ -S /tmp/win10.sock ]; then
        echo "Cannot find spice socket! Is the vm started?"
    else
        echo "Setup cpuset cgroup for host"
        sudo cset set -c 0,4 -s system
        sudo cset proc -m -f root -t system
        sudo cset proc -k -f root -t system --force

        echo "Setup cpumask"
        for i in /sys/devices/virtual/workqueue/*/cpumask; do
            sudo sh -c "echo 001 > $i"
        done;

        echo "Setup interrupt affinity"
        for i in $(sed -n -e 's/ \([0-9]\+\):.*vfio.*/\1/p' /proc/interrupts); do
            sudo sh -c "echo 0,4 > /proc/irq/$i/smp_affinity_list"
        done

        LD_PRELOAD="/usr/\$LIB/libgamemodeauto.so" looking-glass-wrapper

        echo "Restore system"
        # irq
        for i in $(sed -n -e 's/ \([0-9]\+\):.*vfio.*/\1/p' /proc/interrupts); do
            sudo sh -c "echo ff > /proc/irq/$i/smp_affinity"
        done
        # cpumask
        for i in /sys/devices/virtual/workqueue/*/cpumask; do
            sudo sh -c "echo ff > $i"
        done;
        # cpuset
        sudo cset set -d system &>/dev/null
    fi
}
