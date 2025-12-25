if [[ -S $PC_SOCKET_PATH ]]; then
  echo "Services stopping..."
  if ! process-compose down -U; then
    rm -f "$PC_SOCKET_PATH"
  fi
  echo "Services stopped"
else
  echo "Services are not running"
fi
