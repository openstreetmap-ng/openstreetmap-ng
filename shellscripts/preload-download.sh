echo "Available preload datasets:"
echo "  * mazowieckie: Masovian Voivodeship; 1.6 GB download; 60 GB disk space; 15-30 minutes"
read -rp "Preload dataset name [default: mazowieckie]: " dataset
dataset="${dataset:-mazowieckie}"
if [[ $dataset != mazowieckie ]]; then
  echo "Invalid dataset name, must be one of: mazowieckie"
  exit 1
fi

echo "Checking for preload data updates"
remote_check_url="https://files.monicz.dev/openstreetmap-ng/preload/$dataset/checksums.b3"
remote_checksums=$(curl -fsSL "$remote_check_url")

local_dir=data/preload/$dataset
mkdir -p "$local_dir"

while read -r remote_checksum remote_file; do
  remote_file=${remote_file#\*}
  basename=${remote_file##*/}
  if [[ $basename != *.csv.zst ]]; then
    continue
  fi

  name=${basename%.csv.zst}
  remote_url=https://files.monicz.dev/openstreetmap-ng/preload/$dataset/$basename
  local_file=$local_dir/$basename
  local_check_file=$local_file.b3

  # recompute checksum if missing but file exists
  if [[ -f $local_file && ! -f $local_check_file ]]; then
    b3sum --no-names "$local_file" >"$local_check_file"
  fi

  local_checksum=
  { read -r local_checksum <"$local_check_file"; } 2>/dev/null || true
  if [[ -f $local_file && $local_checksum == "$remote_checksum" ]]; then
    echo "File $local_file is up to date"
    continue
  fi

  echo "Downloading $name preload data"
  curl -fL "$remote_url" -o "$local_file"

  local_checksum=$(b3sum --no-names "$local_file")
  echo "$local_checksum" >"$local_check_file"
  if [[ $local_checksum != "$remote_checksum" ]]; then
    echo "[!] Checksum mismatch for $local_file"
    echo "[!] Please retry this command after a few minutes"
    exit 1
  fi
done <<<"$remote_checksums"

cp --archive --link --force "$local_dir/"*.csv.zst data/preload/
