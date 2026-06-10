variable "region" {
  description = "GCP region to deploy resources in"
  type = string
}

variable "zone" {
  description = "Default GCP zone used by provider and zonal operations"
  type = string
}

variable "gcp_project_id" {
  description = "GCP project ID where resources are created"
  type = string
}

variable "network_name" {
  description = "VPC network name"
  type = string
}

variable "subnetwork_name" {
  description = "Subnetwork name for GKE nodes"
  type = string
}

variable "subnetwork_cidr" {
  description = "CIDR range for the GKE subnetwork"
  type = string
}

variable "cluster_name" {
  description = "The name of the GKE cluster"
  type = string
}

variable "node_pool_name" {
  type        = string
  description = "GKE node pool name"
}

variable "machine_type" {
  type        = string
  description = "Machine type for GKE worker nodes (for example e2-standard-2)"
}

variable "desired_size" {
  type        = number
  description = "Desired number of worker nodes"
}

variable "min_size" {
  type        = number
  description = "Minimum number of  worker nodes"
}

variable "max_size" {
  type        = number
  description = "Maximum number of worker nodes"
}

variable "disk_size_gb" {
  type        = number
  description = "Disk size in GB for each GKE node"
}

variable "disk_type" {
  type        = string
  description = "Disk type for GKE nodes (for example pd-standard)"
}

variable "repositories" {
  type = list(string)
}