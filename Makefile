.PHONY: setup clean update version load-osm locale-compile dev-start dev-stop dev-logs zstd-tracks-download zstd-tracks

setup:
	# compile protobuf
	protoc --proto_path=proto --python_betterproto_out=proto proto/*.proto
	# compile cython
	pipenv run python setup.py build_ext --build-lib cython_lib

clean:
	rm -rf proto/*_pb2.py
	rm -rf build/ cython_lib/*{.c,.so,.html}

update:
	docker push $$(docker load < $$(nix-build --no-out-link) | sed -En 's/Loaded image: (\S+)/\1/p')

version:
	sed -i -r "s|VERSION = '([0-9.]+)'|VERSION = '\1.$$(date +%y%m%d)'|g" config.py

load-osm:
	pipenv run python ./scripts/load_osm.py $$(find . -maxdepth 1 -name '*.osm' -print -quit)

locale-compile:
	./scripts/locale_compile.sh

dev-start:
	docker compose -f docker-compose.dev.yml up -d

dev-stop:
	docker compose -f docker-compose.dev.yml down

dev-logs:
	docker compose -f docker-compose.dev.yml logs -f

zstd-tracks-download:
	pipenv run python ./scripts/zstd_tracks_download.py

zstd-tracks:
	zstd -o zstd/tracks.dict -19 --train-fastcover $$(find zstd/tracks/ -type f -name '*.gpx' -print0 | xargs -0)
