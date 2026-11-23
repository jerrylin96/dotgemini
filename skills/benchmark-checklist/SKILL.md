---
name: benchmark-checklist
description: "CRITICAL RULE: You MUST read and follow this skill whenever running a benchmark or reporting/comparing speedups, latency, throughput, profiling, or perf regressions for a changeset (does not fire on unrelated docs merely mentioning perf terms)."
---

# Benchmark Checklist

Apply whenever producing or evaluating a performance number for a changeset (PR before/after, regression claim, optimization loop, or library/config choice). Answer from run evidence, not code guesses.

* **Quick ballpark:** If user explicitly asks for a ballpark, 1 run suffices—still verify questions 4 and 7 and label it a single-run ballpark. Choosing between options is never a ballpark.
* **User-supplied measurements:** If user provides calibrated data with stated methodology (hardware, run count, limiter), verify limits, tuning, and reproducibility from their data instead of re-benchmarking.

## Before Running
- State the exact target claim in shippable words (e.g., `"export is 30% faster at p50 on 60k rows"`).
- Read the measurement script: verify what it times, counts, and ignores.
- Check host load (`uptime`, core count via `nproc` or `sysctl -n hw.ncpu`); if noisy, stop background load or interleave sides and disclose it.

## 7 Evidence Questions

| # | Question | Required Check |
|---|---|---|
| 1 | **Why not double?** | Profile in a separate unreported run (`top`/`pidstat`, `py-spy`/`perf`/`--cpu-prof`, I/O wait, `strace -c`); name the limiter and check load-generator saturation. |
| 2 | **Was it tuned?** | Run all sides with production settings (release flags, batching, pools, realistic warm/cold caches, same versions/data); tune untuned defaults before picking a winner. |
| 3 | **Did it break limits?** | Check arithmetic vs. disk/network bandwidth, core capacity, and Amdahl's law (removing a 10% piece yields at most ~11% total speedup). |
| 4 | **Did it error?** | Count failures, timeouts, and retries, and verify output correctness (rejections fail fast). |
| 5 | **Does it reproduce?** | Run at least 5 alternating iterations (`A, B, A, B, ...`); report median and range; gap smaller than variance is no measurable difference. |
| 6 | **Does it matter?** | Pair microbenchmarks with the end-to-end user path at realistic size/concurrency; report micro share of total time. |
| 7 | **Did it even happen?** | Verify timed region actually executed work (no uniterated generators, unawaited promises, or dead-code JIT elimination). |

## Report & Verdict
- Lead with verdict: **faster**, **slower**, **no measurable difference**, or **inconclusive**.
- State metric + unit, run count, median + range, and named limiter.
- Mark **inconclusive** (naming the gap) if claiming a difference without a named limiter, with an untuned side, or without checking questions 4 and 7.
