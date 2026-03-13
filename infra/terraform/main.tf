terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "bitebuddy_backend_sg" {
  name        = "${var.project_name}-sg"
  description = "Security group for BiteBuddy backend"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_cidrs
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Backend API port (temporary/public)"
    from_port   = var.backend_port
    to_port     = var.backend_port
    protocol    = "tcp"
    cidr_blocks = var.backend_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-sg"
    Project = var.project_name
  }
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "bitebuddy_ssm_role" {
  name               = "${var.project_name}-ssm-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = {
    Name    = "${var.project_name}-ssm-role"
    Project = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "bitebuddy_ssm_core" {
  role       = aws_iam_role.bitebuddy_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "bitebuddy_ssm_profile" {
  name = "${var.project_name}-ssm-profile"
  role = aws_iam_role.bitebuddy_ssm_role.name

  tags = {
    Name    = "${var.project_name}-ssm-profile"
    Project = var.project_name
  }
}

locals {
  env_lines      = join("\n", [for k, v in var.backend_env : "${k}=${v}"])
  backend_host   = var.allocate_eip ? aws_eip.bitebuddy_backend[0].public_ip : aws_instance.bitebuddy_backend.public_ip
  backend_origin = "http://${local.backend_host}:${var.backend_port}"
  api_methods    = toset(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
}

resource "aws_instance" "bitebuddy_backend" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  key_name                    = var.key_pair_name
  iam_instance_profile        = aws_iam_instance_profile.bitebuddy_ssm_profile.name
  vpc_security_group_ids      = [aws_security_group.bitebuddy_backend_sg.id]
  associate_public_ip_address = true

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    app_image    = var.backend_image
    backend_port = var.backend_port
    env_lines    = local.env_lines
  })

  tags = {
    Name    = "${var.project_name}-ec2"
    Project = var.project_name
  }
}

resource "aws_eip" "bitebuddy_backend" {
  count  = var.allocate_eip ? 1 : 0
  domain = "vpc"

  tags = {
    Name    = "${var.project_name}-eip"
    Project = var.project_name
  }
}

resource "aws_eip_association" "bitebuddy_backend" {
  count         = var.allocate_eip ? 1 : 0
  instance_id   = aws_instance.bitebuddy_backend.id
  allocation_id = aws_eip.bitebuddy_backend[0].id
}

resource "aws_apigatewayv2_api" "bitebuddy_https_proxy" {
  count         = var.enable_https_tunnel ? 1 : 0
  name          = "${var.project_name}-https-proxy"
  protocol_type = "HTTP"

  cors_configuration {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_origins     = var.api_gateway_cors_origins
    max_age           = 600
  }
}

resource "aws_apigatewayv2_integration" "bitebuddy_proxy_path" {
  count                  = var.enable_https_tunnel ? 1 : 0
  api_id                 = aws_apigatewayv2_api.bitebuddy_https_proxy[0].id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  integration_uri        = local.backend_origin
  request_parameters     = { "overwrite:path" = "/$request.path.proxy" }
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_integration" "bitebuddy_proxy_root" {
  count                  = var.enable_https_tunnel ? 1 : 0
  api_id                 = aws_apigatewayv2_api.bitebuddy_https_proxy[0].id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  integration_uri        = local.backend_origin
  request_parameters     = { "overwrite:path" = "/" }
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_route" "bitebuddy_proxy_path" {
  for_each  = var.enable_https_tunnel ? local.api_methods : toset([])
  api_id    = aws_apigatewayv2_api.bitebuddy_https_proxy[0].id
  route_key = "${each.value} /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.bitebuddy_proxy_path[0].id}"
}

resource "aws_apigatewayv2_route" "bitebuddy_proxy_root" {
  for_each  = var.enable_https_tunnel ? toset(["GET", "HEAD"]) : toset([])
  api_id    = aws_apigatewayv2_api.bitebuddy_https_proxy[0].id
  route_key = "${each.value} /"
  target    = "integrations/${aws_apigatewayv2_integration.bitebuddy_proxy_root[0].id}"
}

resource "aws_apigatewayv2_stage" "bitebuddy_proxy_default" {
  count       = var.enable_https_tunnel ? 1 : 0
  api_id      = aws_apigatewayv2_api.bitebuddy_https_proxy[0].id
  name        = "$default"
  auto_deploy = true
}
