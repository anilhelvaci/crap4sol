#!/bin/sh
# Remove the crap4sol symlink installed by install.sh, only if it points to this checkout.
# Usage: ./uninstall.sh [target-dir]   (default: $HOME/.local/bin)
set -eu
unset CDPATH  # an exported CDPATH would redirect (and echo) relative cd

# print the physical path a (possibly symlinked) file resolves to; fail if it doesn't exist
resolve() {
    f=$1
    while [ -L "$f" ]; do
        dir=$(cd -P "$(dirname "$f")" && pwd) || return 1
        l=$(readlink "$f")
        case $l in
            /*) f=$l ;;
            *) f=$dir/$l ;;
        esac
    done
    [ -e "$f" ] || return 1
    echo "$(cd -P "$(dirname "$f")" && pwd)/$(basename "$f")"
}

launcher=$(resolve "$(dirname "$0")/bin/crap4sol")
target=${1:-$HOME/.local/bin}
link=$target/crap4sol

if [ ! -e "$link" ] && [ ! -L "$link" ]; then
    echo "Nothing to remove at $link"
    exit 0
fi
if [ ! -L "$link" ]; then
    echo "uninstall.sh: $link is not a symlink; leaving it alone" >&2
    exit 1
fi
if [ "$(resolve "$link" || true)" != "$launcher" ]; then
    echo "uninstall.sh: $link does not point to $launcher; leaving it alone" >&2
    exit 1
fi
rm -f "$link"
echo "Removed $link"
