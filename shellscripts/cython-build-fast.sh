export CFLAGS="$CFLAGS \
  -O0 \
  -fno-lto \
  -fno-sanitize=all"

export LDFLAGS="$LDFLAGS \
  -fno-lto \
  -fno-sanitize=all"

cython-build
