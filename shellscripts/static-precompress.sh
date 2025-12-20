process_file() {
  file="$1"
  mode="$2"

  process_file_inner() {
    dest="$file.$extension"
    if [ "$mode" = "clean" ]; then
      rm -f "$dest"
      return
    fi
    if [ ! -f "$dest" ] || [ "$dest" -ot "$file" ]; then
      tmpfile=$(mktemp -t "$(basename "$dest").XXXXXXXXXX")
      $compressor "${args[@]}" "$file" -o "$tmpfile"
      touch --reference "$file" "$tmpfile"
      mv -f "$tmpfile" "$dest"
    fi
  }

  extension="zst"
  compressor="zstd"
  args=(--force --ultra -22 --single-thread --quiet)
  process_file_inner

  extension="br"
  compressor="brotli"
  args=(--force --best)
  process_file_inner
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
