# 🏀 Argo Rollouts in Action

A hands-on project demonstrating **Argo Rollouts** progressive delivery on a local Minikube cluster. Built with a simple NBA Live Scores API to showcase canary deployments, blue-green releases, and automated analysis — all running on your laptop.

![Argo Rollouts](https://img.shields.io/badge/Argo_Rollouts-latest-EF7B4D?logo=argo&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.31+-326CE5?logo=kubernetes&logoColor=white)
![Minikube](https://img.shields.io/badge/Minikube-local-F7B93E?logo=kubernetes&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)

> 📝 **Read the full walkthrough on Medium:** *[link coming soon]*

## 🏗️ Architecture

```text
                    ┌──────────────────────────────────────────────┐
                    │              Minikube Cluster                 │
                    │                                              │
  NBA Fan ────────► │  ┌─────────────────┐   ┌─────────────────┐  │
  localhost:9080    │  │  Scores API v1   │   │  Scores API v2  │  │
                    │  │  (stable/blue)   │   │  (canary/green) │  │
                    │  └────────┬────────┘   └────────┬────────┘  │
                    │           │                      │           │
                    │     Argo Rollouts Controller                 │
                    │     ──────────────────────────               │
                    │     routes 90% ──► v1                        │
                    │     routes 10% ──► v2 (canary)               │
                    │                                              │
                    │  ┌──────────────┐   ┌───────────────────┐   │
                    │  │  Prometheus  │──►│  AnalysisRun      │   │
                    │  │  (metrics)   │   │  (success rate?)  │   │
                    │  └──────────────┘   └───────────────────┘   │
                    │                                              │
                    │  ┌──────────────────┐                       │
                    │  │ Traffic Generator │  game-night load      │
                    │  └──────────────────┘                       │
                    └──────────────────────────────────────────────┘
```

**Scores API v1** — Returns basic NBA box scores (team, score, quarter, arena). This is the stable "production" version.

**Scores API v2** — Same box scores **plus live play-by-play** data (player actions, timestamps). This is the new version you progressively deliver.

**Traffic Generator** — Simulates game-night fan traffic so Prometheus has data for automated analysis during rollouts.

**Prometheus** — Scrapes `/metrics` from the Scores API pods. The AnalysisTemplate queries success rate to decide: promote or rollback.

## 📋 What You'll Learn

| Argo Rollouts Feature | What It Does | Demo Scenario |
|---|---|---|
| **Canary (Timed)** | Gradually shift traffic with automatic step progression | 10% → 30% → 60% → 100% over ~2 min |
| **Canary (Manual)** | Pause at each step until you explicitly promote | Coach reviews before calling the next play |
| **Canary + Analysis** | Prometheus checks success rate; auto-promotes on pass | Ref reviews the play on the jumbotron |
| **Canary + Analysis (Fail)** | Same analysis but v2 has 40% errors → auto-rollback | Player fouled out — pulled from the game |
| **Blue-Green** | Deploy full v2 alongside v1; preview before switching | Swap the entire starting lineup at once |
| **Blue-Green Auto** | Same but auto-promotes after a timeout | Timeout ends, new lineup is in |
| **Rollback** | Instantly revert to the previous stable version | Call a timeout and revert the play |

## 🚀 Quick Start

### Step 0: Clone the Repository

```bash
git clone https://github.com/23seriy/argo-rollouts-in-action.git
cd argo-rollouts-in-action
```

### Prerequisites

- **macOS** (scripts use Homebrew; adapt for Linux)
- **Docker Desktop** running
- ~6 GB RAM available for the Minikube cluster

### Step 1: Install Tools

```bash
chmod +x scripts/*.sh
./scripts/01-install-prerequisites.sh
```

This installs `minikube`, `kubectl`, `helm`, and the `kubectl-argo-rollouts` plugin via Homebrew if not already present.

### Step 2: Start Cluster + Install Argo Rollouts

```bash
./scripts/02-start-cluster.sh
```

Creates a Minikube cluster (`argo-rollouts-demo` profile) with 4 CPUs and 6 GB RAM, then installs the Argo Rollouts controller.

### Step 3: Build & Deploy the Application

```bash
./scripts/03-deploy-app.sh
```

Builds Docker images inside Minikube's Docker daemon (no registry needed), deploys Prometheus, the Scores API rollout (v1), and the traffic generator.

### Step 4: Access the Application

In **separate terminals**, start:

```bash
# Terminal 1: Scores API
kubectl port-forward svc/scores-api-stable 9080:8080 -n argo-rollouts-demo

# Terminal 2: Argo Rollouts Dashboard
kubectl argo rollouts dashboard -n argo-rollouts-demo

# Terminal 3: Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n argo-rollouts-demo
```

Open:
- **http://localhost:9080** — NBA Scores API (stable)
- **http://localhost:3100** — Argo Rollouts Dashboard
- **http://localhost:9090** — Prometheus

### Step 5: Run the Demo Scenarios

```bash
./scripts/04-demo-scenarios.sh
```

This walks you through each scenario interactively.

## 🎮 Demo Scenarios

### 1. Basic Canary — Opening the Arena Gates

```bash
kubectl apply -f rollouts/canary-basic.yaml
```

Traffic gradually shifts from v1 to v2 in timed steps (10% → 30% → 60% → 100%). Watch the dashboard as the canary progresses automatically.

### 2. Manual Canary — Coach Calls the Plays

```bash
kubectl apply -f rollouts/canary-manual.yaml
```

Pauses at each step. You decide when to advance:

```bash
# Promote to the next step
kubectl argo rollouts promote scores-api -n argo-rollouts-demo

# Or abort and rollback
kubectl argo rollouts abort scores-api -n argo-rollouts-demo
```

### 3. Canary + Automated Analysis (Pass)

```bash
kubectl apply -f rollouts/canary-with-analysis.yaml
```

Prometheus checks that the success rate stays ≥ 95%. With a healthy v2, all checks pass and the canary auto-promotes. Watch the AnalysisRun:

```bash
kubectl get analysisrun -n argo-rollouts-demo -w
```

### 4. Canary + Automated Analysis (Fail → Rollback)

```bash
kubectl apply -f rollouts/canary-with-analysis-fail.yaml
```

This deploys v2 with `ERROR_RATE=0.4` (40% of requests return 500). The analysis detects the bad success rate and **automatically rolls back** — like a player getting ejected for too many fouls.

### 5. Blue-Green — Swap the Starting Lineup

```bash
kubectl apply -f rollouts/blue-green.yaml
```

Full v2 is deployed alongside v1. Stable traffic stays on v1. Preview v2 through the canary service:

```bash
kubectl port-forward svc/scores-api-canary 9081:8080 -n argo-rollouts-demo
# Open http://localhost:9081 to see v2
```

Promote when satisfied:

```bash
kubectl argo rollouts promote scores-api -n argo-rollouts-demo
```

### 6. Blue-Green Auto-Promote

```bash
kubectl apply -f rollouts/blue-green-auto.yaml
```

Same as blue-green, but automatically promotes after 60 seconds.

## 📊 Dashboards

### Argo Rollouts Dashboard

```bash
kubectl argo rollouts dashboard -n argo-rollouts-demo
# Open http://localhost:3100
```

Visualize the rollout state, step progression, canary weight, and revision history in real-time.

### Prometheus

```bash
kubectl port-forward svc/prometheus 9090:9090 -n argo-rollouts-demo
# Open http://localhost:9090
```

Query the metrics that power the AnalysisRuns:

```promql
# Success rate (what the AnalysisTemplate checks)
sum(rate(scores_api_requests_total{status="200"}[1m])) /
sum(rate(scores_api_requests_total[1m]))

# Request rate by version
sum by (version) (rate(scores_api_requests_total[1m]))
```

## 📁 Project Structure

```text
argo-rollouts-in-action/
├── apps/
│   ├── scores-api/              # NBA Scores API (Flask) — v1 basic, v2 + play-by-play
│   │   ├── app.py               # Single source, version set via APP_VERSION env
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── traffic-generator/       # Simulates game-night fan traffic
│       ├── app.py
│       ├── Dockerfile
│       └── requirements.txt
├── k8s/                         # Kubernetes manifests
│   ├── namespace.yaml
│   ├── scores-api-rollout.yaml  # Default Rollout (starts with v1 canary strategy)
│   ├── scores-api-service.yaml  # Stable + canary Services
│   └── traffic-generator.yaml
├── rollouts/                    # Argo Rollouts strategy manifests
│   ├── canary-basic.yaml             # Timed canary: 10→30→60→100
│   ├── canary-manual.yaml            # Manual promotion at each step
│   ├── canary-with-analysis.yaml     # Canary + Prometheus analysis (pass)
│   ├── canary-with-analysis-fail.yaml # Canary + analysis (fail → rollback)
│   ├── blue-green.yaml               # Blue-green with manual promote
│   ├── blue-green-auto.yaml          # Blue-green with auto-promote (60s)
│   └── analysis-template.yaml        # AnalysisTemplate — success rate check
├── monitoring/
│   └── prometheus-deployment.yaml     # Prometheus (metrics for AnalysisRuns)
├── scripts/                     # Automation scripts
│   ├── 01-install-prerequisites.sh
│   ├── 02-start-cluster.sh
│   ├── 03-deploy-app.sh
│   ├── 04-demo-scenarios.sh
│   ├── 05-teardown.sh
│   └── open-dashboard.sh
├── docs/
│   └── medium-story.md          # Companion Medium article draft
└── .gitignore
```

## 🧹 Teardown

```bash
./scripts/05-teardown.sh
```

Deletes the namespace, uninstalls Argo Rollouts, removes the Prometheus ClusterRole/Binding, and deletes the Minikube cluster. Your system is back to clean state.

## 💡 Key Takeaways

1. **Progressive delivery reduces blast radius** — Canary releases let you test with real traffic at low percentages before going all-in. A bad deploy affects 10% of fans, not 100%.

2. **Automated analysis closes the feedback loop** — Instead of a human watching dashboards, Argo Rollouts queries Prometheus and decides: promote or rollback. Ship faster with confidence.

3. **Blue-green gives instant switchover** — When you need atomic releases (all-or-nothing), blue-green deploys the full new version alongside the old. One command switches traffic.

4. **Rollbacks are instant** — Whether automated (failed analysis) or manual (`kubectl argo rollouts abort`), reverting to the stable version happens in seconds.

5. **It's just Kubernetes** — Argo Rollouts enhances standard Deployments. Your existing CI/CD, monitoring, and tooling work alongside it.

## 📚 Resources

- [Argo Rollouts Documentation](https://argoproj.github.io/argo-rollouts/)
- [Argo Rollouts — Canary Strategy](https://argoproj.github.io/argo-rollouts/features/canary/)
- [Argo Rollouts — Blue-Green Strategy](https://argoproj.github.io/argo-rollouts/features/bluegreen/)
- [Argo Rollouts — Analysis & Progressive Delivery](https://argoproj.github.io/argo-rollouts/features/analysis/)
- [Prometheus Documentation](https://prometheus.io/docs/introduction/overview/)
- [Minikube Documentation](https://minikube.sigs.k8s.io/docs/)

## 📝 License

MIT — Use freely for learning, demos, and presentations.
