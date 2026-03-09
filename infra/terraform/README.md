# Terraform + Docker (AWS Free Tier)

This deploys the backend to a single EC2 instance (`t2.micro`) and starts your Docker image automatically via EC2 user-data.

## Prerequisites

1. Terraform installed (`>= 1.6`)
2. AWS CLI configured (`aws configure`)
3. Existing EC2 key pair in your AWS account
4. Backend Docker image pushed to a registry (Docker Hub or GHCR)

## 1) Build and push backend image

From repo root:

```powershell
docker build -t your-user/bitebuddy-backend:latest backend
docker push your-user/bitebuddy-backend:latest
```

## 2) Prepare Terraform variables

```powershell
cd infra/terraform
copy terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
- `key_pair_name` -> your existing EC2 key pair
- `ssh_cidrs` -> your current public IP CIDR (`x.x.x.x/32`)
- `backend_image` -> image you pushed
- `backend_env.CORS_ORIGINS` -> your Vercel frontend URL
- Add any required API keys in `backend_env`

## 3) Provision infra

```powershell
terraform init
terraform plan
terraform apply
```

After apply:

```powershell
terraform output
```

Use `backend_url` output in Vercel as `VITE_API_BASE_URL` with `/api` suffix.

## 4) Destroy when needed

```powershell
terraform destroy
```

## Notes

- This setup opens backend port `8000` publicly for simplicity. Use Nginx + TLS later for production hardening.
- Terraform state is ignored by `.gitignore`.
