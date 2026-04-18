---
name: video-generator
description: Generate videos via LiteLLM proxy API. Use when user wants to create/generate/make a video using a text-to-video model, or asks to generate a video with specific model or parameters. Supports model selection, custom prompts, resolution, duration, steps, guidance scale, and seed. Also use to list available video models, check job status, or poll a video job ID.
---

# Video Generator

Submit text-to-video generation jobs via the LiteLLM proxy at `http://hedge-order-1443101935.ap-southeast-1.elb.amazonaws.com:4001`.

## Quick Start

```bash
# List available models
python3 ~/.openclaw/workspace/skills/video-generator/scripts/submit_video.py --list

# Generate a video
python3 ~/.openclaw/workspace/skills/video-generator/scripts/submit_video.py \
  --model ltx2-19b-fast \
  --prompt "A cat sitting on a windowsill watching rain fall outside" \
  --size 768x512 \
  --duration 3

# Poll existing job
python3 ~/.openclaw/workspace/skills/video-generator/scripts/submit_video.py --poll-only JOB_ID
```

## Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--model` / `-m` | `ltx2-19b-fast` | Model name (use `--list` to see all) |
| `--prompt` / `-p` | — | Text prompt (required) |
| `--size` / `-s` | `768x512` | Resolution, e.g. `768x512`, `1280x720` |
| `--duration` / `-d` | `3` | Video duration in seconds |
| `--steps` | `20` | Inference steps |
| `--guidance` | `4.0` | Guidance scale |
| `--seed` | random | Fixed seed for reproducibility |
| `--list` / `-l` | — | List available models and exit |
| `--poll-only` / `-p2` | — | Poll an existing job ID |

## Workflow

1. **List models** to find the right model for the task
2. **Submit job** with prompt + parameters — returns a `job_id`
3. **Poll** the job every 5 seconds until `completed` or `failed`
4. **Output URL** is returned in the `output.url` field

## Prompt Examples

See [diver-examples.md](references/diver-examples.md) for detailed dive scene prompts with camera movement, lighting, and marine life descriptions. Use these as templates for high-quality video prompts.
