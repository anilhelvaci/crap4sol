#!/bin/sh
# Install crap4sol by symlinking <repo>/bin/crap4sol into a directory on PATH.
# Usage: ./install.sh [target-dir]   (default: $HOME/.local/bin)
set -eu

repo=$(cd -P "$(dirname "$0")" && pwd)
target=${1:-$HOME/.local/bin}
case $target in
    /*) ;;
    *) target=$(pwd)/$target ;;
esac
link=$target/crap4sol

if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "install.sh: $link exists and is not a symlink; remove it or pick another directory" >&2
    exit 1
fi

for tool in uv forge; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "install.sh: warning: $tool not found on PATH; crap4sol needs it to run" >&2
    fi
done

if command -v uv >/dev/null 2>&1; then
    uv sync --project "$repo"
fi

mkdir -p "$target"
rm -f "$link"
ln -s "$repo/bin/crap4sol" "$link"
echo "Installed $link -> $repo/bin/crap4sol"

case ":${PATH:-}:" in
    *":$target:"*) ;;
    *)
        echo "$target is not on PATH; add it, e.g. in your shell profile:"
        echo "  export PATH=\"$target:\$PATH\""
        ;;
esac
echo "Try: crap4sol --help"
