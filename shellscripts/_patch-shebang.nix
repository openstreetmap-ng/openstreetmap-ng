{ pkgs, ... }:
''
  for script in .venv/bin/*; do
    [[ -f $script && -x $script ]] || continue

    read -r first_line <"$script" || continue
    [[ $first_line == *".venv/bin/python"* ]] || continue

    if ! module_name=$(rg -m 1 -o --replace '$1' '^from ([^[:space:]]+)' "$script"); then
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
  done
''
