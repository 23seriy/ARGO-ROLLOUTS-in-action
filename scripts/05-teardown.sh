#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# 05 — Teardown: remove everything
# ────────────────────────────────────────────────────────────────
set -euo pipefail

PROFILE="argo-rollouts-demo"

echo "🏀 Argo Rollouts in Action — Teardown"
echo "======================================="

read -rp "This will delete the Minikube cluster '$PROFILE'. Continue? (y/N) " answer
if [[ ! "$answer" =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

echo "🗑️  Deleting namespace argo-rollouts-demo …"
kubectl delete namespace argo-rollouts-demo --ignore-not-found

echo "🗑️  Removing Argo Rollouts controller …"
kubectl delete namespace argo-rollouts --ignore-not-found

echo "🗑️  Cleaning up ClusterRole/Binding for Prometheus …"
kubectl delete clusterrole prometheus-argo-rollouts-demo --ignore-not-found
kubectl delete clusterrolebinding prometheus-argo-rollouts-demo --ignore-not-found

echo "🗑️  Deleting Minikube profile '$PROFILE' …"
minikube delete -p "$PROFILE"

echo ""
echo "✅ Teardown complete — your system is clean."
