output "repository_urls" {
  value = {
    for repo_name, repo in google_artifact_registry_repository.repos :
    repo_name => "${repo.location}-docker.pkg.dev/${repo.project}/${repo.repository_id}"
  }
}
