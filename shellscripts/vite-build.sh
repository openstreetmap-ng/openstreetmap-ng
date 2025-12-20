manifest_file="app/static/vite/.vite/manifest.json"
if [ ! -f "$manifest_file" ]; then
  echo "No Vite manifest found, building..."
else
  changed=0
  while IFS= read -r -d "" src; do
    if [ "$src" -nt "$manifest_file" ]; then
      changed=1
      break
    fi
  done < <(fd -0 --type f --exclude "*.jinja" . app/views)

  ((changed)) || exit 0
  echo "Source files have changed, rebuilding..."
fi
exec vite build
