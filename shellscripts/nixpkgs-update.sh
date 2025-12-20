hash=$(
  curl -fsSL \
    https://prometheus.nixos.org/api/v1/query \
    -d 'query=channel_revision{channel="nixpkgs-unstable"}' |
    jq -r ".data.result[0].metric.revision"
)
sed -i "s|nixpkgs/archive/[0-9a-f]\\{40\\}|nixpkgs/archive/$hash|" shell.nix
echo "Nixpkgs updated to $hash"
