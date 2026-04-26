terraform {
  required_version = ">= 1.5"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "docker" {}

# AWS ECR repository
resource "aws_ecr_repository" "todoflow" {
  name                 = "todoflow"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project     = "TodoFlow"
    Environment = var.environment
  }
}

# ECR lifecycle policy: keep only last 10 images
resource "aws_ecr_lifecycle_policy" "todoflow" {
  repository = aws_ecr_repository.todoflow.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# Local Docker network for dev stack
resource "docker_network" "todoflow_net" {
  name   = "todoflow-net"
  driver = "bridge"
}

resource "docker_volume" "prometheus_data" {
  name = "todoflow-prometheus-data"
}

resource "docker_volume" "grafana_data" {
  name = "todoflow-grafana-data"
}
