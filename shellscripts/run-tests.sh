if [[ ! -S $PC_SOCKET_PATH ]]; then
  echo "NOTICE: Services are not running"
  echo "NOTICE: Run 'dev-start' before executing tests"
  exit 1
fi

term_output=0
coverage=1
hard_exit=0
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
  --hard-exit)
    coverage=0
    hard_exit=1
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
  elif [[ $hard_exit == 1 ]]; then
    python -c 'import os, sys, pytest; os._exit(pytest.main(sys.argv[1:]))' "${args[@]}"
  else
    python -m pytest "${args[@]}"
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
