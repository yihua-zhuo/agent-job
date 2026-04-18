#!/home/node/.venv/cloakbrowser/bin/python3
"""
Video generation via LiteLLM proxy.
Submit a video job, poll for completion, return result.
"""

import argparse
import json
import time
import os
import requests
import sys


LITELLM_URL = os.environ.get("AI_GATEWAY_URL", "")
API_KEY = os.environ.get("AI_GATEWAY_KEY", "")

if not LITELLM_URL or not API_KEY:
    print("Error: AI_GATEWAY_URL and AI_GATEWAY_KEY must be set")
    sys.exit(1)


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
    print("⚠️ 请等待约10分钟后查询结果 | Please wait ~10 minutes before checking the result.")
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


def download_video(job_id: str, output_dir: str = "~/Downloads") -> str | None:
    """Download completed video content via /videos/{id}/content."""
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print(f"  Downloading video content...")
    resp = requests.get(
        f"{LITELLM_URL}/v1/videos/{job_id}/content",
        headers=headers(),
        timeout=60,
        stream=True,
    )
    if not resp.ok:
        print(f"  Download error: {resp.status_code} {resp.text[:200]}")
        return None

    # Determine filename from Content-Disposition or default
    content_disp = resp.headers.get("Content-Disposition", "")
    if "filename=" in content_disp:
        filename = content_disp.split("filename=")[1].strip('"')
    else:
        ext = resp.headers.get("Content-Type", "video/mp4").split("/")[-1]
        filename = f"video_{job_id[-12:]}.{ext}"

    filepath = os.path.join(output_dir, filename)
    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  Saved: {filepath} ({size_mb:.1f} MB)")
    return filepath


def poll_video(job_id: str, poll_interval: int = 5, timeout: int = 600, download: bool = True) -> dict | None:
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
            print(f"  Completed! Generate time: {output.get('generate_time_sec', '?')}s")
            if download:
                local_path = download_video(job_id)
                if local_path:
                    print(f"  Local file: {local_path}")
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
    parser.add_argument("--poll-only", "-p2", metavar="JOB_ID", help="Poll existing job ID (auto-downloads when complete)")
    parser.add_argument("--download", "-dl", action="store_true", help="Download video to --output-dir after completion")
    parser.add_argument("--output-dir", "-o", default="~/Downloads", help="Directory to save downloaded video")
    args = parser.parse_args()

    if args.list:
        models = list_models()
        print(f"Available models ({len(models)}):")
        for m in models:
            print(f"  {m}")
        return

    if args.poll_only:
        result = poll_video(args.poll_only, download=args.download)
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
        poll_video(job_id, download=True, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
