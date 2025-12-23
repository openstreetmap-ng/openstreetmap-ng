if [[ -S $PC_SOCKET_PATH ]]; then
  echo "Services stopping..."
  process-compose down -U || rm -f "$PC_SOCKET_PATH"
  echo "Services stopped"
else
  echo "Services are not running"
fi
