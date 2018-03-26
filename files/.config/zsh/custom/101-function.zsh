vialias() {
	$EDITOR $ZSH_CUSTOM/100-alias.zsh
	source $ZSH_CUSTOM/100-alias.zsh
}

vifunction() {
	$EDITOR $ZSH_CUSTOM/101-function.zsh
	source $ZSH_CUSTOM/101-function.zsh
}

nmap-libvirt() {
    __nmap_iface 'virbr[0-9]+' $@
}

nmap-tun() {
    __nmap_iface 'tun[0-9]+' $@
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
