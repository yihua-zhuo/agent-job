# Video Generator — Tips & Lessons Learned

## Queue & Timing

- **Video generation takes ~10 minutes per job.** Do NOT expect completion in <5 min.
- Server-side queue can hold ~20 pending jobs. Overflow = all new jobs queue indefinitely.
- If job stays `queued` for >15 min, the server queue is backed up — wait and re-poll.
- Use spend logs (`/spend/logs`) to check if jobs are being processed even when status polls show `queued` — the API logs real activity.
- **Never submit many jobs in rapid succession.** Space them out (30s+ intervals) to avoid queue overflow.

## Job ID Format

- LiteLLM job IDs are base64-encoded and long. Copy the full ID from the API response.
- The `request_id` in spend logs matches the job ID.

## Spend / Billing

- Each `avideo_generation` log entry = one job submitted (not one completed).
- Spend per job: ~$0.15–$0.25 for `ltx2-19b-fast` (3–5s clips).
- `avideo_status` calls are free.
- Total team spend visible at `/user/info` → `spend` field.

## Submission Tips

- For long prompts (>200 chars), curl is more reliable than the Python script (fewer dependency issues).
- Always set `num_inference_steps` ≥ 20 and `guidance_scale` ≥ 4.0 for quality output.
- `duration` = seconds of video (3–5s typical for ltx2-19b-fast).

## ⚠️ After Submitting

**Always tell the user: "请等待10分钟后查询结果"** — video generation takes ~10 min. Do NOT poll within the first few minutes or tell the user to check soon. Set expectation upfront.

## Skills Reference

- Diver prompt examples: [diver-examples.md](references/diver-examples.md)
- Submit script: [scripts/submit_video.py](scripts/submit_video.py)
