# Projects Guide

This folder contains all implementation parts used in this repository.

## Folder Map

1. `boutique-microservices/`
   - Frontend + backend services + shared code + local Docker setup
2. `Infrastructure/`
   - Terraform for GCP (network, GKE, Artifact Registry, monitoring)
3. `aiops-gcp-assistant/`
   - Kira Streamlit assistant using Vertex AI + Cloud Logging + Prometheus + K8s API

## Recommended Execution Order

1. Local app run (optional)
2. GCP infrastructure provisioning with Terraform
3. Kubernetes deployment via Kustomize
4. Monitoring validation (Prometheus, Grafana)
5. AIOps assistant validation (Kira)

## 1) Local Run (Optional)

```bash
cd projects/boutique-microservices
docker-compose up -d
```

Stop:

```bash
docker-compose down
```

## 2) Provision Infrastructure (GCP)

```bash
cd projects/Infrastructure
terraform init
terraform plan
terraform apply
```

Then configure cluster access:

```bash
gcloud container clusters get-credentials boutique-cluster --zone us-central1-a --project <your-project-id>
```

## 3) Deploy Application

From repository root:

```bash
kubectl apply -k gitops/
```

Check app namespace:

```bash
kubectl get pods -n boutique
```

Once the PostgreSQL pod is running, restore the database:

```bash
kubectl apply -f gitops/k8s/database/restore-job.yml -n boutique
```

## 4) Monitoring Validation

1. Check `monitoring` namespace pods.
2. Check ServiceMonitor objects.
3. Confirm Prometheus targets are up.

## 5) Run Kira (AIOps Assistant)

```bash
cd projects/aiops-gcp-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
gcloud auth application-default login
streamlit run app.py
```

For metrics tool, keep Prometheus port-forward running:

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
```

## Notes for New Pullers

1. This repo uses GCP/GKE workflow (not AWS EKS).
2. Kira is Vertex-auth based (ADC), not Gemini API-key based.
3. Ensure your selected Gemini model is available in your project/region.
4. If image updates are not visible on frontend, rebuild and redeploy frontend image.
```

You should see SQL being executed across all 4 databases. `Completed` status means it ran successfully — this is expected and normal.

---

## Setting Up the CI/CD Pipeline

The GitHub Actions pipeline (`.github/workflows/ci.yml`) automatically builds Docker images and pushes them to GCP Artifact Registry on every push to `main`. It then updates the image tags in the k8s manifests. After the pipeline runs, re-apply manifests manually:

```bash
kubectl apply -k gitops/
```

### Pipeline jobs

```
push to main
     │
     ▼
build-and-push (7 parallel jobs)
  └── For each service: docker build → docker push to Artifact Registry
     │
     ▼
update-manifests
  └── Updates image tags in gitops/k8s/
  └── Commits back to main
```

### Step 1: Enable Workload Identity Federation for GitHub Actions

Follow Google's guide: [Workload Identity Federation for GitHub Actions](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)

### Step 2: Add secrets to GitHub

Go to your repository → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|-------------|-------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_REGION` | `us-central1` (or your region) |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Your Workload Identity Provider |
| `GCP_SERVICE_ACCOUNT` | Service account email for CI |

### Step 3: Trigger the pipeline

Push any change to `main`:

```bash
git add .
git commit -m "trigger CI"
git push origin main
```

### Step 4: Check pipeline status

1. Go to your repo → **Actions** tab
2. Click the latest **Boutique CI Pipeline** run
3. You'll see two jobs:
   - **build-and-push** — 7 parallel matrix jobs. Each builds and pushes one service image to Artifact Registry.
   - **update-manifests** — runs after all builds succeed. Replaces image tags in `gitops/k8s/` and commits back.

---

## Setting Up Observability

### Prometheus

Prometheus is installed by Terraform via `kube-prometheus-stack`. It scrapes metrics from the cluster and the boutique services.

#### How services expose metrics

Each backend service exposes a `/metrics` endpoint (Node.js `prom-client`). A `ServiceMonitor` resource tells Prometheus where to scrape:

```yaml
# gitops/k8s/backend/service-monitor.yml
spec:
  namespaceSelector:
    matchNames:
      - boutique
  selector:
    matchLabels:
      app: gateway
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
```

The `ServiceMonitor` has the label `release: kube-prometheus-stack` which is how the Prometheus Operator discovers it automatically.

#### Access Prometheus

```bash
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring &
```

Open http://localhost:9090

#### Useful PromQL queries to try

```promql
# Request rate per service
sum by (job) (rate(http_requests_total[5m]))

# 95th percentile response time
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# 5xx error rate per service
sum by (job) (rate(http_requests_total{status_code=~"5.."}[5m]))

# Pod CPU usage
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="boutique"}[5m]))

# Pod memory usage
sum by (pod) (container_memory_working_set_bytes{namespace="boutique"})

# Pod restart count
kube_pod_container_status_restarts_total{namespace="boutique"}

# Which services are up
up{job=~"gateway|auth|product-service|order-service|orders|user-service"}

# Node.js heap memory
nodejs_heap_size_used_bytes
```

Go to **Graph** tab to visualise any query over time.

---

### Grafana

Grafana is also installed by `kube-prometheus-stack`. It is pre-configured with Prometheus as a datasource and comes with a custom boutique dashboard automatically loaded.

#### How the dashboard is pre-loaded

The dashboard lives in `gitops/k8s/grafana-dashboard.yml` as a `ConfigMap`. It has the label:

```yaml
labels:
  grafana_dashboard: "1"
```

The `kube-prometheus-stack` Helm chart includes a **Grafana sidecar** that watches for ConfigMaps with this label across all namespaces. When it finds one, it automatically imports the JSON dashboard into Grafana — no manual import needed.

#### Access Grafana

```bash
kubectl port-forward svc/kube-prometheus-stack-grafana 8080:80 -n monitoring &
```

Open http://localhost:8080

Get the admin password:
```bash
kubectl get secret kube-prometheus-stack-grafana -n monitoring \
  -o jsonpath="{.data.admin-password}" | base64 --decode
```

- Username: `admin`

#### What's in the pre-loaded dashboard

The **Boutique Microservices** dashboard includes:

| Panel | What it shows |
|-------|--------------|
| Request Rate — $service | HTTP requests/sec broken down by status code |
| Response Time — $service | p95 and p99 latency |
| Active Requests | In-flight requests at any moment |
| Error Rate | 5xx rate as a percentage of total traffic |
| Request Rate by Service | All services on one graph |
| Node.js Heap Memory | Used vs total heap per service |
| Node.js Event Loop Lag | Latency in the JS event loop (indicator of CPU pressure) |
| Pod CPU Usage | CPU per pod in the boutique namespace |
| Pod Memory Usage | Memory per pod |
| Pod Restart Count | Surfaces crash-looping pods |
| Service Health | UP/DOWN status per service |
| HTTP Error Rate by Service | 4xx and 5xx breakdown per service |

The dashboard has a **Service** dropdown variable at the top — use it to filter all panels to a specific service.

---

---

## Port Forwarding Reference

Run all at once in the background:

```bash
kubectl port-forward svc/frontend 80:80 -n boutique &
kubectl port-forward svc/gateway 3001:3001 -n boutique &
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring &
kubectl port-forward svc/kube-prometheus-stack-grafana 8080:80 -n monitoring &
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:80 |
| Gateway / Metrics | http://localhost:3001/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:8080 |

---

## Credentials

### Grafana
```bash
kubectl get secret kube-prometheus-stack-grafana -n monitoring \
  -o jsonpath="{.data.admin-password}" | base64 --decode
```
Username: `admin`

---

## Cleanup

```bash
cd projects/Infrastructure
terraform destroy --auto-approve
```
