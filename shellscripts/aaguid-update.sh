url="https://raw.githubusercontent.com/passkeydeveloper/passkey-authenticator-aaguids/main/combined_aaguid.json"
data=$(curl -fsSL --compressed "$url")

count=$(jq 'length' <<<"$data")
if ((count == 0)); then
  echo "Error: AAGUID database is empty"
  exit 1
fi

jq --sort-keys . <<<"$data" >config/aaguid.json
echo "Saved $count AAGUID entries"
