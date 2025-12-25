version=75.0.1
dest=app/static/img/browser

current_version=
{ read -r current_version <"$dest/.version"; } 2>/dev/null || true
if [[ $current_version == "$version" ]]; then
  exit 0
fi

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
  if ((${#svgs[@]})); then
    cp -f -- "${svgs[0]}" "$dest/$name.svg"
    ((count += 1))
    continue
  fi

  # Fallback to 128x128 PNG
  pngs=("$browser_dir"/*_128x128.png)
  if ((${#pngs[@]})); then
    cp -f -- "${pngs[0]}" "$dest/$name.png"
    ((count += 1))
    continue
  fi
done

echo "Downloaded $count browser logos"
echo "$version" >"$dest/.version"
