#!/home/node/.venv/cloakbrowser/bin/python3
"""
Video generation via LiteLLM proxy.
Submit a video job, poll for completion, return result.
"""

import argparse
import json
import time
import requests
import sys


LITELLM_URL = "http://hedge-order-1443101935.ap-southeast-1.elb.amazonaws.com:4001"
API_KEY = "sk-cNuXYqrIDqo0pvFCUiUxHA"


def headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def list_models() -> list[str]:
    resp = requests.get(f"{LITELLM_URL}/v1/models", headers=headers(), timeout=10)
    if not resp.ok:
        print(f"Error listing models: {resp.status_code} {resp.text[:200]}")
        return []
    models = resp.json().get("data", [])
    return [m["id"] for m in models]


def submit_video(
    model: str,
    prompt: str,
    size: str = "768x512",
    duration: int = 3,
    num_inference_steps: int = 20,
    guidance_scale: float = 4.0,
    seed: int | None = None,
) -> str | None:
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "duration": duration,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
    }
    if seed is not None:
        payload["seed"] = seed

    print(f"Submitting: {model} | prompt={prompt[:60]}...")
    resp = requests.post(
        f"{LITELLM_URL}/v1/videos",
        json=payload,
        headers=headers(),
        timeout=30,
    )
    if not resp.ok:
        print(f"Error: {resp.status_code} {resp.text[:300]}")
        return None

    data = resp.json()
    job_id = data.get("id")
    print(f"Job ID: {job_id} | Status: {data.get('status')}")
    return job_id


def poll_video(job_id: str, poll_interval: int = 5, timeout: int = 300) -> dict | None:
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(
            f"{LITELLM_URL}/v1/videos/{job_id}",
            headers=headers(),
            timeout=15,
        )
        if not resp.ok:
            print(f"Error: {resp.status_code} {resp.text[:200]}")
            return None

        data = resp.json()
        status = data.get("status", "")
        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] {status}")

        if status == "completed":
            output = data.get("output") or {}
            print(f"  Completed! URL: {output.get('url', 'N/A')}")
            print(f"  Generate time: {output.get('generate_time_sec', '?')}s")
            return data
        elif status == "failed":
            print(f"FAILED: {data.get('error', {}).get('message', 'unknown')}")
            return data

        time.sleep(poll_interval)

    print("Timeout")
    return None


def main():
    parser = argparse.ArgumentParser(description="Generate video via LiteLLM proxy")
    parser.add_argument("--model", "-m", default="ltx2-19b-fast")
    parser.add_argument("--prompt", "-p", default="A cat sitting on a windowsill watching rain fall outside")
    parser.add_argument("--size", "-s", default="768x512")
    parser.add_argument("--duration", "-d", type=int, default=3)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--guidance", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--list", "-l", action="store_true", help="List available models and exit")
    parser.add_argument("--poll-only", "-p2", metavar="JOB_ID", help="Poll existing job ID")
    args = parser.parse_args()

    if args.list:
        models = list_models()
        print(f"Available models ({len(models)}):")
        for m in models:
            print(f"  {m}")
        return

    if args.poll_only:
        result = poll_video(args.poll_only)
        if result:
            print(json.dumps(result, indent=2))
        return

    job_id = submit_video(
        model=args.model,
        prompt=args.prompt,
        size=args.size,
        duration=args.duration,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        seed=args.seed,
    )
    if job_id:
        poll_video(job_id)


if __name__ == "__main__":
    main()
