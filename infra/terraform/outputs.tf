output "instance_id" {
  value       = aws_instance.bitebuddy_backend.id
  description = "EC2 instance ID."
}

output "public_ip" {
  value       = aws_instance.bitebuddy_backend.public_ip
  description = "EC2 public IP."
}

output "public_dns" {
  value       = aws_instance.bitebuddy_backend.public_dns
  description = "EC2 public DNS."
}

output "backend_url" {
  value       = "http://${aws_instance.bitebuddy_backend.public_ip}:${var.backend_port}"
  description = "Backend API URL."
}
