dir=app/views/lib/vector-styles
mkdir -p "$dir"
styles=(
  "liberty+https://tiles.openfreemap.org/styles/liberty"
)
for style in "${styles[@]}"; do
  name="${style%%+*}"
  url="${style#*+}"
  file="$dir/$name.json"
  echo "Updating $name vector style"
  curl -fsSL --compressed "$url" | jq --sort-keys . >"$file"
done
