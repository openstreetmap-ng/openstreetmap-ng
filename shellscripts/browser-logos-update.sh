version=75.0.1
dest=app/static/img/browser

current_version=
{ read -r current_version <"$dest/.version"; } 2>/dev/null || true
[[ $current_version == "$version" ]] && exit 0

echo "Downloading browser logos (v$version)..."

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fL "https://github.com/alrra/browser-logos/archive/refs/tags/$version.tar.gz" |
  tar -xz -C "$tmp"

src="$tmp/browser-logos-$version/src"
rm -rf "$dest"
mkdir -p "$dest"

count=0

for browser_dir in "$src"/*/; do
  name="${browser_dir%/}"
  name="${name##*/}"

  # Prefer SVG
  svgs=("$browser_dir"/*.svg)
  ((${#svgs[@]})) && {
    cp -f -- "${svgs[0]}" "$dest/$name.svg"
    ((count++))
    continue
  }

  # Fallback to 128x128 PNG
  pngs=("$browser_dir"/*_128x128.png)
  ((${#pngs[@]})) && {
    cp -f -- "${pngs[0]}" "$dest/$name.png"
    ((count++))
    continue
  }
done

echo "Downloaded $count browser logos"
echo "$version" >"$dest/.version"
