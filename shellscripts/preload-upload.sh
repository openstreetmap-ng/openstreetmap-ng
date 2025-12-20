read -rp "Preload dataset name: " dataset
if [ "$dataset" != "mazowieckie" ]; then
  echo "Invalid dataset name, must be one of: mazowieckie"
  exit 1
fi
mkdir -p "data/preload/$dataset"
cp --archive --link --force data/preload/*.csv.zst "data/preload/$dataset/"
echo "Computing checksums file"
b3sum "data/preload/$dataset/"*.csv.zst >"data/preload/$dataset/checksums.b3"
rsync \
  --verbose \
  --archive \
  --checksum \
  --whole-file \
  --delay-updates \
  --human-readable \
  --progress \
  "data/preload/$dataset/"*.csv.zst \
  "data/preload/$dataset/checksums.b3" \
  edge:"/var/www/files.monicz.dev/openstreetmap-ng/preload/$dataset/"
