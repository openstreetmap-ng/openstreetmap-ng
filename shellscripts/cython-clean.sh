rm -rf build/
rm -f -- \
  app/*.{c,html,so,pyd} \
  app/!(static|views)/**/*.{c,html,so,pyd} \
  scripts/**/*.{c,html,so,pyd}
