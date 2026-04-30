output "ecr_repository_url" {
  description = "The URL of the ECR repository"
  value       = aws_ecr_repository.todoflow.repository_url
}

output "docker_network_id" {
  description = "The ID of the local Docker network"
  value       = docker_network.todoflow_net.id
}
