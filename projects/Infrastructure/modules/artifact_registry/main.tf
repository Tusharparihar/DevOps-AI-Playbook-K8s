resource "google_project_service" "artifact_registry" {
  project = var.gcp_project_id
  service = "artifactregistry.googleapis.com"
}

resource "google_artifact_registry_repository" "repos" {
  for_each = toset(var.repositories)

  project       = var.gcp_project_id
  location      = var.region
  repository_id = each.value
  format        = "DOCKER"
  description   = "Docker repository for ${each.value} service"

  depends_on = [google_project_service.artifact_registry]
}
