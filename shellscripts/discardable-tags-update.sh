url="https://taginfo.openstreetmap.org/api/4/keys/discardable"
data=$(curl -fsSL --compressed "$url")
keys=$(jq '[.data[].key] | unique | sort' <<<"$data")
count=$(jq 'length' <<<"$keys")

if ((count == 0)); then
  echo "Error: discardable keys list is empty"
  exit 1
fi

jq . <<<"$keys" >config/discardable_tags.json
echo "Saved $count discardable tag keys"
