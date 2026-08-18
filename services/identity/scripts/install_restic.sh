#!/bin/bash
# Instala el binario oficial fijado y verificado de restic para linux/amd64.
set -euo pipefail
umask 077

VERSION="0.19.1"
EXPECTED_SHA256="f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c"
URL="https://github.com/restic/restic/releases/download/v${VERSION}/restic_${VERSION}_linux_amd64.bz2"
TEMP_DIR=$(mktemp -d)
trap 'rm -rf -- "$TEMP_DIR"' EXIT

curl --fail --location --silent --show-error "$URL" -o "$TEMP_DIR/restic.bz2"
echo "$EXPECTED_SHA256  $TEMP_DIR/restic.bz2" | sha256sum --check --status
python3 -c 'import bz2, pathlib, sys; pathlib.Path(sys.argv[2]).write_bytes(bz2.decompress(pathlib.Path(sys.argv[1]).read_bytes()))' "$TEMP_DIR/restic.bz2" "$TEMP_DIR/restic"
install -o root -g root -m 0755 "$TEMP_DIR/restic" /usr/local/bin/restic
/usr/local/bin/restic version
