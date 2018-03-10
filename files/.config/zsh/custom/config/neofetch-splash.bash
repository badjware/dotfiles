ascii_distro="arch_small"

print_info () {
	info line_break

    info "OS" distro
    info "Shell" shell
    info "Kernel" kernel

    info line_break
    
    info "Packages" packages "$update_msg"
}
