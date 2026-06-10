variable "gcp_project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "Region for Artifact Registry repositories"
}

variable "repositories" {
  type        = list(string)
  description = "List of Artifact Registry repository names"
}
