#!/usr/bin/env bash
# Wait for the generation run to finish, then run the whole analysis chain.
#
# Step 1 re-runs the generator. That is almost entirely cache hits; its job is
# to refill the handful of generations lost to server contention, which are no
# longer cached as errors (GOTCHAS.md), so they are retried rather than frozen
# in as failures.
set -u
cd /home/jmannings/dev/waveconv

echo "=== waiting for generation to finish ==="
while pgrep -f "exp.run_generate" > /dev/null; do sleep 60; done
echo "generation process exited at $(date)"

echo "=== purging any errored cache entries ==="
grep -l '"error": "[^"]' out/cache/generation/*.json 2>/dev/null | xargs -r rm
echo "cached generations: $(ls out/cache/generation | wc -l)"

echo "=== step 1: refill gaps (cache hits + retries) ==="
.venv/bin/python -m exp.run_generate 2>&1 | tail -20

echo "=== step 2: E0 ==="
OMP_NUM_THREADS=48 .venv/bin/python -m exp.e0 2>&1 | tail -40

echo "=== step 3: E1 (NLI on CPU; the long pole) ==="
OMP_NUM_THREADS=48 .venv/bin/python -m exp.e1 2>&1 | tail -80

echo "=== step 4: M0 artifacts ==="
.venv/bin/python m0/ceiling.py > out/m0_ceiling.txt 2>&1
.venv/bin/python -m m0.simulate > out/m0_simulate.txt 2>&1
tail -3 out/m0_ceiling.txt; tail -3 out/m0_simulate.txt

echo "=== step 5: result package ==="
OMP_NUM_THREADS=48 .venv/bin/python -m exp.package 2>&1 | tail -40

echo "=== ALL DONE at $(date) ==="
