{
  isDevelopment,
  webPort,
  webWorkers,
  webMaxRequests,
  webMaxRequestsJitter,
  ...
}:
(
  if isDevelopment then
    ''
      exec python -m h2corn app.main:app \
        --port ${toString webPort} \
        --reload \
        --reload-include "*.mo" \
        --reload-exclude scripts \
        --reload-exclude tests \
        --reload-exclude typings
    ''
  else
    ''
      exec python -m h2corn app.main:app \
        --port ${toString webPort} \
        --workers ${toString webWorkers} \
        --max-requests ${toString webMaxRequests} \
        --max-requests-jitter ${toString webMaxRequestsJitter} \
        --proxy-headers \
        --no-http1
    ''
)
