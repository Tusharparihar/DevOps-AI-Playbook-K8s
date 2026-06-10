output "network_name" {
  value = google_compute_network.vpc.name
}

output "subnetwork_name" {
  value = google_compute_subnetwork.subnet.name
}

output "pods_range_name" {
  value = google_compute_subnetwork.subnet.secondary_ip_range[0].range_name
}

output "services_range_name" {
  value = google_compute_subnetwork.subnet.secondary_ip_range[1].range_name
}
