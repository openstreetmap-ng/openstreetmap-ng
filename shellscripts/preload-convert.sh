python scripts/preload_convert.py "$@"
for file in data/preload/*.csv; do
  zstd \
    --rm \
    --force -19 \
    --threads "$(($(nproc) * 2))" \
    "$file"
done
