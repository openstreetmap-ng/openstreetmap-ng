process_file() {
  local file="$1"
  local mode="$2"

  process_file_inner() {
    local extension="$1"
    local compressor="$2"
    shift 2
    local -a args=("$@")

    local dest="$file$extension"
    if [[ $mode == clean ]]; then
      rm -f -- "$dest"
      return 0
    fi

    if [[ ! -f $dest || $dest -ot $file ]]; then
      local tmpfile
      tmpfile=$(mktemp -t "${dest##*/}.XXXXXXXXXX")
      if ! "$compressor" "${args[@]}" "$file" -o "$tmpfile"; then
        rm -f -- "$tmpfile"
        return 1
      fi
      touch --reference="$file" "$tmpfile"
      mv -f -- "$tmpfile" "$dest"
    fi
  }

  process_file_inner .zst zstd --force -19 --single-thread --quiet
  process_file_inner .br brotli --force --best
}
export -f process_file

roots=(
  "app/static"
  "config/locale/i18next"
  node_modules/.bun/iD@*/node_modules/iD/dist
  node_modules/.bun/@rapideditor+rapid@*/node_modules/@rapideditor/rapid/dist
)

fd -I0 \
  -t f \
  -S +499b \
  -E "*.xcf" \
  -E "*.gif" \
  -E "*.jpg" \
  -E "*.jpeg" \
  -E "*.png" \
  -E "*.webp" \
  -E "*.ts" \
  -E "*.scss" \
  -E "*.br" \
  -E "*.zst" \
  . "${roots[@]}" |
  xargs -0 -r stat --printf '%s\t%n\0' -- |
  sort -z --numeric-sort --reverse |
  cut -z -f2- |
  parallel --null \
    --halt now,fail=1 \
    process_file {} "$@"
