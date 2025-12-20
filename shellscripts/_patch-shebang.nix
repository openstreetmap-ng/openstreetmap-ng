{ pkgs, ... }:
''
  while IFS= read -r -d "" script; do
    if ! head -n 1 "$script" | rg -q -F ".venv/bin/python"; then continue; fi

    module_name=$(rg -m 1 -o --replace '$1' '^from ([^[:space:]]+)' "$script")
    if [ -z "$module_name" ]; then
      echo "Warning: Could not extract module name from $script"
      continue
    fi

    temp_file=$(mktemp)
    {
      printf '%s\n' "#!${pkgs.runtimeShell}"
      printf 'exec python -m "%s" "$@"\n' "$module_name"
    } > "$temp_file"
    chmod --reference="$script" "$temp_file"
    mv "$temp_file" "$script"

    echo "Patched $script"
  done < <(fd -0 -t x -d 1 . .venv/bin)
''
