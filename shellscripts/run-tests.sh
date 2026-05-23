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
  --no-coverage)
    coverage=0
    ;;
  --term)
    term_output=1
    ;;
  *)
    args+=("$arg")
    ;;
  esac
done

set +e
if [[ $coverage == 1 ]]; then
  (
    set -x
    python -m coverage run -m pytest "${args[@]}"
  )
else
  (
    set -x
    python -m pytest "${args[@]}"
  )
fi
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
