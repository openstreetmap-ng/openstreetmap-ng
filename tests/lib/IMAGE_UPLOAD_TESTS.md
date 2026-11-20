# Image upload regression boundaries

Normal project tests use the documented Nix environment and `run-tests`.
The added `test_image_upload_errors.py` also supports a focused native probe:

```sh
uv run --no-project --python 3.14 --with pillow==12.2.0 --with cython==3.2.4 --with blurhash-rs==1.1.0 --with sizestr==1.2.1 --with fastapi==0.136.1 --with pytest==9.0.3 --with pytest-asyncio==1.3.0 python tests/lib/image_native_probe.py
```

These image/test package versions match `uv.lock`; this is not a full dependency
sync. The probe runs the actual image module, real Pillow, actual default
exceptions/APIError and model type aliases. Configuration is selected from the
source AST through a small whitelist. Unused native element-ID bindings are
explicit boundaries that raise if called; no image operation is stubbed.
`--noconftest` deliberately excludes database/application lifespan setup.
The missing optional NSFW model warning is expected and is not content-safety
validation. The probe does not prove HTTP/RPC, authentication, database or
Cython-compiled execution. Cython source-to-C translation is a separate check.

The bomb tests lower Pillow's threshold for tiny 8x8 and 4x4 PNGs rather than
allocating a huge image. Corrupt/empty data, default error status, background
decoding, valid WebP output and propagation of unrelated runtime errors are
covered.

Browser regression:

```sh
bun test tests/views/utils/image-upload.test.ts
```

It requires Playwright and installed Chrome; `PLAYWRIGHT_PACKAGE` can point to an
external Playwright module entry point. The actual StandardForm, upload helper,
Bootstrap feedback, browser files and Preact run. RPC/protobuf, password
collection and unused map hooks are boundaries. The fixture uses a small 1024
byte server-limit value to test both sides of the boundary without allocating a
large file. It does not run the complete profile/application page or a real RPC
request. Set `IMAGE_UPLOAD_SCREENSHOT_DIR` to an existing directory for screenshots.

The production helper uses `REQUEST_BODY_MAX_SIZE`, not the compressed avatar
or background output target. A file at that limit passing preflight is not a
promise that a complete encoded HTTP request of that size will be accepted.
