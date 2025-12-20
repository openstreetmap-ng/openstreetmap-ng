rm -rf build/
fd -I \
  -t f \
  -e c \
  -e html \
  -e so \
  -E static \
  -E views \
  . app scripts \
  -x rm -f -- {}
