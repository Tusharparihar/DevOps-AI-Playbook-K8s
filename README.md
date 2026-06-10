# DevOps AI Playbook

> End-to-end DevOps + AIOps project: microservices app deployed on GKE with Terraform, Kustomize, monitoring, and an AI SRE assistant.

---

## What This Project Does

1. Deploys a boutique e-commerce app (7 microservices + PostgreSQL) on Google Kubernetes Engine (GKE).
2. Provisions GCP infrastructure using Terraform (VPC, GKE cluster, Artifact Registry, monitoring).
3. Uses Kustomize for Kubernetes manifest management, deployed manually via `kubectl apply`.
4. Sets up Prometheus + Grafana for metrics and dashboards.
5. Includes **Kira**, an AI-powered SRE assistant that uses Vertex AI Gemini to diagnose live cluster issues.

---

## Architecture

```
Browser
  │
  ▼
nginx (frontend pod)
  ├── static files (React app + product images)
  └── /api/* → gateway:3001
                 ├── /api/auth/*     → auth:3002
                 ├── /api/products/* → product-service:3003
                 ├── /api/orders/*   → order-service:3004
                 └── /api/users/*    → user-service:3006

Monitoring: Prometheus (9090) ← Grafana
AIOps:      Kira (Streamlit) → Vertex AI Gemini + Cloud Logging + Prometheus + K8s API
```

---

## Kira in Action

Kira is the most visible AIOps part of this repo, so the screenshots are surfaced here first.

### Boutique App Running

![Boutique App](./projects/aiops-gcp-assistant/screenshots/app.jpg)

### Boutique App Running 2

![Boutique App Output 3](./projects/aiops-gcp-assistant/screenshots/app3.jpg)

### Kira Investigation Results

![Kira output 1](./projects/aiops-gcp-assistant/screenshots/1.jpg)

![Kira output 2](./projects/aiops-gcp-assistant/screenshots/2.jpg)

The first two screenshots show the Boutique App running, and the lower screenshots show Kira investigation results.

See the Kira project guide for setup details and the full screenshot gallery in [projects/aiops-gcp-assistant/README.md](projects/aiops-gcp-assistant/README.md).

---

## Repository Structure

```
devops-ai-playbook/
├── gitops/                           # Kubernetes manifests
│   ├── kustomization.yml             # Kustomize entry point
│   ├── namespace.yml / secrets.yml
│   └── k8s/
│       ├── backend/                  # Deployment + Service per backend service
│       ├── frontend/                 # Frontend Deployment (nginx) + Service
│       ├── database/                 # PostgreSQL StatefulSet + restore Job
│       └── grafana-dashboard.yml     # Pre-loaded Grafana dashboard
├── projects/
│   ├── boutique-microservices/       # Application source code
│   │   ├── frontend/                 # React app (served via nginx in prod)
│   │   ├── backend/services/         # Node.js microservices
│   │   └── database/                 # SQL schema + seed data
│   ├── Infrastructure/               # Terraform for GCP provisioning
│   └── aiops-gcp-assistant/          # Kira — AI SRE assistant (Streamlit + Vertex AI)
└── .github/workflows/                # CI pipeline
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Application | React, Node.js/TypeScript, PostgreSQL |
| Containers | Docker, Docker Compose |
| Orchestration | Kubernetes (GKE) |
| Infrastructure | Terraform (GCP) |
| Manifest Management | Kustomize |
| Monitoring | Prometheus + Grafana |
| Logging | GCP Cloud Logging (built into GKE) |
| AIOps | Vertex AI Gemini (Kira assistant) |
| Container Registry | GCP Artifact Registry |

---

## Quick Start

### 1. Provision Infrastructure
```bash
cd projects/Infrastructure
terraform init && terraform apply
```

### 2. Connect to Cluster
```bash
gcloud container clusters get-credentials boutique-cluster \
  --zone us-central1-a --project <YOUR_PROJECT_ID>
```

### 3. Deploy Application
```bash
kubectl apply -k gitops/
kubectl get pods -n boutique
# Wait for postgres pod, then restore DB:
kubectl apply -f gitops/k8s/database/restore-job.yml -n boutique
```

### 4. Run Kira (AIOps Assistant)
```bash
cd projects/aiops-gcp-assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
gcloud auth application-default login
streamlit run app.py
```

---

## Key Design Decisions

1. **Frontend uses nginx** — serves React static files and proxies `/api/*` to gateway inside the cluster. No API URL hardcoding needed.
2. **Kira uses Vertex AI** — authenticates via GCP ADC (no API key required). Calls Cloud Logging, Prometheus, and K8s API as investigation tools.
3. **ServiceMonitor** — Prometheus scrapes gateway metrics via ServiceMonitor CRD.
4. **Single entry point** — all backend traffic flows through gateway service.

---

## Learning Resources

- [`projects/README.md`](projects/README.md) — Deployment guide
- [`projects/aiops-gcp-assistant/README.md`](projects/aiops-gcp-assistant/README.md) — Kira setup and usage
- [`projects/Issues.md`](projects/Issues.md) — Known issues and fixes
