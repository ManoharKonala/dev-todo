#!/bin/bash
PROMETHEUS_URL=${1:-http://localhost:9090}
THRESHOLD=${2:-0.05}
QUERY='rate(http_requests_total{status=~"5.."}[5m])'

echo "============================================"
echo "  HEALTH GATE CHECK"
echo "  Prometheus: $PROMETHEUS_URL"
echo "  Threshold:  $THRESHOLD"
echo "============================================"

RESULT=$(curl -sf "$PROMETHEUS_URL/api/v1/query" \
  --data-urlencode "query=$QUERY" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); v=d['data']['result']; print(float(v[0]['value'][1]) if v else 0)")

echo "Current error rate: $RESULT"

if python3 -c "exit(0 if float('$RESULT') < float('$THRESHOLD') else 1)"; then
  echo "GATE PASSED — error rate $RESULT is below threshold $THRESHOLD"
  exit 0
else
  echo "GATE FAILED — error rate $RESULT exceeds threshold $THRESHOLD"
  exit 1
fi
