#!/usr/bin/env python3
"""Sync VITE_API_BASE_URL in Vercel project environments."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib import error, parse, request


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _normalize_api_base_url(value: str) -> str:
    trimmed = value.strip().rstrip("/")
    if not trimmed:
        raise ValueError("Resolved backend URL is empty.")
    return trimmed if trimmed.endswith("/api") else f"{trimmed}/api"


def _resolve_api_base_url() -> str:
    explicit = os.getenv("BACKEND_BASE_URL", "").strip()
    if explicit:
        return _normalize_api_base_url(explicit)

    script_dir = Path(__file__).resolve().parent
    terraform_dir = Path(os.getenv("TERRAFORM_DIR", script_dir.parent / "terraform"))

    try:
        tf_value = _run(
            ["terraform", "output", "-raw", "recommended_frontend_api_base_url"],
            cwd=terraform_dir,
        )
        if tf_value and tf_value != "<sensitive>":
            return _normalize_api_base_url(tf_value)
    except Exception:
        pass

    aws_region = os.getenv("AWS_REGION", "us-east-1")
    apigw_name = os.getenv("AWS_APIGW_API_NAME", "bitebuddy-https-proxy")
    try:
        endpoint = _run(
            [
                "aws",
                "apigatewayv2",
                "get-apis",
                "--region",
                aws_region,
                "--query",
                f"Items[?Name=='{apigw_name}'].ApiEndpoint | [0]",
                "--output",
                "text",
            ]
        )
        if endpoint and endpoint != "None":
            return _normalize_api_base_url(endpoint)
    except Exception as exc:
        raise RuntimeError(
            "Unable to resolve backend URL from BACKEND_BASE_URL, terraform output, or AWS API Gateway."
        ) from exc

    raise RuntimeError(
        "Unable to resolve backend URL from BACKEND_BASE_URL, terraform output, or AWS API Gateway."
    )


def _vercel_request(
    token: str,
    method: str,
    url: str,
    body: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    req = request.Request(url=url, data=payload, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _upsert_vercel_env(
    token: str,
    project_id: str,
    team_id: str | None,
    key: str,
    value: str,
    env_type: str,
    target: str,
) -> None:
    payload = {
        "key": key,
        "value": value,
        "type": env_type,
        "target": [target],
    }
    attempts: list[tuple[str, str]] = []

    def _build_endpoint(include_team: bool) -> str:
        query = {"upsert": "true"}
        if include_team and team_id:
            query["teamId"] = team_id
        return f"https://api.vercel.com/v10/projects/{project_id}/env?{parse.urlencode(query)}"

    endpoints = [_build_endpoint(include_team=True)] if team_id else []
    endpoints.append(_build_endpoint(include_team=False))

    for endpoint in endpoints:
        try:
            _vercel_request(token=token, method="POST", url=endpoint, body=payload)
            return
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            attempts.append((endpoint, details))
        except Exception as exc:  # noqa: BLE001
            attempts.append((endpoint, str(exc)))

    joined = " | ".join([f"{url} -> {msg}" for url, msg in attempts])
    raise RuntimeError(f"Vercel API failed for target={target}. Attempts: {joined}")


def _trigger_deploy_hooks(urls: list[str]) -> None:
    for hook in urls:
        if not hook:
            continue
        req = request.Request(url=hook, method="POST")
        with request.urlopen(req, timeout=30):
            pass


def main() -> int:
    token = os.getenv("VERCEL_TOKEN", "").strip()
    project_id = os.getenv("VERCEL_PROJECT_ID", "").strip()
    team_id = os.getenv("VERCEL_TEAM_ID", "").strip() or None
    key = os.getenv("VERCEL_ENV_KEY", "VITE_API_BASE_URL").strip()
    env_type = os.getenv("VERCEL_ENV_TYPE", "encrypted").strip()
    targets_raw = os.getenv("VERCEL_TARGETS", "production,preview").strip()
    deploy_hooks_raw = os.getenv("VERCEL_DEPLOY_HOOK_URLS", "").strip()

    if not token or not project_id:
        print("Missing required VERCEL_TOKEN or VERCEL_PROJECT_ID.", file=sys.stderr)
        return 1

    targets = [part.strip() for part in targets_raw.split(",") if part.strip()]
    if not targets:
        print("No Vercel targets configured (VERCEL_TARGETS).", file=sys.stderr)
        return 1

    api_base_url = _resolve_api_base_url()
    print(f"Resolved API base URL: {api_base_url}")

    for target in targets:
        _upsert_vercel_env(
            token=token,
            project_id=project_id,
            team_id=team_id,
            key=key,
            value=api_base_url,
            env_type=env_type,
            target=target,
        )
        print(f"Updated {key} for target={target}")

    deploy_hooks = [part.strip() for part in deploy_hooks_raw.split(",") if part.strip()]
    if deploy_hooks:
        _trigger_deploy_hooks(deploy_hooks)
        print(f"Triggered {len(deploy_hooks)} deploy hook(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
