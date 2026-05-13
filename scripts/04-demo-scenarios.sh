#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# 04 — Interactive demo scenarios for Argo Rollouts
# ────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
NS="argo-rollouts-demo"

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

banner() { echo -e "\n${CYAN}${BOLD}══════════════════════════════════════════════${NC}"; echo -e "${CYAN}${BOLD}  $1${NC}"; echo -e "${CYAN}${BOLD}══════════════════════════════════════════════${NC}\n"; }
info()   { echo -e "${GREEN}▸ $1${NC}"; }
warn()   { echo -e "${YELLOW}▸ $1${NC}"; }

wait_for_enter() {
  echo ""
  read -rp "Press ENTER to continue …"
  echo ""
}

show_status() {
  echo ""
  kubectl argo rollouts get rollout scores-api -n "$NS" --no-color 2>/dev/null || true
  echo ""
}

# ── Reset to v1 baseline ─────────────────────────────────────
reset_to_v1() {
  info "Resetting to v1 baseline …"
  kubectl apply -f "$PROJECT_DIR/k8s/scores-api-rollout.yaml"
  sleep 5
  kubectl argo rollouts status scores-api -n "$NS" --timeout 60s 2>/dev/null || true
}

echo "🏀 Argo Rollouts in Action — Demo Scenarios"
echo "============================================="
echo ""
echo "Make sure you have these running in separate terminals:"
echo "  1) kubectl port-forward svc/scores-api-stable 9080:8080 -n $NS"
echo "  2) kubectl argo rollouts dashboard -n $NS"
echo "  3) kubectl port-forward svc/prometheus 9090:9090 -n $NS"
echo ""
echo "Dashboard:  http://localhost:3100"
echo "App:        http://localhost:9080"
echo "Prometheus: http://localhost:9090"

wait_for_enter

# ══════════════════════════════════════════════════════════════
# Scenario 1: Basic Canary
# ══════════════════════════════════════════════════════════════
banner "Scenario 1: Basic Canary — Timed Steps"
info "Like opening arena gates gradually: 10% → 30% → 60% → 100%"
info "Each step pauses for 30 seconds before advancing."
echo ""
info "Applying canary-basic.yaml …"
kubectl apply -f "$PROJECT_DIR/rollouts/canary-basic.yaml"
echo ""
info "Watch the rollout progress in the dashboard (http://localhost:3100)"
info "Or monitor here:"
echo ""
echo "  kubectl argo rollouts get rollout scores-api -n $NS -w"
echo ""
warn "The canary will automatically promote through all steps (~2 min total)."

wait_for_enter
show_status

# ══════════════════════════════════════════════════════════════
# Scenario 2: Manual Canary
# ══════════════════════════════════════════════════════════════
banner "Scenario 2: Manual Canary — Coach Calls the Plays"
info "Each step pauses indefinitely until you promote."
echo ""
reset_to_v1
echo ""
info "Applying canary-manual.yaml …"
kubectl apply -f "$PROJECT_DIR/rollouts/canary-manual.yaml"
echo ""
info "The rollout is paused at 10%. Promote when ready:"
echo "  kubectl argo rollouts promote scores-api -n $NS"
echo ""
info "To abort/rollback at any point:"
echo "  kubectl argo rollouts abort scores-api -n $NS"
echo ""
warn "Try promoting a couple steps, then abort to see the rollback."

wait_for_enter
show_status

# ══════════════════════════════════════════════════════════════
# Scenario 3: Canary with Analysis (Success)
# ══════════════════════════════════════════════════════════════
banner "Scenario 3: Canary + Analysis — Ref Reviews the Play (Pass)"
info "Prometheus checks success rate at each step."
info "v2 with ERROR_RATE=0 → analysis passes → auto-promotes."
echo ""
reset_to_v1
echo ""
info "Applying canary-with-analysis.yaml …"
kubectl apply -f "$PROJECT_DIR/rollouts/canary-with-analysis.yaml"
echo ""
info "Watch the AnalysisRun progress:"
echo "  kubectl get analysisrun -n $NS -w"
echo ""
warn "With a healthy v2, all analysis checks should pass."

wait_for_enter
show_status

# ══════════════════════════════════════════════════════════════
# Scenario 4: Canary with Analysis (Fail → Rollback)
# ══════════════════════════════════════════════════════════════
banner "Scenario 4: Canary + Analysis — Bad Version Gets Ejected"
info "v2 with ERROR_RATE=0.4 (40% failures) → analysis fails → auto-rollback!"
info "Like a player fouling out — pulled automatically."
echo ""
reset_to_v1
echo ""
info "Applying canary-with-analysis-fail.yaml …"
kubectl apply -f "$PROJECT_DIR/rollouts/canary-with-analysis-fail.yaml"
echo ""
info "Watch for the automatic rollback:"
echo "  kubectl argo rollouts get rollout scores-api -n $NS -w"
echo "  kubectl get analysisrun -n $NS"
echo ""
warn "The analysis should detect the high error rate and trigger rollback."

wait_for_enter
show_status

# ══════════════════════════════════════════════════════════════
# Scenario 5: Blue-Green (Manual)
# ══════════════════════════════════════════════════════════════
banner "Scenario 5: Blue-Green — Swap the Starting Lineup"
info "Full v2 is deployed alongside v1. Traffic stays on v1 (stable)."
info "Preview service lets you test v2 before switching."
echo ""
reset_to_v1
echo ""
info "Applying blue-green.yaml …"
kubectl apply -f "$PROJECT_DIR/rollouts/blue-green.yaml"
echo ""
info "Preview the new version:"
echo "  kubectl port-forward svc/scores-api-canary 9081:8080 -n $NS"
echo "  open http://localhost:9081  (should show v2)"
echo ""
info "Promote when satisfied:"
echo "  kubectl argo rollouts promote scores-api -n $NS"

wait_for_enter
show_status

# ══════════════════════════════════════════════════════════════
# Scenario 6: Blue-Green Auto-Promote
# ══════════════════════════════════════════════════════════════
banner "Scenario 6: Blue-Green Auto-Promote — Timeout Ends, New Lineup In"
info "Same as blue-green, but auto-promotes after 60 seconds."
echo ""
reset_to_v1
echo ""
info "Applying blue-green-auto.yaml …"
kubectl apply -f "$PROJECT_DIR/rollouts/blue-green-auto.yaml"
echo ""
info "v2 will be promoted automatically after 60 seconds."
echo ""
warn "Watch the transition in the dashboard."

wait_for_enter
show_status

# ══════════════════════════════════════════════════════════════
banner "🎉 All Scenarios Complete!"
echo ""
info "Run ./scripts/05-teardown.sh to clean up when done."
echo ""
