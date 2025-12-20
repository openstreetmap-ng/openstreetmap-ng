version=75.0.1
dest=app/static/img/browser

[ "$(cat "$dest/.version" 2>/dev/null)" = "$version" ] && exit 0
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
  name=$(basename "$browser_dir")

  # Prefer SVG
  svg=$(fd -I -t f -d 1 -e svg --max-results 1 . "$browser_dir")
  if [ -n "$svg" ]; then
    cp "$svg" "$dest/$name.svg"
    count=$((count + 1))
    continue
  fi

  # Fallback to 128x128 PNG
  png=$(fd -I -t f -d 1 -g '*_128x128.png' --max-results 1 . "$browser_dir")
  if [ -n "$png" ]; then
    cp "$png" "$dest/$name.png"
    count=$((count + 1))
    continue
  fi
done

echo "Downloaded $count browser logos"
echo "$version" >"$dest/.version"
