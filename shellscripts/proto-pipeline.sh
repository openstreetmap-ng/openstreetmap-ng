reference_file="app/models/proto/shared_pb2.py"
if [ ! -f "$reference_file" ]; then
  echo "No protobuf outputs found, compiling..."
else
  changed=0
  while IFS= read -r -d "" proto; do
    if [ "$proto" -nt "$reference_file" ]; then
      changed=1
      break
    fi
  done < <(fd -0 -t f -e proto . app/models/proto)

  ((changed)) || exit 0
  echo "Proto files have changed, recompiling..."
fi

mkdir -p app/views/lib/proto
protoc \
  -I app/models/proto \
  --plugin=node_modules/.bin/protoc-gen-es \
  --es_out app/views/lib/proto \
  --es_opt target=ts \
  --python_out app/models/proto \
  --pyi_out app/models/proto \
  app/models/proto/*.proto
rm app/views/lib/proto/server*
