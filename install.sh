#!/bin/bash

log() {
    printf '[%s] %s\n' "$1" "$2"
}

print_help() {
    cat <<EOF

Install the dotfiles.

USAGE
  install.sh [OPTIONS]

OPTIONS
  -h, --help      Display this help message.
  -y  --yes       Skip confirmations.
      --symlink   Symlink the files. This is the default behavior.
      --copy      Copy the files.
      --noscript  Skip the pre-install and the post-install scripts

EOF
}

# Filter dir to keep only the lowest in the tree
# format to be readable by find
# assume reverse sorted
filter_path() {
    # the first occurence is not prefixed
    prefix=
    previous_dir=

	printf "("
	while IFS= read -r dir; do
		if [[ -z "$previous_dir" || "$dir" != "$previous_dir"* ]]; then
            printf -- "%s -path %s " "$prefix" "${dir%/}"
			previous_dir="$dir"
			prefix="-o"
		fi
	done
	printf ")"
}

# List all the files in path, except if it find a file name .@dir
get_path() {
    pushd "$1" >/dev/null
    shopt -s dotglob

     [[ "$(find . -mindepth 1 -maxdepth 1 | wc -c)" -eq 0 ]] && return

    # find dirs .@dir files
    find_dir_args="$(find * -mindepth 1 -name '.@dir' -type f -empty -printf "%h\n" | sort -r | filter_path)"

    # find files and exclude paths that containe a .@dir
    if [[ $find_dir_args = "()" ]]; then
        find * ! -type d
    else
        find * -type d $find_dir_args -prune -o ! -type d
    fi

    shopt -u dotglob
    popd >/dev/null
}

# Link the dotfile
make_link() {
	repo_f="$1"
	home_f="$HOME/$2"

    if [[ -L "$home_f" || -e "$home_f" ]]; then
        # Check if it's already symlinked
        if [[ ! "$OPT_COPY" && -L "$home_f" && "$(readlink -- "$home_f")" ]]; then
            return;
        fi

        # File exists, ask to delete
        if [[ "$OPT_YES" ]]; then
            rm -rf "$home_f"
        else
            while true; do
                read -r -p "Override $2? [Y/n] " a
                if [[ "${a,,}" = "y"  ]]; then
                    rm -r "$home_f"
                    break
                elif [[ "${a,,}" = "n"  ]]; then
                    echo "skipping..."
                    return
                fi
            done
       fi
    fi

    mkdir -p "$(dirname "$home_f")" &>/dev/null
    if [[ -n "$OPT_COPY"  ]]; then
        log + "Creating copy $repo_f > $home_f"
        cp -r "$repo_f" "$home_f"
    else
        log + "Creating symlink $repo_f > $home_f"
        ln -s "$repo_f" "$home_f"
    fi
}

short_args=hy
long_args=help,yes,symlink,copy,noscript

# Parse arguments
parsed_args=$(getopt --options $short_args --longoptions $long_args --name "$0" -- "$@")
if [[ $? -ne 0 ]]; then
	echo "Failed to parse arguments"
	exit 2
fi
eval set -- "$parsed_args"
while true; do
	case "$1" in
		-h|--help)
			print_help
            exit
			;;
		-y|--yes)
            OPT_YES="--yes"
            OPT_NOCONFIRM="--noconfirm"
            shift
			;;
		--symlink)
            OPT_SYMLINK=true
			shift
			;;
		--copy)
            OPT_COPY=true
			shift
			;;
		--noscript)
            OPT_NOSCRIPT=true
			shift
			;;
		--)
			shift
			break
			;;
		*)
			break
			;;
	esac
done

if [[ "$OPT_SYMLINK" && "$OPT_COPY" ]]; then
    log E "Cannot use --symlink and --copy at the same time!"
    exit 1
fi

pushd "${0%/*}" >/dev/null

if [[ -f "./scripts/pre-install.sh" && -z "$OPT_NOSCRIPT" ]]; then
    log "*" "Running pre-install"
    bash ./scripts/pre-install.sh
fi

for file_source in "files"; do
    log "*" "Processing $file_source"
    while read file_path; do
        make_link "$PWD/$file_source/$file_path" "$file_path"
    done < <(get_path "$file_source")
done

if [[ -f "./scripts/post-install.sh" && -z "$OPT_NOSCRIPT" ]]; then
    log "*" "Running post-install"
    bash ./scripts/post-install.sh
fi

popd >/dev/null

