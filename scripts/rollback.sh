#!/bin/bash
NAMESPACE=${1:-todoflow-dev}
echo "============================================"
echo "  ROLLBACK — Namespace: $NAMESPACE"
echo "============================================"
echo "Initiating rollback in namespace: $NAMESPACE"
kubectl rollout undo deployment/todoflow-green -n $NAMESPACE
kubectl rollout status deployment/todoflow-green -n $NAMESPACE --timeout=60s
echo "Rollback complete in $NAMESPACE"
echo "============================================"
