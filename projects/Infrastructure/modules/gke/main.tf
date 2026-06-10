resource "google_project_service" "container" {
  project = var.gcp_project_id
  service = "container.googleapis.com"
}

resource "google_container_cluster" "gke" {
  name     = var.cluster_name
  location = var.zone

  network    = var.network_name
  subnetwork = var.subnetwork_name

  remove_default_node_pool = true
  initial_node_count       = 1

  release_channel {
    channel = "REGULAR"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "gke-pods"
    services_secondary_range_name = "gke-services"
  }

  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
  }

  deletion_protection = false

  depends_on = [google_project_service.container]
}

resource "google_container_node_pool" "primary" {
  name       = var.node_pool_name
  cluster    = google_container_cluster.gke.name
  location   = var.zone
  node_count = var.desired_size

  autoscaling {
    min_node_count = var.min_size
    max_node_count = var.max_size
  }

  node_config {
    machine_type = var.machine_type
    disk_size_gb = var.disk_size_gb
    disk_type    = var.disk_type
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    labels = {
      workload = "boutique"
    }

    tags = ["gke-node", "boutique"]
  }
}
