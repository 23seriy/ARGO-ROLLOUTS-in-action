#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# Open the Argo Rollouts dashboard + supporting port-forwards
# ────────────────────────────────────────────────────────────────
set -euo pipefail

NS="argo-rollouts-demo"

echo "🏀 Argo Rollouts in Action — Dashboard & Port-Forwards"
echo "========================================================"
echo ""
echo "Choose what to open:"
echo "  1) Argo Rollouts Dashboard (http://localhost:3100)"
echo "  2) NBA Scores API          (http://localhost:9080)"
echo "  3) Prometheus               (http://localhost:9090)"
echo "  4) All of the above"
echo ""
read -rp "Enter choice [1-4]: " choice

case "$choice" in
  1)
    echo "🚀 Starting Argo Rollouts Dashboard …"
    kubectl argo rollouts dashboard -n "$NS"
    ;;
  2)
    echo "🏀 Port-forwarding Scores API …"
    kubectl port-forward svc/scores-api-stable 9080:8080 -n "$NS"
    ;;
  3)
    echo "📊 Port-forwarding Prometheus …"
    kubectl port-forward svc/prometheus 9090:9090 -n "$NS"
    ;;
  4)
    echo "🚀 Starting all services …"
    echo "   Dashboard:  http://localhost:3100"
    echo "   Scores API: http://localhost:9080"
    echo "   Prometheus: http://localhost:9090"
    echo ""
    kubectl port-forward svc/scores-api-stable 9080:8080 -n "$NS" &
    kubectl port-forward svc/prometheus 9090:9090 -n "$NS" &
    kubectl argo rollouts dashboard -n "$NS"
    ;;
  *)
    echo "Invalid choice."
    exit 1
    ;;
esac
