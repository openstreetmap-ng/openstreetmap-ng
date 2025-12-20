echo "Available preload datasets:"
echo "  * mazowieckie: Masovian Voivodeship; 1.6 GB download; 60 GB disk space; 15-30 minutes"
read -rp "Preload dataset name [default: mazowieckie]: " dataset
dataset="${dataset:-mazowieckie}"
if [ "$dataset" != "mazowieckie" ]; then
  echo "Invalid dataset name, must be one of: mazowieckie"
  exit 1
fi

echo "Checking for preload data updates"
remote_check_url="https://files.monicz.dev/openstreetmap-ng/preload/$dataset/checksums.b3"
remote_checksums=$(curl -fsSL "$remote_check_url")

mkdir -p "data/preload/$dataset"
while IFS= read -r name; do
  remote_url="https://files.monicz.dev/openstreetmap-ng/preload/$dataset/$name.csv.zst"
  local_file="data/preload/$dataset/$name.csv.zst"
  local_check_file="data/preload/$dataset/$name.csv.zst.b3"

  # recompute checksum if missing but file exists
  if [ -f "$local_file" ] && [ ! -f "$local_check_file" ]; then
    b3sum --no-names "$local_file" >"$local_check_file"
  fi

  # compare with remote checksum
  remote_checksum=$(
    rg -P -m 1 -o --replace '$1' "^([0-9a-fA-F]+)\\s+\\Q$local_file\\E$" <<<"$remote_checksums"
  )
  if cmp -s "$local_check_file" <(echo "$remote_checksum"); then
    echo "File $local_file is up to date"
    continue
  fi

  echo "Downloading $name preload data"
  curl -fL "$remote_url" -o "$local_file"

  # recompute checksum
  local_checksum=$(b3sum --no-names "$local_file")
  echo "$local_checksum" >"$local_check_file"
  if [ "$remote_checksum" != "$local_checksum" ]; then
    echo "[!] Checksum mismatch for $local_file"
    echo "[!] Please retry this command after a few minutes"
    exit 1
  fi
done < <(rg -P -o '[^/[:space:]\\]+(?=[.]csv[.]zst$)' <<<"$remote_checksums")
cp --archive --link --force "data/preload/$dataset/"*.csv.zst data/preload/
