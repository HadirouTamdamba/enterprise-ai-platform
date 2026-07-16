output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "database_endpoint" {
  value     = module.rds.db_instance_endpoint
  sensitive = true
}

output "ecr_repositories" {
  value = { for name, repo in aws_ecr_repository.images : name => repo.repository_url }
}

output "vpc_id" {
  value = module.vpc.vpc_id
}
