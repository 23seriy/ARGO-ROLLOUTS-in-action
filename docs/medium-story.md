# Argo Rollouts in Action: Progressive Delivery with Canary, Blue-Green, and Automated Analysis on Your Laptop

*Ship new versions of your NBA Scores API without waking up the on-call engineer.*

---

## The Problem: Deploying Is Scary

You've built a new feature. Tests pass. CI is green. You merge to main and `kubectl apply` — and now every single user is on the new version instantly.

If something goes wrong, you find out from a PagerDuty alert at 2 AM.

This is how most Kubernetes deployments work by default. A standard `Deployment` does a rolling update: it replaces pods one by one, and there's no built-in way to check if the new version is actually *healthy* before all traffic moves to it.

**Argo Rollouts** fixes this. It replaces the `Deployment` resource with a `Rollout` that supports:

- **Canary releases** — send 10% of traffic to the new version first, then 30%, then 60%, then 100%
- **Blue-green deployments** — run the full new version alongside the old and switch instantly
- **Automated analysis** — query Prometheus (or any metrics provider) to decide: promote or rollback

In this article, I'll show you how to set all of this up on your laptop with Minikube, using an NBA Live Scores API as the demo service. No cloud account needed.

---

## What We're Building

The demo has four components:

| Component | Role |
|---|---|
| **Scores API v1** | Returns basic NBA box scores (team, score, quarter) |
| **Scores API v2** | Same scores + live play-by-play data |
| **Traffic Generator** | Simulates game-night fan traffic |
| **Prometheus** | Collects metrics for automated analysis |

The idea: you're running a live scores service for NBA fans. Version 1 shows basic scores. Version 2 adds play-by-play — but you don't want to push it to all users at once. Argo Rollouts lets you gradually roll it out, monitor the metrics, and auto-rollback if something breaks.

```
Fan Request → Argo Rollouts → 90% to v1 (stable)
                             → 10% to v2 (canary)
                                    ↓
                              Prometheus checks success rate
                                    ↓
                              Pass → promote to 30%, 60%, 100%
                              Fail → auto-rollback to v1
```

---

## Prerequisites

- macOS with Homebrew
- Docker Desktop running
- ~6 GB RAM available

The setup scripts handle everything else.

---

## Step 1: Install Tools

```bash
git clone https://github.com/23seriy/argo-rollouts-in-action.git
cd argo-rollouts-in-action
chmod +x scripts/*.sh
./scripts/01-install-prerequisites.sh
```

This installs Minikube, kubectl, Helm, and the `kubectl-argo-rollouts` plugin.

---

## Step 2: Start the Cluster

```bash
./scripts/02-start-cluster.sh
```

This creates a Minikube cluster and installs the Argo Rollouts controller. The controller watches for `Rollout` resources (instead of `Deployments`) and manages the progressive delivery.

---

## Step 3: Deploy the Application

```bash
./scripts/03-deploy-app.sh
```

This builds the Docker images inside Minikube (no registry needed), deploys Prometheus, the Scores API as a Rollout starting at v1, and the traffic generator.

---

## Scenario 1: Basic Canary

The simplest progressive delivery. Instead of pushing v2 to everyone, we gradually increase traffic:

```yaml
strategy:
  canary:
    steps:
      - setWeight: 10
      - pause: {duration: 30s}
      - setWeight: 30
      - pause: {duration: 30s}
      - setWeight: 60
      - pause: {duration: 30s}
      - setWeight: 100
```

Think of it like opening arena gates. First let 10% of fans in. If nothing catches fire, open to 30%. Then 60%. Then everyone.

```bash
kubectl apply -f rollouts/canary-basic.yaml
```

Open the Argo Rollouts dashboard to watch it progress:

```bash
kubectl argo rollouts dashboard -n argo-rollouts-demo
# http://localhost:3100
```

The dashboard shows each step, the current weight, and the number of pods running each version. After about 2 minutes, v2 is fully promoted.

**Key insight:** At any point during the canary, if you notice problems, you can abort:

```bash
kubectl argo rollouts abort scores-api -n argo-rollouts-demo
```

Traffic instantly reverts to v1. No downtime.

---

## Scenario 2: Manual Canary

Sometimes you want a human in the loop. Replace the timed pauses with indefinite pauses:

```yaml
steps:
  - setWeight: 10
  - pause: {}        # waits for manual promotion
  - setWeight: 30
  - pause: {}
```

The rollout parks at 10% and waits. You test, check dashboards, talk to your team, then:

```bash
kubectl argo rollouts promote scores-api -n argo-rollouts-demo
```

This is like a coach reviewing each play before calling the next one. You control the pace.

---

## Scenario 3: Canary with Automated Analysis

This is where it gets powerful. Instead of a human watching Grafana, you define an `AnalysisTemplate` that queries Prometheus:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
spec:
  metrics:
    - name: success-rate
      interval: 20s
      count: 3
      failureLimit: 1
      successCondition: result[0] >= 0.95
      provider:
        prometheus:
          address: http://prometheus:9090
          query: |
            sum(rate(scores_api_requests_total{status="200"}[1m])) /
            sum(rate(scores_api_requests_total[1m]))
```

Translation: every 20 seconds, check if the success rate is ≥ 95%. Run 3 checks. If more than 1 fails, abort the rollout.

When you apply the canary-with-analysis manifest, Argo Rollouts runs an `AnalysisRun` alongside the canary steps. If the new version is healthy (ERROR_RATE=0), all checks pass and it auto-promotes through the steps.

```bash
kubectl apply -f rollouts/canary-with-analysis.yaml
kubectl get analysisrun -n argo-rollouts-demo -w
```

It's like the ref reviewing a play on the jumbotron — if the evidence looks good, the call stands.

---

## Scenario 4: Automated Rollback

Now the fun part. What happens when the new version is *bad*?

The `canary-with-analysis-fail.yaml` deploys v2 with `ERROR_RATE=0.4` — 40% of requests return HTTP 500.

```bash
kubectl apply -f rollouts/canary-with-analysis-fail.yaml
```

Watch what happens:

1. Canary starts at 10%
2. Analysis queries Prometheus
3. Success rate is ~60% (below the 95% threshold)
4. AnalysisRun fails
5. **Argo Rollouts automatically rolls back to v1**

No human intervention. No 2 AM pages. The bad version is pulled like a player with too many fouls — ejected from the game automatically.

---

## Scenario 5: Blue-Green Deployment

Canary is gradual. Blue-green is atomic.

```yaml
strategy:
  blueGreen:
    activeService: scores-api-stable
    previewService: scores-api-canary
    autoPromotionEnabled: false
```

Argo Rollouts deploys the full v2 alongside v1. The stable service still points to v1. The preview service points to v2 so you can test it:

```bash
kubectl port-forward svc/scores-api-canary 9081:8080 -n argo-rollouts-demo
# Open http://localhost:9081 — you should see v2
```

When you're ready, promote and all traffic switches instantly:

```bash
kubectl argo rollouts promote scores-api -n argo-rollouts-demo
```

It's like swapping your entire starting lineup between quarters. Everyone's on the new roster at once.

---

## How Is This Different from Istio?

If you've read my [Istio in Action](https://medium.com/@sergeiolshanetski/istio-in-action-a-hands-on-guide-to-service-mesh-on-your-laptop-e5ccac34262e) article, you might wonder: doesn't Istio do traffic splitting too?

Yes, but with a different scope:

| | Istio | Argo Rollouts |
|---|---|---|
| **Primary purpose** | Service mesh (mTLS, observability, policy) | Progressive delivery automation |
| **Traffic splitting** | Manual VirtualService configuration | Automated step-based progression |
| **Analysis** | Not built-in | Native AnalysisRun with Prometheus, etc. |
| **Auto-rollback** | Manual | Automatic based on metrics |
| **Blue-green** | Not native | First-class support |

In production, they work together: Istio handles the mesh networking, and Argo Rollouts uses Istio as a [traffic router](https://argoproj.github.io/argo-rollouts/features/traffic-management/istio/) for fine-grained canary control.

---

## Project Structure

```
argo-rollouts-in-action/
├── apps/
│   ├── scores-api/              # Flask API — v1 basic, v2 + play-by-play
│   └── traffic-generator/       # Simulates game-night traffic
├── k8s/                         # Namespace, services, base rollout
├── rollouts/                    # Strategy manifests + AnalysisTemplate
├── monitoring/                  # Prometheus deployment
└── scripts/                     # Automation (install → deploy → demo → teardown)
```

---

## Teardown

```bash
./scripts/05-teardown.sh
```

Everything cleaned up in one command.

---

## Key Takeaways

1. **Progressive delivery reduces blast radius.** A canary at 10% means 90% of your fans never see a bug.

2. **Automated analysis closes the loop.** Prometheus + AnalysisTemplate = no more staring at dashboards hoping nothing breaks.

3. **Blue-green for atomic switches.** When gradual isn't appropriate, swap everything at once with instant rollback.

4. **Rollbacks are instant.** Whether automated or manual, reverting takes seconds.

5. **It's additive, not invasive.** Argo Rollouts enhances standard Kubernetes. Your CI/CD, monitoring, and existing tooling work alongside it.

---

## What's Next?

Try these extensions on your own:

- **Add Istio as a traffic router** — combine Argo Rollouts with Istio VirtualServices for weighted routing
- **Add Slack notifications** — configure the Rollout to send a Slack message on promotion or rollback
- **Multi-metric analysis** — check both success rate AND latency in the AnalysisTemplate
- **Integration with ArgoCD** — GitOps-driven progressive delivery

The full source code is on GitHub: [github.com/23seriy/argo-rollouts-in-action](https://github.com/23seriy/argo-rollouts-in-action)

---

*If you found this useful, check out my other "in Action" articles:*
- [Istio in Action](https://medium.com/@sergeiolshanetski/istio-in-action-a-hands-on-guide-to-service-mesh-on-your-laptop-e5ccac34262e)
- [KEDA in Action](https://medium.com/@sergeiolshanetski/keda-in-action-building-event-driven-autoscaling-demos-with-kubernetes-redis-rabbitmq-and-an-06f7dd7bd70c)
