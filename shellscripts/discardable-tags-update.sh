url="https://taginfo.openstreetmap.org/api/4/keys/discardable"
data=$(curl -fsSL --compressed "$url")
keys=$(echo "$data" | jq '[.data[].key] | unique | sort')
count=$(echo "$keys" | jq 'length')

if [ "$count" -eq 0 ]; then
  echo "Error: discardable keys list is empty"
  exit 1
fi

echo "$keys" | jq . >config/discardable_tags.json
echo "Saved $count discardable tag keys"
