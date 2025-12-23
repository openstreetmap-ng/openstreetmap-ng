# shellcheck disable=SC2016
(if [[ -t 0 ]]; then git ls-files; else cat; fi) | parallel \
  --no-run-if-empty \
  --halt now,fail=1 '
    timestamp=$(git log -1 --format=%ct -- {})
    touch -d "@$timestamp" {}
  '
