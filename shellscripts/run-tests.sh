if [[ ! -S $PC_SOCKET_PATH ]]; then
  echo "NOTICE: Services are not running"
  echo "NOTICE: Run 'dev-start' before executing tests"
  exit 1
fi

term_output=0
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
  *)
    args+=("$arg")
    ;;
  esac
done

set +e
(
  set -x
  python -m coverage run -m pytest "${args[@]}"
)
result=$?
set -e

if [[ $term_output == 1 ]]; then
  python -m coverage report --skip-covered
else
  python -m coverage xml --quiet
fi
python -m coverage erase
exit "$result"
