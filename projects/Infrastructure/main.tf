module "gcp_network" {
  source = "./modules/gcp_network"

  network_name    = var.network_name
  subnetwork_name = var.subnetwork_name
  subnetwork_cidr = var.subnetwork_cidr
  region          = var.region
}


module "gke" {
  source = "./modules/gke"

  gcp_project_id = var.gcp_project_id
  region         = var.region
  zone           = var.zone
  cluster_name   = var.cluster_name
  node_pool_name = var.node_pool_name

  machine_type   = var.machine_type
  min_size       = var.min_size
  desired_size   = var.desired_size
  max_size       = var.max_size
  disk_size_gb   = var.disk_size_gb
  disk_type      = var.disk_type

  network_name    = module.gcp_network.network_name
  subnetwork_name = module.gcp_network.subnetwork_name
  depends_on      = [module.gcp_network]
}

module "artifact_registry" {
  source = "./modules/artifact_registry"

  gcp_project_id = var.gcp_project_id
  region         = var.region
  repositories = var.repositories
}


data "google_client_config" "default" {}

provider "kubernetes" {
  alias                  = "gke"
  host                   = "https://${module.gke.cluster_endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
}

provider "helm" {
  alias = "gke"

  kubernetes {
    host                   = "https://${module.gke.cluster_endpoint}"
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
  }
}


module "monitoring" {
  source = "./modules/monitoring"

  providers = {
    kubernetes = kubernetes.gke
    helm       = helm.gke
  }

  depends_on = [module.gke]
}

