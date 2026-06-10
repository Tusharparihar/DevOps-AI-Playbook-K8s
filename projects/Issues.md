# Issues Faced During Implementation

## Infrastructure

### 1. Node Pool Pod Capacity

- **Problem**: When replica counts were increased with monitoring running, pods became unschedulable.
- **Root Cause**: The GKE node pool machine type had limited pod capacity. With boutique services + monitoring, the cluster ran out of allocatable pod slots.
- **Solution**: Use a machine type with higher pod capacity (e.g. `e2-standard-4`) or add more nodes to the pool.

---

## Database Issue

### 1. StatefulSet Init Script Failure

- **Problem**: Even though the StatefulSet was attached with an init script which had a DB dump in it, it was still failing to initialize. It was skipping the DB initializing resulting in "products page not found".

- **Root Cause**: The persistent volume had a `lost+found` directory, so Postgres considered the volume non-empty and skipped initialization — resulting in missing databases.

- **Solution**: Created a DB-restore Job to load the DB after PostgreSQL is ready.
- **Steps to Fix**:
  1. Wait for the PostgreSQL pod to be up and running
  2. Apply the DB-restore Job: `kubectl apply -f gitops/k8s/database/restore-job.yml -n boutique`
  3. If the Job fails initially, delete it and reapply after PostgreSQL is ready

---

## Frontend

### 1. Product Images Not Loading

- **Problem**: Product images showed broken image icons on the deployed site.
- **Root Cause**: The React app was calling `http://localhost:3001/api` from the browser, which doesn't work when the app is deployed on GKE.
- **Solution**: Switched frontend to nginx with a reverse proxy config. Nginx serves static files and proxies `/api/*` to the gateway service inside the cluster. API URL is now relative (`/api`), no hardcoded localhost.

---

## Monitoring

### 1. Boutique Application Metrics Not Found

- **Problem**: Cluster and node metrics worked, but boutique application metrics were missing in Grafana.
- **Root Cause**: The ServiceMonitor was not properly configured to scrape the application services.
- **Solution**: Added a ServiceMonitor targeting the gateway service with the correct label `release: kube-prometheus-stack` so the Prometheus Operator discovers it automatically.

