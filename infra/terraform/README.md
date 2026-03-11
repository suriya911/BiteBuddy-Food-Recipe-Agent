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
- `api_gateway_cors_origins` -> your Vercel frontend URL(s)
- `backend_env.CORS_ORIGINS` -> your Vercel frontend URL
- optional: `backend_env.CORS_ORIGIN_REGEX` -> regex for Vercel preview URLs (`^https://.*\\.vercel\\.app$`)
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

Use `recommended_frontend_api_base_url` output in Vercel as `VITE_API_BASE_URL`.
This stack now creates:
- stable EC2 public endpoint (`backend_url`) backed by Elastic IP
- HTTPS API Gateway proxy endpoint (`https_backend_url`) for frontend use

## 4) Destroy when needed

```powershell
terraform destroy
```

## Vercel setup (one-time)

1. In Vercel project settings, set `VITE_API_BASE_URL` to `terraform output -raw recommended_frontend_api_base_url`.
2. Keep this variable the same for Production and Preview if you want both to use the same backend.
3. Redeploy frontend once after setting the variable.

After this, normal frontend rebuilds do not require changing the backend URL.

## Auto Sync To Vercel

This repo includes:
- script: `infra/scripts/sync_vercel_api_url.py`
- workflow: `.github/workflows/sync-vercel-api-url.yml`

The workflow runs every 30 minutes and on infra changes, resolves the current HTTPS backend endpoint, and upserts `VITE_API_BASE_URL` in Vercel.

Required GitHub secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `VERCEL_TOKEN`
- `VERCEL_PROJECT_ID`
- `VERCEL_TEAM_ID` (optional if not in a team)
- `VERCEL_DEPLOY_HOOK_URLS` (optional comma-separated deploy hooks)

## Notes

- This setup opens backend port `8000` publicly for simplicity. Limit `backend_cidrs` or use Nginx + TLS for production hardening.
- Terraform state is ignored by `.gitignore`.
