staged=0
if [ "${1:-}" = "--staged" ]; then
  staged=1
  shift
fi

list_files() {
  if ((staged)); then
    git diff --cached --name-only --diff-filter=ACMR -z -- "$@"
  else
    local file
    while IFS= read -r -d '' file; do
      test -e "$file" && printf '%s\0' "$file"
    done < <(git ls-files -z -- "$@")
  fi
}

# format_files <patterns...> -- <command...>
format_files() {
  local patterns=()
  while [ "$1" != "--" ]; do
    patterns+=("$1")
    shift
  done
  shift # Skip the --

  echo "Formatting ${patterns[*]} files..."
  list_files "${patterns[@]}" | xargs -0 -r "$@"
}

run_formatters() {
  format_files '*.nix' -- nixfmt
  format_files '*.sh' -- shfmt -w
  format_files '*.py' '*.pyi' -- ruff check --select I --fix --force-exclude
  format_files '*.py' '*.pyi' -- ruff format --force-exclude
  format_files '*.scss' -- bunx prettier --cache --write
  format_files '*.sql' -- bunx sql-formatter --fix
  format_files '*.ts' '*.js' '*.json' -- biome format --write --no-errors-on-unmatched
  (cd speedup && cargo fmt)
}

run_linters() {
  local status=0
  echo "Linting files..."
  ruff check --fix || status=$?
  biome check --fix --formatter-enabled=false || status=$?
  bunx typescript --noEmit || status=$?
  (cd speedup && cargo clippy --locked -- -D warnings) || status=$?
  return $status
}

restage_files=()
partial_files=()
if ((staged)); then
  while IFS= read -r -d '' file; do
    if git diff --quiet --no-ext-diff -- "$file"; then
      restage_files+=("$file")
    else
      partial_files+=("$file")
    fi
  done < <(git diff --cached --name-only --diff-filter=ACMR -z --)

  if ((${#partial_files[@]})); then
    echo "Skipping partially-staged files:" >&2
    printf '  - %s\n' "${partial_files[@]}" >&2
  fi
fi

run_formatters

if ((staged)); then
  if ((${#restage_files[@]})); then
    printf '%s\0' "${restage_files[@]}" |
      git add --pathspec-from-file=- --pathspec-file-nul --
  fi
else
  run_linters
fi
