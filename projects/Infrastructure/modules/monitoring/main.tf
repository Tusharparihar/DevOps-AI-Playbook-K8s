resource "kubernetes_namespace_v1" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
    }
    helm = {
      source  = "hashicorp/helm"
    }
  }
}


resource "helm_release" "monitoring" {
  name       = "kube-prometheus-stack"
  namespace  = kubernetes_namespace_v1.monitoring.metadata[0].name

  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "56.21.0"

  timeout          = 600
  create_namespace = false

  values = [
    yamlencode({
      grafana = {
        service = {
          type = "ClusterIP"
        }
      }

      prometheus = {
        service = {
          type = "ClusterIP"
        }
      }

      alertmanager = {
        service = {
          type = "ClusterIP"
        }
      }
    })
  ]

  depends_on = [
    kubernetes_namespace_v1.monitoring
  ]
}
