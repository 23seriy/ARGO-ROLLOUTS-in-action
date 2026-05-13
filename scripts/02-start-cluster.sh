#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# 02 — Start Minikube cluster + install Argo Rollouts controller
# ────────────────────────────────────────────────────────────────
set -euo pipefail

PROFILE="argo-rollouts-demo"
K8S_VERSION="v1.31.0"

echo "🏀 Argo Rollouts in Action — Starting cluster"
echo "==============================================="

# ── Minikube ──────────────────────────────────────────────────
if minikube status -p "$PROFILE" &>/dev/null; then
  echo "✅ Minikube profile '$PROFILE' is already running."
else
  echo "🚀 Creating Minikube cluster (profile=$PROFILE, k8s=$K8S_VERSION) …"
  minikube start \
    -p "$PROFILE" \
    --kubernetes-version="$K8S_VERSION" \
    --cpus=4 \
    --memory=6g \
    --driver=docker
fi

# Make sure kubectl context points at our profile
minikube update-context -p "$PROFILE"
echo "📌 kubectl context set to $PROFILE"

# ── Argo Rollouts controller ─────────────────────────────────
echo ""
echo "📦 Installing Argo Rollouts controller …"
kubectl create namespace argo-rollouts --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argo-rollouts \
  -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

echo "⏳ Waiting for argo-rollouts controller to be ready …"
kubectl rollout status deployment/argo-rollouts -n argo-rollouts --timeout=120s

echo ""
echo "✅ Argo Rollouts controller is running."
kubectl get pods -n argo-rollouts
echo ""
echo "Next → ./scripts/03-deploy-app.sh"
