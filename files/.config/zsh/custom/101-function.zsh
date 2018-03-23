vialias() {
	$EDITOR $ZSH_CUSTOM/100-alias.zsh
	source $ZSH_CUSTOM/100-alias.zsh
}

vifunction() {
	$EDITOR $ZSH_CUSTOM/101-function.zsh
	source $ZSH_CUSTOM/101-function.zsh
}

nmap-libvirt() {
    local addr_list=""
    for link in $(ip link show up | grep -Eo 'virbr[0-9]+'); do
        for addr in $(ip addr show $link | grep -oP '(?<=inet )([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}'); do
            addr_list="$addr_list $addr"
        done
    done
    echo "Scanning $addr_list"
    nmap $@ $addr_list
}

nmap-local() {
    local addr_list=""
    for link in $(ip link show up | grep -Eo '(eth|wlan)[0-9]+'); do
        for addr in $(ip addr show $link | grep -oP '(?<=inet )([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}'); do
            addr_list="$addr_list $addr"
        done
    done
    echo "Scanning $addr_list"
    nmap $@ $addr_list
}
