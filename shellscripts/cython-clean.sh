rm -rf build/
fd \
  --type f \
  --extension c \
  --extension html \
  --extension so \
  --exclude static \
  --exclude views \
  . app scripts \
  -x rm -f -- {}
