#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# 03 — Build images & deploy the NBA Scores API + supporting infra
# ────────────────────────────────────────────────────────────────
set -euo pipefail

PROFILE="argo-rollouts-demo"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🏀 Argo Rollouts in Action — Build & Deploy"
echo "============================================="

# ── Point Docker at Minikube ──────────────────────────────────
echo "🐳 Configuring Docker to use Minikube daemon …"
eval "$(minikube docker-env -p "$PROFILE")"

# ── Build images ──────────────────────────────────────────────
echo ""
echo "🔨 Building scores-api:v1 …"
docker build \
  --build-arg APP_VERSION=v1 \
  -t scores-api:v1 \
  "$PROJECT_DIR/apps/scores-api"

echo "🔨 Building scores-api:v2 …"
docker build \
  --build-arg APP_VERSION=v2 \
  -t scores-api:v2 \
  "$PROJECT_DIR/apps/scores-api"

echo "🔨 Building traffic-generator …"
docker build \
  -t traffic-generator:latest \
  "$PROJECT_DIR/apps/traffic-generator"

# ── Create namespace ──────────────────────────────────────────
echo ""
echo "📁 Creating namespace …"
kubectl apply -f "$PROJECT_DIR/k8s/namespace.yaml"

# ── Deploy Prometheus (needed for AnalysisRuns) ───────────────
echo "📊 Deploying Prometheus …"
kubectl apply -f "$PROJECT_DIR/monitoring/prometheus-deployment.yaml"

# ── Deploy services ───────────────────────────────────────────
echo "🌐 Deploying services …"
kubectl apply -f "$PROJECT_DIR/k8s/scores-api-service.yaml"

# ── Deploy AnalysisTemplate ───────────────────────────────────
echo "🔬 Deploying AnalysisTemplate …"
kubectl apply -f "$PROJECT_DIR/rollouts/analysis-template.yaml"

# ── Deploy the Rollout (starts with v1) ───────────────────────
echo "🚀 Deploying scores-api Rollout (v1) …"
kubectl apply -f "$PROJECT_DIR/k8s/scores-api-rollout.yaml"

# ── Deploy traffic generator ─────────────────────────────────
echo "🚗 Deploying traffic generator …"
kubectl apply -f "$PROJECT_DIR/k8s/traffic-generator.yaml"

# ── Wait for pods ─────────────────────────────────────────────
echo ""
echo "⏳ Waiting for pods to be ready …"
kubectl rollout status deployment/prometheus -n argo-rollouts-demo --timeout=90s
kubectl rollout status deployment/traffic-generator -n argo-rollouts-demo --timeout=90s

# Rollouts use a different status check
echo "⏳ Waiting for scores-api Rollout …"
kubectl argo rollouts status scores-api -n argo-rollouts-demo --timeout 90s 2>/dev/null || true

echo ""
echo "✅ All components deployed!"
echo ""
kubectl get pods -n argo-rollouts-demo
echo ""
echo "────────────────────────────────────────────"
echo "Access the app:"
echo "  kubectl port-forward svc/scores-api-stable 9080:8080 -n argo-rollouts-demo"
echo "  open http://localhost:9080"
echo ""
echo "Open the Argo Rollouts dashboard:"
echo "  kubectl argo rollouts dashboard -n argo-rollouts-demo"
echo "  open http://localhost:3100"
echo ""
echo "Open Prometheus:"
echo "  kubectl port-forward svc/prometheus 9090:9090 -n argo-rollouts-demo"
echo "  open http://localhost:9090"
echo ""
echo "Next → ./scripts/04-demo-scenarios.sh"
