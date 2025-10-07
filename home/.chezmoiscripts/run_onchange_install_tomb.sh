#!/bin/bash
set -e

version="2.12"

cd /tmp

# File URLs
base_url="https://files.dyne.org/?file=tomb/releases"
file="Tomb-$version.tar.gz"
# import GPG key
curl -sL jaromil.dyne.org/jaromil.pub | gpg --import
echo "6113D89CA825C5CEDD02C87273B35DA54ACB7D10:6:" | gpg --import-ownertrust
# Download files
[ -r $file ]     || curl -o $file "$base_url/$file"
[ -r $file.sha ] || curl -o $file.sha "$base_url/$file.sha"
[ -r $file.asc ] || curl -o $file.asc "$base_url/$file.asc"
# Verify hash
sha512sum -c "$file.sha" || {
    echo "❌ tomb hash verification failed"
    exit 1; }
# Verify GPG signature
gpg --verify "$file.asc" "$file" || {
    echo "❌ tomb GPG signature verification failed"
    exit 1; }

# Extract and install
tar xvf "$file"
cd "Tomb-$version"
sudo make install

# Cleanup
sudo rm -r /tmp/Tomb-*