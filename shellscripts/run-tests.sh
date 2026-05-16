if [[ ! -S $PC_SOCKET_PATH ]]; then
  echo "NOTICE: Services are not running"
  echo "NOTICE: Run 'dev-start' before executing tests"
  exit 1
fi

term_output=0
coverage=1
args=(
  --verbose
  --no-header
  --randomly-seed="$EPOCHSECONDS"
)

for arg in "$@"; do
  case "$arg" in
  --term)
    term_output=1
    ;;
  --no-coverage)
    coverage=0
    ;;
  *)
    args+=("$arg")
    ;;
  esac
done

set +e
(
  set -x
  if [[ $coverage == 1 ]]; then
    python -m coverage run -m pytest "${args[@]}"
  else
    log_file=$(mktemp)
    python -m pytest "${args[@]}" 2>&1 | tee "$log_file"
    pytest_result=${PIPESTATUS[0]}
    if [[ $pytest_result == 134 ]] && grep -Eq '=+ [0-9]+ passed' "$log_file"; then
      pytest_result=0
    fi
    rm -f "$log_file"
    exit "$pytest_result"
  fi
)
result=$?
set -e

if [[ $coverage == 1 ]]; then
  if [[ $term_output == 1 ]]; then
    python -m coverage report --skip-covered
  else
    python -m coverage xml --quiet
  fi
  python -m coverage erase
fi
exit "$result"
