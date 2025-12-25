manifest_file="app/static/vite/.vite/manifest.json"
if [[ ! -f $manifest_file ]]; then
  echo "No Vite manifest found, building..."
else
  changed=0
  for src in app/views/**/!(*.jinja); do
    [[ -f $src && $src -nt $manifest_file ]] || continue
    changed=1
    break
  done

  if ((changed == 0)); then
    exit 0
  fi
  echo "Source files have changed, rebuilding..."
fi
exec vite build
