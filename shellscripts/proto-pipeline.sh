tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

buf export \
  . \
  -o "$tmp/export" \
  --path app/models/proto

proto_files=(
  "$tmp/export"/app/models/proto/*.proto
  "$tmp/export"/buf/validate/*.proto
)

for src in "${proto_files[@]}"; do
  sed -E 's@^import "(app/models/proto|buf/validate)/([^"]+)";@import "\2";@' \
    "$src" >"$tmp/${src##*/}"
done
rm -rf "$tmp/export"

printf 'version: v2\nmodules:\n  - path: .\n' >"$tmp/buf.yaml"

buf generate \
  --template "$PWD/buf.gen.web.yaml" \
  --output "$PWD" \
  --config "$tmp/buf.yaml" \
  "$tmp"

buf generate \
  --template buf.gen.yaml \
  --path app/models/proto
