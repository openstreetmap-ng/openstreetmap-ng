url="https://raw.githubusercontent.com/passkeydeveloper/passkey-authenticator-aaguids/main/combined_aaguid.json"
data=$(curl -fsSL --compressed "$url")

if [ "$(echo "$data" | jq 'length')" -eq 0 ]; then
  echo "Error: AAGUID database is empty"
  exit 1
fi

echo "$data" | jq --sort-keys . >config/aaguid.json
echo "Saved $(echo "$data" | jq 'length') AAGUID entries"
