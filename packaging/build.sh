#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/build"
APP_DIR="$BUILD_DIR/usr/share/gsdeploy"
VERSION_FILE="$SCRIPT_DIR/version"

# Read and increment patch version (first run starts at 1.0.0 without incrementing)
if [ -f "$VERSION_FILE" ]; then
    VERSION=$(cat "$VERSION_FILE")
    MAJOR=$(echo "$VERSION" | cut -d. -f1)
    MINOR=$(echo "$VERSION" | cut -d. -f2)
    PATCH=$(echo "$VERSION" | cut -d. -f3)
    PATCH=$((PATCH + 1))
    VERSION="$MAJOR.$MINOR.$PATCH"
else
    VERSION="1.0.0"
fi
echo "$VERSION" > "$VERSION_FILE"

echo "Building version $VERSION..."

echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"

echo "Setting up package structure..."
mkdir -p "$APP_DIR"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/DEBIAN"

echo "Copying app files..."
cp -r "$REPO_DIR/gsdeploy"       "$APP_DIR/"
cp -r "$REPO_DIR/roles"          "$APP_DIR/"
cp -r "$REPO_DIR/playbooks"      "$APP_DIR/"
cp -r "$REPO_DIR/group_vars"     "$APP_DIR/"
cp -r "$REPO_DIR/group_vars"     "$APP_DIR/playbooks/"
cp    "$REPO_DIR/requirements.txt" "$APP_DIR/"
cp    "$REPO_DIR/ansible.cfg"    "$APP_DIR/"
cp    "$REPO_DIR/hosts"          "$APP_DIR/"

echo "Copying packaging files..."
sed "s/^Version:.*/Version: $VERSION/" "$SCRIPT_DIR/DEBIAN/control" > "$BUILD_DIR/DEBIAN/control"
cp "$SCRIPT_DIR/DEBIAN/postinst" "$BUILD_DIR/DEBIAN/postinst"
cp "$SCRIPT_DIR/usr/bin/gsdeploy" "$BUILD_DIR/usr/bin/gsdeploy"
cp "$SCRIPT_DIR/usr/share/applications/gsdeploy.desktop" \
   "$BUILD_DIR/usr/share/applications/gsdeploy.desktop"

echo "Setting permissions..."
chmod 755 "$BUILD_DIR/DEBIAN/postinst"
chmod 755 "$BUILD_DIR/usr/bin/gsdeploy"
find "$APP_DIR" -name "*.py" -exec chmod 644 {} \;
find "$APP_DIR" -name "*.yaml" -exec chmod 644 {} \;
find "$APP_DIR" -name "*.yml" -exec chmod 644 {} \;

echo "Building .deb package..."
dpkg-deb --build "$BUILD_DIR" "$SCRIPT_DIR/gsdeploy_${VERSION}.deb"

chmod 644 "$SCRIPT_DIR/gsdeploy_${VERSION}.deb"

echo ""
echo "Done: $SCRIPT_DIR/gsdeploy_${VERSION}.deb"
echo "Install with: sudo apt install ./packaging/gsdeploy_${VERSION}.deb"
