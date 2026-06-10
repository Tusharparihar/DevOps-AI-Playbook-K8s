gcp_project_id = "project-d7cf163f-d55b-4c30-a72"
region         = "us-central1"
zone           = "us-central1-a"

network_name    = "boutique-vpc"
subnetwork_name = "boutique-subnet"
subnetwork_cidr = "10.10.0.0/20"

cluster_name   = "boutique-cluster"
node_pool_name = "boutique-node-pool"
machine_type   = "e2-standard-2"

desired_size = 3
min_size     = 2
max_size     = 4

disk_size_gb = 50
disk_type    = "pd-standard"

repositories = [
  "boutique-repo"
]