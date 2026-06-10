"""
tools.py — The 3 tools Kira (Gemini AI) can call to investigate your GKE cluster.

Each function talks to a real GCP/Kubernetes API:
  fetch_logs    → GCP Cloud Logging  (your pod logs)
  fetch_metrics → Prometheus         (CPU, memory, request rates)
  fetch_health  → Kubernetes API     (pod/node status)
"""

import os
import requests
from datetime import datetime, timezone, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1: fetch_logs
# Reads your pod logs from GCP Cloud Logging.
# GKE automatically ships all pod stdout/stderr to Cloud Logging — nothing
# to configure. Just needs GCP_PROJECT_ID in your .env.
# ─────────────────────────────────────────────────────────────────────────────

def fetch_logs(service_name: str = "", minutes: int = 60, severity: str = "ERROR") -> str:
    """
    Fetch recent application logs from GCP Cloud Logging.
    Returns last 30 log entries matching the filters.
    """
    try:
        from google.cloud import logging as gcp_logging

        project_id = os.environ.get("GCP_PROJECT_ID")
        if not project_id:
            return "Error: GCP_PROJECT_ID not set. Add it to your .env file."

        log_client = gcp_logging.Client(project=project_id)

        # Build the Cloud Logging filter
        time_ago = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        time_str = time_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

        filters = [
            'resource.type="k8s_container"',
            'resource.labels.namespace_name="boutique"',
            f'timestamp>="{time_str}"',
        ]

        if service_name:
            filters.append(f'resource.labels.container_name="{service_name}"')

        severity_upper = severity.upper()
        if severity_upper in ("ERROR", "CRITICAL", "ALERT", "EMERGENCY"):
            filters.append('severity>="ERROR"')
        elif severity_upper == "WARNING":
            filters.append('severity>="WARNING"')

        filter_str = " AND ".join(filters)

        entries = []
        for entry in log_client.list_entries(
            filter_=filter_str,
            max_results=30,
            order_by=gcp_logging.DESCENDING,
        ):
            service = "unknown"
            if entry.resource and entry.resource.labels:
                service = entry.resource.labels.get("container_name", "unknown")

            payload = ""
            if isinstance(entry.payload, dict):
                payload = str(entry.payload)
            elif entry.payload:
                payload = str(entry.payload)

            entries.append({
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else "unknown",
                "severity": str(entry.severity) if hasattr(entry, "severity") else "INFO",
                "service": service,
                "message": payload[:300],
            })

        if not entries:
            svc_label = service_name if service_name else "all services"
            return (
                f"No {severity} logs found in the last {minutes} minutes for {svc_label}. "
                f"The services may be healthy, or logs haven't been generated yet."
            )

        result = f"Found {len(entries)} log entries (last {minutes} min | severity>={severity} | namespace=boutique):\n\n"
        for e in entries:
            result += f"[{e['timestamp']}] [{e['service']}] {e['severity']}: {e['message']}\n"

        return result

    except ImportError:
        return "Error: google-cloud-logging not installed. Run: pip install google-cloud-logging"
    except Exception as e:
        return f"Error fetching logs: {type(e).__name__}: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2: fetch_metrics
# Queries Prometheus HTTP API for real-time metrics.
#
# IMPORTANT: Prometheus must be reachable. Two options:
#   Option A (easiest): Port-forward in a separate terminal:
#     kubectl port-forward svc/prometheus-kube-prometheus-prometheus \
#       -n monitoring 9090:9090
#   Option B: Expose as LoadBalancer and set PROMETHEUS_URL in .env.
#
# If Prometheus is not running, this returns a helpful error message.
# ─────────────────────────────────────────────────────────────────────────────

def fetch_metrics(query: str = "") -> str:
    """
    Fetch metrics from Prometheus running on GKE.
    If no query is provided, returns a health overview of all boutique services.
    """
    prometheus_url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

    def prom_query(q: str, label: str) -> str:
        try:
            resp = requests.get(
                f"{prometheus_url}/api/v1/query",
                params={"query": q},
                timeout=5,
            )
            data = resp.json()
            if data.get("status") != "success":
                return f"  {label}: query error — {data.get('error', 'unknown')}"

            results = data["data"]["result"]
            if not results:
                return f"  {label}: no data (metric may not exist yet)"

            lines = [f"  {label}:"]
            for item in results[:6]:
                metric_labels = item["metric"]
                value = float(item["value"][1])
                name = (
                    metric_labels.get("service")
                    or metric_labels.get("container")
                    or metric_labels.get("pod")
                    or str(metric_labels)
                )
                lines.append(f"    {name}: {value:.3f}")
            return "\n".join(lines)

        except requests.exceptions.ConnectionError:
            return (
                f"  {label}: Cannot connect to Prometheus at {prometheus_url}\n"
                f"  → Run this in a separate terminal:\n"
                f"    kubectl port-forward svc/prometheus-kube-prometheus-prometheus "
                f"-n monitoring 9090:9090"
            )
        except Exception as e:
            return f"  {label}: error — {str(e)}"

    if not query:
        # Default overview — runs 4 useful queries
        overview_queries = {
            "HTTP 5xx error rate (req/s)": (
                'sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)'
            ),
            "HTTP request rate (req/s)": (
                'sum(rate(http_requests_total[5m])) by (service)'
            ),
            "Memory usage (MB)": (
                'sum(container_memory_usage_bytes{namespace="boutique"}) by (container) / 1024 / 1024'
            ),
            "CPU usage (cores)": (
                'sum(rate(container_cpu_usage_seconds_total{namespace="boutique"}[5m])) by (container)'
            ),
        }

        sections = [f"Prometheus metrics (source: {prometheus_url}):\n"]
        for label, q in overview_queries.items():
            sections.append(prom_query(q, label))

        return "\n".join(sections)

    else:
        # Run the custom PromQL query directly
        try:
            resp = requests.get(
                f"{prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=5,
            )
            data = resp.json()
            if data.get("status") != "success":
                return f"Prometheus query failed: {data.get('error', 'unknown')}"

            results = data["data"]["result"]
            if not results:
                return f"No data for query: {query}"

            output = f"Query: {query}\nResults:\n"
            for item in results[:10]:
                output += f"  {item['metric']}: {item['value'][1]}\n"
            return output

        except requests.exceptions.ConnectionError:
            return (
                f"Cannot connect to Prometheus at {prometheus_url}.\n"
                "Run: kubectl port-forward svc/prometheus-kube-prometheus-prometheus "
                "-n monitoring 9090:9090"
            )
        except Exception as e:
            return f"Error fetching metrics: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3: fetch_health
# Uses the Kubernetes Python client to check pod and node health directly.
# This is the same data as `kubectl get pods -n boutique` but richer.
# ─────────────────────────────────────────────────────────────────────────────

def fetch_health() -> str:
    """
    Check real-time health of all pods and nodes in the GKE boutique namespace.
    Detects: OOMKilled, CrashLoopBackOff, pending pods, high restart counts.
    """
    try:
        from kubernetes import client as k8s_client, config as k8s_config

        # Try loading kubeconfig (works in WSL when kubectl is configured)
        try:
            k8s_config.load_kube_config()
        except Exception:
            try:
                k8s_config.load_incluster_config()
            except Exception as e:
                return (
                    f"Cannot load Kubernetes config: {str(e)}\n"
                    "Make sure kubectl is configured: "
                    "gcloud container clusters get-credentials YOUR_CLUSTER --zone YOUR_ZONE"
                )

        v1 = k8s_client.CoreV1Api()

        # ── Pods ──────────────────────────────────────────────────────────────
        pods = v1.list_namespaced_pod(namespace="boutique")

        pod_lines = []
        issues = []

        for pod in pods.items:
            pod_name = pod.metadata.name
            phase = pod.status.phase or "Unknown"
            total_restarts = 0
            container_states = []

            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    total_restarts += cs.restart_count
                    state_str = "running"
                    reason = ""

                    if cs.state.waiting:
                        state_str = "waiting"
                        reason = cs.state.waiting.reason or ""
                    elif cs.state.terminated:
                        state_str = "terminated"
                        reason = cs.state.terminated.reason or ""

                    suffix = f"({reason})" if reason else ""
                    container_states.append(f"{cs.name}:{state_str}{suffix}")

                    # Flag critical states
                    if reason in ("OOMKilled", "Error", "CrashLoopBackOff", "ImagePullBackOff"):
                        issues.append(
                            f"CRITICAL — {pod_name} [{cs.name}] is {reason}"
                        )

            restart_note = f"  ⚠ {total_restarts} restarts" if total_restarts >= 3 else ""
            if total_restarts >= 3:
                issues.append(f"WARNING — {pod_name} has restarted {total_restarts} times")

            pod_lines.append(
                f"  {pod_name:<45} {phase:<12} {', '.join(container_states)}{restart_note}"
            )

        # ── Nodes ─────────────────────────────────────────────────────────────
        nodes = v1.list_node()
        node_lines = []

        for node in nodes.items:
            node_name = node.metadata.name
            conditions = {c.type: c.status for c in (node.status.conditions or [])}
            ready = conditions.get("Ready", "Unknown")

            allocatable = node.status.allocatable or {}
            cpu = allocatable.get("cpu", "?")
            memory_ki = allocatable.get("memory", "0Ki").replace("Ki", "")
            try:
                memory_gb = f"{int(memory_ki) / 1024 / 1024:.1f}GB"
            except ValueError:
                memory_gb = allocatable.get("memory", "?")

            node_lines.append(
                f"  {node_name:<45} Ready={ready}  CPU={cpu}  Memory={memory_gb}"
            )

        # ── Build output ──────────────────────────────────────────────────────
        output = "═══ POD HEALTH  (namespace: boutique) ═══\n"
        output += "\n".join(pod_lines)

        output += "\n\n═══ NODE HEALTH ═══\n"
        output += "\n".join(node_lines)

        if issues:
            output += "\n\n═══ ISSUES DETECTED ═══\n"
            output += "\n".join(f"  ❌ {i}" for i in issues)
        else:
            output += "\n\n═══ No critical issues detected ✅ ═══"

        return output

    except ImportError:
        return "Error: kubernetes package not installed. Run: pip install kubernetes"
    except Exception as e:
        return f"Error checking cluster health: {type(e).__name__}: {str(e)}"
