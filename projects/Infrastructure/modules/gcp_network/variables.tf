variable "network_name" {
  type        = string
  description = "VPC network name"
}

variable "subnetwork_name" {
  type        = string
  description = "Subnetwork name"
}

variable "subnetwork_cidr" {
  type        = string
  description = "Primary subnetwork CIDR"
}

variable "region" {
  type        = string
  description = "GCP region"
}

variable "pods_cidr" {
  type        = string
  description = "Secondary CIDR for GKE pods"
  default     = "10.20.0.0/16"
}

variable "services_cidr" {
  type        = string
  description = "Secondary CIDR for GKE services"
  default     = "10.30.0.0/20"
}
