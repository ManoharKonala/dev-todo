#!/bin/bash
NAMESPACE=${1:-todoflow-prod}
COLOR=${2:-green}
echo "============================================"
echo "  PROMOTE — Namespace: $NAMESPACE"
echo "  Switching traffic to: $COLOR"
echo "============================================"
kubectl patch service todoflow-svc -n $NAMESPACE \
  --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/spec/selector/deploy_color\", \"value\": \"$COLOR\"}]"
echo "Traffic now routed to: $COLOR"
kubectl get service todoflow-svc -n $NAMESPACE -o jsonpath='{.spec.selector}'
echo ""
echo "============================================"
echo "  PROMOTION COMPLETE"
echo "============================================"
