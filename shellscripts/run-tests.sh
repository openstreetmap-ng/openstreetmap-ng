if [[ ! -S $PC_SOCKET_PATH ]]; then
  echo "NOTICE: Services are not running"
  echo "NOTICE: Run 'dev-start' before executing tests"
  exit 1
fi

term_output=0
coverage_enabled=1
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

if find app -name "*$(python-config --extension-suffix)" -print -quit | grep -q .; then
  # Python 3.14 currently aborts during coverage shutdown after compiled Cython
  # test runs, even when pytest itself has completed successfully.
  coverage_enabled=0
fi

set +e
if [[ $coverage_enabled == 1 ]]; then
  (
    set -x
    python -m coverage run -m pytest "${args[@]}"
  )
  result=$?
else
  pytest_output=$(mktemp)
  set -x
  python -m pytest "${args[@]}" 2>&1 | tee "$pytest_output"
  result=${PIPESTATUS[0]}
  set +x
  if [[ $result == 134 ]] && grep -Eq "={2,} [0-9]+ passed" "$pytest_output"; then
    echo "NOTICE: pytest passed, ignoring Python 3.14 Cython shutdown abort"
    result=0
  fi
  rm -f "$pytest_output"
fi
set -e

if [[ $coverage_enabled == 1 ]]; then
  if [[ $term_output == 1 ]]; then
    python -m coverage report --skip-covered
  else
    python -m coverage xml --quiet
  fi
  python -m coverage erase
fi
exit "$result"
