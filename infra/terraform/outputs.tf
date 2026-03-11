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
  value       = "http://${local.backend_host}:${var.backend_port}"
  description = "Backend base URL (append /api in frontend configuration)."
}

output "https_backend_url" {
  value       = var.enable_https_tunnel ? aws_apigatewayv2_stage.bitebuddy_proxy_default[0].invoke_url : null
  description = "HTTPS backend URL via API Gateway proxy."
}

output "recommended_frontend_api_base_url" {
  value = format(
    "%s/api",
    trimsuffix(
      var.enable_https_tunnel ? aws_apigatewayv2_stage.bitebuddy_proxy_default[0].invoke_url : "http://${local.backend_host}:${var.backend_port}",
      "/",
    ),
  )
  description = "Use this as VITE_API_BASE_URL in Vercel."
}
