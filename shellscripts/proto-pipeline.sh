reference_file="app/models/proto/shared_pb2.py"
if [[ ! -f $reference_file ]]; then
  echo "No protobuf outputs found, compiling..."
else
  changed=0
  for proto in app/models/proto/*.proto; do
    [[ $proto -nt $reference_file ]] || continue
    changed=1
    break
  done

  if ((changed == 0)); then
    exit 0
  fi
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
