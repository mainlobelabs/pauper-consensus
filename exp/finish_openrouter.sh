#!/usr/bin/env bash
# Wait for the OpenRouter generation run AND for the local embedding server,
# then analyse that panel.
#
# E1 needs :1234 for retrieval embeddings. It deliberately does NOT fall back to
# an in-process embedding model: the local panel's alignment was measured
# through the LM Studio endpoint, and running the replication panel through a
# different embedding runtime would confound any panel difference with a change
# of measurement stack. Waiting is the correct behaviour; substituting is not.
#
# The pattern below is matched against process command lines. Because this is a
# script file its own cmdline is "bash exp/finish_openrouter.sh" and cannot
# match the pattern. (The same pgrep/pkill run from `bash -c` DOES self-match,
# which killed a shell twice in this project.)
set -u
cd /home/jmannings/dev/waveconv

echo "=== waiting for the OpenRouter run ==="
while pgrep -f "run_generate --backend openrouter" > /dev/null; do sleep 60; done
echo "openrouter generation exited at $(date)"

echo "=== waiting for the local embedding server on :1234 ==="
waited=0
until curl -s --max-time 10 http://localhost:1234/v1/models > /dev/null 2>&1; do
  sleep 30
  waited=$((waited + 30))
  if [ $((waited % 600)) -eq 0 ]; then
    echo "  still waiting for :1234 after ${waited}s (start LM Studio to proceed)"
  fi
done
echo ":1234 is up after ${waited}s"

echo "=== purging errored cache entries so they are retried, not frozen in ==="
grep -l '"error": "[^"]' out/cache/generation/*.json 2>/dev/null | xargs -r rm

echo "=== refill pass (cache hits + retries) ==="
.venv/bin/python -m exp.run_generate --backend openrouter 2>&1 | tail -10

echo "=== E0 (openrouter) ==="
OMP_NUM_THREADS=40 .venv/bin/python -m exp.e0 --backend openrouter 2>&1 | tail -30

echo "=== E1 (openrouter) ==="
OMP_NUM_THREADS=40 .venv/bin/python -m exp.e1 --backend openrouter 2>&1 \
  | grep -v "Loading weights" | tail -45

echo "=== result package ==="
OMP_NUM_THREADS=40 .venv/bin/python -m exp.package 2>&1 | tail -25

echo "=== OPENROUTER PANEL DONE at $(date) ==="
