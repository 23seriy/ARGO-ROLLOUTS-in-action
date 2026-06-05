# CLAUDE.md — Argo Rollouts in Action

## Project Overview

Hands-on demo of **Argo Rollouts** progressive delivery on a local Minikube cluster. Uses an NBA Live Scores API to showcase canary deployments, blue-green releases, and automated analysis.

## Tech Stack

- **App**: Python/Flask (scores-api, traffic-generator)
- **Platform**: Minikube (profile: `argo-rollouts-demo`)
- **Tool**: Argo Rollouts controller + kubectl plugin
- **Container**: Docker (images built inside Minikube's Docker daemon)

## Project Structure

```
apps/                  # Application source code
  scores-api/          # NBA Scores API (Flask, Python 3.12)
  traffic-generator/   # Generates HTTP traffic for analysis
k8s/                   # Base Kubernetes manifests (namespace, service, rollout)
rollouts/              # Argo Rollouts strategies (canary, blue-green, analysis)
monitoring/            # Prometheus deployment for metrics-based analysis
scripts/               # Numbered automation scripts (01–05 + open-dashboard)
```

## Scripts Convention

All scripts are in `scripts/` and numbered sequentially:
- `01-install-prerequisites.sh` — Installs minikube, kubectl, argo-rollouts plugin via Homebrew
- `02-start-cluster.sh` — Creates Minikube cluster
- `03-deploy-app.sh` — Builds images and deploys base app
- `04-demo-scenarios.sh` — Interactive walkthrough of all rollout strategies
- `05-teardown.sh` — Destroys cluster (has confirmation prompt)
- `open-dashboard.sh` — Opens Argo Rollouts dashboard

Scripts use `#!/usr/bin/env bash` and `set -euo pipefail`.

## Key Concepts

- **Rollout strategies** are in `rollouts/` — canary-basic, canary-with-analysis, blue-green, etc.
- **AnalysisTemplate** in `rollouts/analysis-template.yaml` queries Prometheus for success-rate metrics
- The app serves inline HTML with NBA scores data — the HTML is embedded in `app.py`
- Images are tagged `v1` (basic scores) and `v2` (+ live play-by-play)

## Conventions

- All Kubernetes resources use the `argo-rollouts-demo` namespace
- Scripts source no external files — each is self-contained
- Emoji prefixes in script output for readability (🏀, ✅, 🗑️)
- Docker images are built locally in Minikube's Docker daemon (no registry push)
