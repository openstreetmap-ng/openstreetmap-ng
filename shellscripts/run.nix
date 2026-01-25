{
  isDevelopment,
  gunicornPort,
  gunicornWorkers,
  ...
}:
(
  if isDevelopment then
    ''
      exec python -m uvicorn app.main:app \
        --reload \
        --reload-include "*.mo" \
        --reload-exclude scripts \
        --reload-exclude tests \
        --reload-exclude typings
    ''
  else
    ''
      exec python -m gunicorn app.main:app \
        --bind localhost:${toString gunicornPort} \
        --workers ${toString gunicornWorkers} \
        --worker-class uvicorn_worker.UvicornWorker \
        --max-requests 10000 \
        --max-requests-jitter 1000 \
        --graceful-timeout 5 \
        --keep-alive 300 \
        --access-logfile -
    ''
)
