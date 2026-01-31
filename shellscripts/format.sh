staged=0
if [[ ${1-} == --staged ]]; then
  staged=1
  shift
fi

list_files() {
  if ((staged)); then
    git diff --cached --name-only --diff-filter=ACMR -z -- "$@"
  else
    local file
    while IFS= read -r -d '' file; do
      if [[ -e $file ]]; then
        printf '%s\0' "$file"
      fi
    done < <(git ls-files -z -- "$@")
  fi
}

# format_files [--per-file] <patterns...> -- <command>
format_files() {
  local per_file=0
  if [[ ${1-} == --per-file ]]; then
    per_file=1
    shift
  fi

  local patterns=()
  while [[ $1 != -- ]]; do
    patterns+=("$1")
    shift
  done
  shift # Skip the --

  echo "Formatting ${patterns[*]} files..."
  local xargs_args=(-0 -r)
  if ((per_file)); then
    xargs_args+=(-n 1)
  fi
  list_files "${patterns[@]}" |
    xargs "${xargs_args[@]}" "$@"
}

run_formatters() {
  format_files '*.nix' -- nixfmt
  format_files '*.py' '*.pyi' -- ruff check --select I --fix --force-exclude
  format_files '*.py' '*.pyi' -- ruff format --force-exclude
  format_files '*.scss' -- bunx prettier --cache --write
  format_files '*.sh' -- shfmt -w
  format_files '*.sql' -- bunx sql-formatter --fix
  format_files '*.toml' -- tombi format
  format_files '*.ts' '*.tsx' '*.json' -- biome format --write --no-errors-on-unmatched
  format_files --per-file '*.proto' -- buf format -w
  (cd speedup && cargo fmt)
}

run_linters() {
  local status=0
  echo "Linting files..."
  ruff check --fix || status=$?
  BROWSERSLIST_IGNORE_OLD_DATA=true BASELINE_BROWSER_MAPPING_IGNORE_OLD_DATA=true \
    oxlint --fix --type-aware --type-check \
    app/views vite.config.ts || status=$?
  buf lint --path app/models/proto || status=$?
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
      git add --pathspec-from-file=- --pathspec-file-nul -- || true
  fi
else
  run_linters
fi
