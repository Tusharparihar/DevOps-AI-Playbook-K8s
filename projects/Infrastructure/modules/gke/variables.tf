variable "gcp_project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region"
}

variable "zone" {
  type        = string
  description = "GCP zone for zonal GKE cluster and node pool"
}

variable "cluster_name" {
  type        = string
  description = "GKE cluster name"
}

variable "node_pool_name" {
  type        = string
  description = "GKE node pool name"
}

variable "network_name" {
  type        = string
  description = "VPC network name"
}

variable "subnetwork_name" {
  type        = string
  description = "Subnetwork name"
}

variable "machine_type" {
  type        = string
  description = "GKE node machine type"
}

variable "desired_size" {
  type        = number
  description = "Desired node count"
}

variable "min_size" {
  type        = number
  description = "Minimum node count"
}

variable "max_size" {
  type        = number
  description = "Maximum node count"
}

variable "disk_size_gb" {
  type        = number
  description = "Node disk size in GB"
}

variable "disk_type" {
  type        = string
  description = "Node disk type (for example pd-standard)"
}
