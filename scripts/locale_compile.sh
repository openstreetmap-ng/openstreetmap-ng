#!/bin/sh
set -e

echo "Translating oci files ..."
pipenv run python ./scripts/locale_compile_oci.py

echo "Merging .po files ..."
for file in $(find ./config/locale -type f -name "out-osm-0-all.po"); do
    locale_dir=$(dirname "$file")
    msgcat --use-first "$file" "$locale_dir/oci.po" > "$locale_dir/combined.po"
done

echo "Compiling .po files ..."
for file in $(find ./config/locale -type f -name "combined.po"); do
    msgfmt "$file" -o "${file%.po}.mo";
done
