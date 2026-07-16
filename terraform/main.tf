# Enterprise AI Platform — AWS reference infrastructure
# Cloud-agnostic layout: swap the module sources for Azure/GCP equivalents;
# the Kubernetes manifests in ../kubernetes are cloud-independent.

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
  backend "s3" {
    # Configure via `terraform init -backend-config=backend.hcl`
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "enterprise-ai-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "eap-${var.environment}"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "production"
  enable_dns_hostnames = true
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.14"

  cluster_name    = "eap-${var.environment}"
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    general = {
      instance_types = var.node_instance_types
      min_size       = var.environment == "production" ? 3 : 1
      max_size       = 10
      desired_size   = var.environment == "production" ? 3 : 2
    }
  }

  enable_cluster_creator_admin_permissions = true
}

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.7"

  identifier = "eap-${var.environment}"

  engine               = "postgres"
  engine_version       = "16.3"
  family               = "postgres16"
  major_engine_version = "16"
  instance_class       = var.db_instance_class

  allocated_storage     = 50
  max_allocated_storage = 500
  storage_encrypted     = true

  db_name  = "eap"
  username = "eap"
  port     = 5432
  manage_master_user_password = true

  multi_az               = var.environment == "production"
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.db.id]

  backup_retention_period = var.environment == "production" ? 14 : 3
  deletion_protection     = var.environment == "production"
}

resource "aws_security_group" "db" {
  name_prefix = "eap-db-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_ecr_repository" "images" {
  for_each = toset(["eap-backend", "eap-worker", "eap-frontend"])
  name     = each.key

  image_scanning_configuration {
    scan_on_push = true
  }
}
