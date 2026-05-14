# Argo Rollouts in Action: Progressive Delivery with Canary, Blue-Green, and Automated Analysis on Your Laptop

*Your CI is green. You hit deploy. Thirty seconds later, 100% of production traffic is on the new version — and the error rate just tripled. Sound familiar?*

---

It's a Tuesday night. The Lakers are playing the Celtics. Your NBA Live Scores API is handling thousands of requests per second. You ship a new version that adds play-by-play data. The rolling update replaces pods one by one — and within a minute, every user is on the new code.

Then the alerts start. The new serialization logic has a bug. Every third request returns a 500. By the time you roll back, thousands of fans have hit errors, and your SLA dashboard is red.

**The root cause isn't the bug. It's the deployment strategy.** A standard Kubernetes `Deployment` gives you one option: rolling update. All pods get replaced, and there's no gate between "new version is running" and "new version is handling all traffic."

What if only 10% of fans saw the new version first? What if Prometheus automatically caught the error spike and rolled back before you even woke up?

That's exactly what **Argo Rollouts** does.

---

## What Is Argo Rollouts?

Argo Rollouts is a Kubernetes controller that replaces the standard `Deployment` with a `Rollout` resource. It adds three capabilities that standard Kubernetes doesn't have:

1. **Canary releases** — shift traffic to the new version in configurable steps (10% → 30% → 60% → 100%), with pauses between each step
2. **Blue-green deployments** — run the full new version alongside the old, preview it, and switch traffic atomically
3. **Automated analysis** — query Prometheus, Datadog, CloudWatch, or any metrics provider at each step, and auto-promote or auto-rollback based on the results

It works alongside your existing Kubernetes stack — no service mesh required (though it integrates beautifully with Istio if you have one).

---

## What We're Building

We'll deploy an NBA Live Scores API on Minikube and use Argo Rollouts to progressively deliver a new version. The demo has four components:

| Component | What It Does |
|---|---|
| **Scores API v1** | Returns NBA box scores — team, score, quarter, arena |
| **Scores API v2** | Same scores **+ live play-by-play** (the new feature) |
| **Traffic Generator** | Sends continuous requests, simulating game-night fan traffic |
| **Prometheus** | Scrapes success-rate metrics for automated canary analysis |

Think of it as: you run a live scores platform. Version 1 shows the scoreboard. Version 2 adds a play-by-play feed. You want to roll out v2 during a Lakers-Celtics game — but carefully.

```
Fan Request ──► Argo Rollouts Controller
                    │
                    ├── 90% ──► Scores API v1 (stable)
                    │
                    └── 10% ──► Scores API v2 (canary)
                                       │
                                  Prometheus scrapes /metrics
                                       │
                                  AnalysisRun checks success rate
                                       │
                                  ✅ Pass → promote to 30%, 60%, 100%
                                  ❌ Fail → auto-rollback to v1
```

The entire project runs on your laptop. No cloud account needed.

---

## Getting Started

### Prerequisites

- **macOS** with Homebrew (adapt for Linux)
- **Docker Desktop** running
- ~6 GB RAM available for the Minikube cluster

### Clone and install

```bash
git clone https://github.com/23seriy/argo-rollouts-in-action.git
cd argo-rollouts-in-action
chmod +x scripts/*.sh
```

### Step 1 — Install tools

```bash
./scripts/01-install-prerequisites.sh
```

Installs Minikube, kubectl, Helm, and the `kubectl-argo-rollouts` plugin if they're not already present.

### Step 2 — Start the cluster

```bash
./scripts/02-start-cluster.sh
```

Creates a Minikube cluster (`argo-rollouts-demo` profile, 4 CPUs, 6 GB RAM) and deploys the Argo Rollouts controller. You should see:

```
✅ Argo Rollouts controller is running.
NAME                             READY   STATUS    RESTARTS   AGE
argo-rollouts-54595797c6-tdtcn   1/1     Running   0          70s
```

### Step 3 — Deploy the application

```bash
./scripts/03-deploy-app.sh
```

This builds three Docker images directly inside Minikube's Docker daemon (no registry push needed), deploys Prometheus, the Scores API as a Rollout starting at v1, and the traffic generator.

### Step 4 — Open the dashboards

In **three separate terminals**:

```bash
# Terminal 1: NBA Scores API
kubectl port-forward svc/scores-api-stable 9080:8080 -n argo-rollouts-demo

# Terminal 2: Argo Rollouts Dashboard
kubectl argo rollouts dashboard -n argo-rollouts-demo

# Terminal 3: Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n argo-rollouts-demo
```

Now open:
- **http://localhost:9080** — the NBA Scores API dashboard (v1, showing box scores)
- **http://localhost:3100** — the Argo Rollouts dashboard (shows rollout state and steps)
- **http://localhost:9090** — Prometheus (query the metrics that power analysis)

> 📸 *Screenshot opportunity: Take a screenshot of the Scores API dashboard showing the v1 version badge and the three NBA game scorecards.*

---

## Scenario 1: Basic Canary — Opening the Arena Gates

The simplest form of progressive delivery. Instead of replacing all pods at once, we shift traffic in steps:

```yaml
strategy:
  canary:
    steps:
      - setWeight: 10       # 10% of fans see v2
      - pause: {duration: 30s}
      - setWeight: 30       # 30%
      - pause: {duration: 30s}
      - setWeight: 60       # 60%
      - pause: {duration: 30s}
      - setWeight: 100      # everyone
```

Think of it like opening arena gates before a game. Let 10% of the crowd in first. If the concourse handles it fine, open wider. Then wider. Then let everyone in.

```bash
kubectl apply -f rollouts/canary-basic.yaml
```

Watch it progress in the Argo Rollouts dashboard at http://localhost:3100. You'll see each step light up as the canary advances. After about 2 minutes, v2 is fully promoted.

While the canary is running, open the Scores API at http://localhost:9080 and hit the **"20-Request Burst"** button. The version distribution bar will show the blue/green split matching the current canary weight.

> 📸 *Screenshot opportunity: The Argo Rollouts dashboard showing the canary at 30%, with 3 pods on v1 and 1 pod on v2.*

**The safety net:** At any point during the canary, if you spot trouble, you can abort instantly:

```bash
kubectl argo rollouts abort scores-api -n argo-rollouts-demo
```

All traffic reverts to v1. No downtime. No rollback deployment needed.

---

## Scenario 2: Manual Canary — The Coach Calls Every Play

Sometimes you want a human in the loop — especially for the first deploy of a major feature. Replace the timed pauses with indefinite ones:

```yaml
steps:
  - setWeight: 10
  - pause: {}        # ← waits forever until you promote
  - setWeight: 30
  - pause: {}
  - setWeight: 60
  - pause: {}
  - setWeight: 100
```

Apply the manifest:

```bash
kubectl apply -f rollouts/canary-manual.yaml
```

The rollout parks at 10% and waits. You can test, check dashboards, talk to your team, sleep on it — then advance when you're ready:

```bash
# Advance to the next step
kubectl argo rollouts promote scores-api -n argo-rollouts-demo
```

This is like a coach reviewing the film after every play before calling the next one. You control the pace entirely.

Try promoting a couple of steps, then abort to see the rollback:

```bash
kubectl argo rollouts abort scores-api -n argo-rollouts-demo
```

---

## Scenario 3: Canary with Automated Analysis — The Ref Reviews the Play

This is where Argo Rollouts gets genuinely powerful. Instead of a human watching Grafana during the rollout, you define an `AnalysisTemplate` that queries Prometheus automatically:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
spec:
  metrics:
    - name: success-rate
      interval: 20s        # check every 20 seconds
      count: 3             # run 3 total checks
      failureLimit: 1      # allow at most 1 failure
      successCondition: result[0] >= 0.95  # success rate must be ≥ 95%
      provider:
        prometheus:
          address: http://prometheus:9090
          query: |
            sum(rate(scores_api_requests_total{status="200"}[1m])) /
            sum(rate(scores_api_requests_total[1m]))
```

In plain English: every 20 seconds, check if ≥ 95% of requests are returning 200. Run 3 checks total. If more than 1 fails, abort the entire rollout.

The canary-with-analysis manifest wires this template into the rollout strategy:

```bash
kubectl apply -f rollouts/canary-with-analysis.yaml
```

Argo Rollouts creates an `AnalysisRun` alongside the canary. Watch it:

```bash
kubectl get analysisrun -n argo-rollouts-demo -w
```

With a healthy v2 (ERROR_RATE=0), all checks pass and the canary auto-promotes through each step without human intervention.

It's like the ref reviewing a challenged play on the jumbotron. The evidence looks good — the call on the court stands. Play on.

> 📸 *Screenshot opportunity: `kubectl argo rollouts get rollout scores-api -n argo-rollouts-demo` showing AnalysisRun status: ✔ Successful.*

---

## Scenario 4: Automated Rollback — The Player Gets Ejected

Now the most dramatic demo. What happens when the new version is *bad*?

The `canary-with-analysis-fail.yaml` deploys v2 with `ERROR_RATE=0.4` — meaning 40% of requests deliberately return HTTP 500.

```bash
kubectl apply -f rollouts/canary-with-analysis-fail.yaml
```

Here's what unfolds:

1. Canary starts at 10% — some traffic hits the broken v2
2. The traffic generator sends requests; Prometheus scrapes the metrics
3. AnalysisRun queries: *what's the success rate?* Answer: ~60%
4. 60% is below the 95% threshold — **analysis fails**
5. Argo Rollouts **automatically rolls back to v1**

No human intervention. No 2 AM PagerDuty. No scrambling to find the right SHA to revert to.

The bad version gets pulled like a player with too many flagrant fouls — ejected from the game automatically.

Watch it happen in real-time:

```bash
kubectl argo rollouts get rollout scores-api -n argo-rollouts-demo -w
```

You'll see the status change from `Progressing` → `Degraded` → traffic returns to v1.

> 📸 *Screenshot opportunity: The dashboard showing the rollback — v2 pods terminating, v1 pods back to full weight.*

---

## Scenario 5: Blue-Green Deployment — Swap the Starting Lineup

Canary is gradual. Blue-green is atomic.

Instead of shifting traffic in percentages, you deploy the *entire* new version alongside the old. Both run simultaneously. You test v2 through a preview service, and when you're satisfied, you flip all traffic at once.

```yaml
strategy:
  blueGreen:
    activeService: scores-api-stable    # current production traffic
    previewService: scores-api-canary   # test the new version here
    autoPromotionEnabled: false         # don't switch until I say so
    previewReplicaCount: 2
    scaleDownDelaySeconds: 30
```

```bash
kubectl apply -f rollouts/blue-green.yaml
```

Now you have two versions running simultaneously:

```bash
# v1 — stable (production traffic)
curl http://localhost:9080/scores | jq .version
# → "v1"

# v2 — preview (no production traffic yet)
kubectl port-forward svc/scores-api-canary 9081:8080 -n argo-rollouts-demo
curl http://localhost:9081/scores | jq .version
# → "v2"
```

Open http://localhost:9081 — you should see the v2 dashboard with **play-by-play data** visible on the game cards.

When you're confident, promote:

```bash
kubectl argo rollouts promote scores-api -n argo-rollouts-demo
```

All traffic switches to v2 instantly. It's like swapping your entire starting lineup between quarters. Everyone's on the new roster at once. And if something goes wrong, the old lineup is still on the bench — rollback is one command away.

---

## Scenario 6: Blue-Green Auto-Promote

Same as above, but the promotion happens automatically after a timeout:

```yaml
autoPromotionEnabled: true
autoPromotionSeconds: 60    # auto-switch after 60 seconds
```

```bash
kubectl apply -f rollouts/blue-green-auto.yaml
```

After 60 seconds, if the preview hasn't been manually aborted, traffic switches automatically. Like a timeout that runs out — play resumes with the new lineup whether the coach is ready or not.

---

## How Is This Different from Istio?

If you've read my [Istio in Action](https://medium.com/@sergeiolshanetski/istio-in-action-a-hands-on-guide-to-service-mesh-on-your-laptop-e5ccac34262e) article, you might wonder: doesn't Istio already do traffic splitting?

Yes — but they solve different problems:

| Capability | Istio | Argo Rollouts |
|---|---|---|
| **Primary purpose** | Service mesh (mTLS, observability, policy) | Progressive delivery automation |
| **Traffic splitting** | Manual VirtualService config — you set the weights | Automated step progression — the controller advances the weights |
| **Automated analysis** | Not built-in | Native AnalysisRun with Prometheus, Datadog, etc. |
| **Auto-rollback** | You detect the problem and revert manually | Automatic — metrics-driven, no human needed |
| **Blue-green** | Not a native concept | First-class strategy with preview services |
| **Scope** | L7 networking layer | Deployment orchestration layer |

In production, **they complement each other**. Istio provides the L7 traffic routing and mTLS, while Argo Rollouts uses Istio as a [traffic router plugin](https://argoproj.github.io/argo-rollouts/features/traffic-management/istio/) for precise canary weight control. Together, they give you: encrypted service-to-service traffic + automated progressive delivery with analysis.

---

## When Would You Use This in Production?

This isn't just a demo toy. Here are real patterns where Argo Rollouts delivers immediate value:

- **API services** — canary new API versions while monitoring error rates and p99 latency
- **Frontend deployments** — blue-green swap your Next.js app and preview it before switching DNS
- **ML model serving** — canary a new model version and analyze prediction accuracy before full promotion
- **Database migrations** — deploy the new app version that expects the new schema, but only send 10% of traffic while you monitor for query errors
- **Multi-region rollouts** — combine with ArgoCD ApplicationSets for region-by-region progressive delivery
- **Compliance-heavy environments** — manual canary with required human approval gates at each step

---

## Project Structure

```
argo-rollouts-in-action/
├── apps/
│   ├── scores-api/              # Flask API — v1 box scores, v2 + play-by-play
│   │   └── app.py               # Prometheus metrics + injectable ERROR_RATE
│   └── traffic-generator/       # Continuous load for analysis demos
├── k8s/                         # Namespace, services, base Rollout
├── rollouts/                    # 6 strategy manifests + AnalysisTemplate
│   ├── canary-basic.yaml
│   ├── canary-manual.yaml
│   ├── canary-with-analysis.yaml
│   ├── canary-with-analysis-fail.yaml
│   ├── blue-green.yaml
│   ├── blue-green-auto.yaml
│   └── analysis-template.yaml
├── monitoring/                  # Prometheus deployment + RBAC
└── scripts/                     # Install → deploy → demo → teardown
```

---

## Teardown

One command to clean everything up:

```bash
./scripts/05-teardown.sh
```

Removes the namespace, uninstalls Argo Rollouts, cleans up RBAC resources, and deletes the Minikube cluster.

---

## Key Takeaways

1. **Progressive delivery reduces blast radius.** A canary at 10% means 90% of your fans never see a bug. You find out about problems when they're affecting a sliver of traffic, not all of it.

2. **Automated analysis replaces hope-driven deployments.** Prometheus + AnalysisTemplate = the system decides whether to promote or rollback. You don't need a human staring at dashboards at midnight.

3. **Blue-green gives you atomic switchover with a safety net.** When gradual isn't appropriate (schema changes, breaking API updates), deploy the full new version and flip traffic in one shot — with instant rollback waiting in the wings.

4. **Rollbacks are instant, not panicked.** Whether automated (failed analysis) or manual (`kubectl argo rollouts abort`), reverting to the stable version takes seconds. No `git revert` → CI → deploy cycle.

5. **It layers on top of standard Kubernetes.** Argo Rollouts enhances Deployments — it doesn't replace your CI/CD pipeline, your monitoring stack, or your existing workflow. Adoption is incremental: swap one Deployment for a Rollout and see the difference immediately.

---

## What's Next?

If you want to extend this project:

- **Add Istio as a traffic router** — combine Argo Rollouts with Istio VirtualServices for L7 weighted routing (the most production-realistic setup)
- **Add Slack/PagerDuty notifications** — get alerted on promotion, rollback, or analysis failure via the Argo Rollouts notification engine
- **Multi-metric analysis** — check both success rate AND p99 latency in the AnalysisTemplate
- **Integrate with ArgoCD** — GitOps-driven progressive delivery where a `git push` triggers a canary rollout automatically

---

## Full Source Code

Everything in this article is on GitHub:

**[github.com/23seriy/argo-rollouts-in-action](https://github.com/23seriy/argo-rollouts-in-action)**

Clone it, run the scripts, break things, fix things. That's the fastest way to learn.

---

*This is the third article in my "in Action" series — hands-on Kubernetes projects you can run on your laptop:*

1. **[Istio in Action](https://medium.com/@sergeiolshanetski/istio-in-action-a-hands-on-guide-to-service-mesh-on-your-laptop-e5ccac34262e)** — Service mesh: traffic splitting, mTLS, fault injection, observability
2. **[KEDA in Action](https://medium.com/@sergeiolshanetski/keda-in-action-building-event-driven-autoscaling-demos-with-kubernetes-redis-rabbitmq-and-an-06f7dd7bd70c)** — Event-driven autoscaling: Redis queues, RabbitMQ, scale-to-zero
3. **Argo Rollouts in Action** *(this article)* — Progressive delivery: canary, blue-green, automated analysis

*Follow me for the next one.*
