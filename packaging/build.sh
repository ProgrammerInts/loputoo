#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/build"
APP_DIR="$BUILD_DIR/usr/share/gsdeploy"
VERSION_FILE="$SCRIPT_DIR/version"

# Read current version
if [ -f "$VERSION_FILE" ]; then
    VERSION=$(cat "$VERSION_FILE")
else
    VERSION="1.0.0"
fi

MAJOR=$(echo "$VERSION" | cut -d. -f1)
MINOR=$(echo "$VERSION" | cut -d. -f2)
PATCH=$(echo "$VERSION" | cut -d. -f3)

echo "Current version: $VERSION"
echo "Bump version:"
echo "  1) Major ($MAJOR -> $((MAJOR + 1)).0.0)"
echo "  2) Minor ($MAJOR.$MINOR -> $MAJOR.$((MINOR + 1)).0)"
echo "  3) Patch ($VERSION -> $MAJOR.$MINOR.$((PATCH + 1)))"
read -rp "Choice [1/2/3]: " BUMP

case "$BUMP" in
    1) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    2) MINOR=$((MINOR + 1)); PATCH=0 ;;
    3) PATCH=$((PATCH + 1)) ;;
    *) echo "Invalid choice. Aborting."; exit 1 ;;
esac

VERSION="$MAJOR.$MINOR.$PATCH"
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
