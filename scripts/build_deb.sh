#!/usr/bin/env bash
# Build a self-contained Debian package without installing anything on the host.
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_DIR"
build_python="${FF_BUILD_PYTHON:-python3}"
version="${1:-$(cat VERSION)}"
package_name="fitgirl-ff-link-extractor"

dpkg --validate-version "$version"
architecture="$(dpkg --print-architecture)"
glibc_version="$(getconf GNU_LIBC_VERSION)"
glibc_version="${glibc_version#glibc }"
"$build_python" -c 'import tkinter, PyInstaller'

mkdir -p build dist
work_dir="$(mktemp -d "$PROJECT_DIR/build/deb.XXXXXX")"
trap 'rm -rf -- "$work_dir"' EXIT
stage="$work_dir/package"

"$build_python" -m PyInstaller \
    --noconfirm --clean --onedir \
    --name "$package_name" \
    --distpath "$work_dir/frozen" \
    --workpath "$work_dir/pyinstaller" \
    --specpath "$work_dir" \
    --additional-hooks-dir "$PROJECT_DIR/packaging/hooks" \
    --add-data "$PROJECT_DIR/assets:assets" \
    --hidden-import distutils.version \
    ff_grabber.py

install -d "$stage/DEBIAN" "$stage/opt/$package_name" "$stage/usr/bin" \
    "$stage/usr/share/applications" "$stage/usr/share/icons/hicolor/scalable/apps" \
    "$stage/usr/share/doc/$package_name"
cp -a "$work_dir/frozen/$package_name/." "$stage/opt/$package_name/"
ln -s "/opt/$package_name/$package_name" "$stage/usr/bin/$package_name"
install -m 644 packaging/fitgirl-ff-link-extractor.desktop "$stage/usr/share/applications/"
install -m 644 assets/fitgirl-ff-link-extractor.svg "$stage/usr/share/icons/hicolor/scalable/apps/"
install -m 644 README.md "$stage/usr/share/doc/$package_name/README.md"
install -m 755 packaging/postinst packaging/postrm "$stage/DEBIAN/"
installed_size="$(du -sk "$stage/opt" "$stage/usr" | awk '{total += $1} END {print total}')"

cat > "$stage/DEBIAN/control" <<EOF
Package: $package_name
Version: $version
Section: net
Priority: optional
Architecture: $architecture
Maintainer: FitGirl FF Link Extractor contributors <noreply@github.com>
Installed-Size: $installed_size
Depends: libc6 (>= $glibc_version), libfontconfig1, libx11-6, libxext6, libxft2, libxrender1
Homepage: https://github.com/zouhirdev/fitgirl-ff-link-extractor
Description: Desktop tool for extracting direct download links
 Select files from FitGirl pages and resolve FuckingFast download URLs.
 Includes Python, Tkinter, and Python dependencies. Uses an installed Chrome,
 Edge, Brave, or Firefox browser with a configurable background tab limit.
 Browser engines are not downloaded by this application.
EOF

output="$PROJECT_DIR/dist/${package_name}_${version}_${architecture}.deb"
dpkg-deb --root-owner-group --build "$stage" "$output"
printf '\nBuilt %s\n' "$output"
