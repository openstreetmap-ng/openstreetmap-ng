if [ "$1" = "--staged" ]; then
  list_files() { git diff --cached --name-only --diff-filter=ACMR -z -- "$@"; }
else
  list_files() {
    while IFS= read -r -d '' file; do
      test -e "$file" && printf '%s\0' "$file"
    done < <(git ls-files -z "$@")
  }
fi

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

# Run formatters
format_files '*.nix' -- nixfmt
format_files '*.sh' -- shfmt -w
format_files '*.py' '*.pyi' -- ruff check --select I --fix --force-exclude
format_files '*.py' '*.pyi' -- ruff format --force-exclude
format_files '*.scss' -- bunx prettier --cache --write
format_files '*.sql' -- bunx sql-formatter --fix
format_files '*.ts' '*.js' '*.json' -- biome format --write --no-errors-on-unmatched
(cd speedup && cargo fmt)

if [ "$1" = "--staged" ]; then
  # Stage changes
  while IFS= read -r -d '' file; do
    if ! git diff --quiet -- "$file"; then
      printf '%s\0' "$file"
    fi
  done < <(git diff --cached --name-only --diff-filter=ACMR -z --) |
    git add --pathspec-from-file=- --pathspec-file-nul --
else
  # Run linters
  status=0
  echo "Linting files..."
  ruff check --fix || status=1
  biome check --fix --formatter-enabled=false || status=1
  bunx typescript --noEmit || status=1
  (cd speedup && cargo clippy --locked -- -D warnings) || status=1
  exit $status
fi
