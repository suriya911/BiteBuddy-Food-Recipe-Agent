variable "project_name" {
  type        = string
  description = "Project name prefix for resources."
  default     = "bitebuddy"
}

variable "aws_region" {
  type        = string
  description = "AWS region."
  default     = "us-east-1"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type."
  default     = "t2.micro"
}

variable "key_pair_name" {
  type        = string
  description = "Existing AWS EC2 key pair name."
}

variable "ssh_cidrs" {
  type        = list(string)
  description = "CIDR blocks allowed for SSH."
  default     = ["0.0.0.0/0"]
}

variable "root_volume_size_gb" {
  type        = number
  description = "Root EBS volume size in GB."
  default     = 20
}

variable "backend_port" {
  type        = number
  description = "Backend API exposed container port."
  default     = 8000
}

variable "backend_image" {
  type        = string
  description = "Docker image for backend."
}

variable "backend_env" {
  type        = map(string)
  description = "Environment variables passed to backend container."
  default     = {}
}
