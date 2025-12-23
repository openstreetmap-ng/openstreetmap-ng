files=()
declare -A BLACKLIST

# Reason: Unsupported PEP-654 Exception Groups
# https://github.com/cython/cython/issues/4993
BLACKLIST["app/services/optimistic_diff/__init__.py"]=1

# Reason: Lambda default arguments fail with embedsignature=True
# https://github.com/cython/cython/issues/6880
BLACKLIST["app/lib/pydantic_settings_integration.py"]=1

DIRS=(
  "app/exceptions" "app/exceptions06" "app/format" "app/lib"
  "app/middlewares" "app/responses" "app/services"
  "app/queries" "app/validators"
)
for dir in "${DIRS[@]}"; do
  for file in "$dir"/**/*.py; do
    [[ -f $file && -z ${BLACKLIST[$file]:-} ]] || continue
    files+=("$file")
  done
done

EXTRA_PATHS=(
  "app/db.py" "app/utils.py"
  "app/models/element.py" "app/models/scope.py" "app/models/tags_format.py"
  "scripts/preload_convert.py" "scripts/replication_download.py"
  "scripts/replication_generate.py"
)
for file in "${EXTRA_PATHS[@]}"; do
  [[ -f $file && -z ${BLACKLIST[$file]:-} ]] || continue
  files+=("$file")
done

echo "Found ${#files[@]} source files"

CFLAGS="$(python-config --cflags) $CFLAGS \
  -shared -fPIC \
  -DCYTHON_PROFILE=1 \
  -DCYTHON_USE_SYS_MONITORING=0"
export CFLAGS

LDFLAGS="$(python-config --ldflags) $LDFLAGS"
export LDFLAGS

_SUFFIX=$(python-config --extension-suffix)
export _SUFFIX

process_file() {
  pyfile="$1"
  module_name="${pyfile%.py}"        # Remove .py extension
  module_name="${module_name//\//.}" # Replace '/' with '.'
  c_file="${pyfile%.py}.c"
  so_file="${pyfile%.py}$_SUFFIX"

  # Skip unchanged files
  [[ $so_file -nt $pyfile ]] && return 0

  (
    set -x
    cython -3 \
      --annotate \
      --directive overflowcheck=True,embedsignature=True,profile=True \
      --module-name "$module_name" \
      "$pyfile" -o "$c_file"
  )

  # shellcheck disable=SC2086
  (
    set -x
    $CC $CFLAGS "$c_file" -o "$so_file" $LDFLAGS
  )
}
export -f process_file

parallel process_file ::: "${files[@]}"
