tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mapfile -t service_protos < <(rg -l '^service ' app/models/proto --glob '*.proto' | sort)

buf_export_args=(. -o "$tmp/export" --path app/models/proto/shared.proto)
for p in "${service_protos[@]}"; do
  buf_export_args+=(--path "$p")
done

buf export "${buf_export_args[@]}"

for src in "$tmp/export"/**/*.proto; do
  sed -E 's@^import "(app/models/proto|buf/validate)/([^"]+)";@import "\2";@' "$src" >"$tmp/${src##*/}"
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
