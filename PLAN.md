# Plan: Slice 3 — five-family availability, measured

Run `20260830-134531-f0f0d997`, workstream `20260828-181135-0d060fc4` slice 3 of 4.
Request: `REQUEST.md`. Master: `MASTER_v3.md` §"Slice 3".

**Revision 2** (round-1 plan-QA closure; non-normative note — the live spec is `## Approach`
and the `## Tasks` fence). B1 removed the retries that contradicted one-probe-per-endpoint.
B2 made the runner a single command with a cheap default and a `--probe` mode. B3 gave
identity mismatch a defined status that cannot inflate the margin. B4 encoded the
single-model-slot constraint with an overlap test. B5 added negative integration tests for
every gate assertion. B6 made the paid spend calculated, not merely counted. A1 added
artifact provenance and freshness. A2 added error sanitisation.

## Approach

Slice 4 needs to know what can actually be registered. The five-family target has failed
twice on availability, so this slice measures rather than assumes, and records the MARGIN,
because the human decision of 2026-08-30 makes margin the deciding quantity: M=5 is
registrable only if MORE than five families answer.

**A real generation, never a catalogue lookup.** `prereg_v2.yaml` records the exact trap:
the `:1234` catalogue lists `qwen3.8-27b` and 400s on completion. Any check that asks "is
this model listed" reports it available when it is not. Each candidate therefore gets one
attempted generation that must return usable content, reusing the frozen
`exp/smoke_v2.py`'s throwaway theory — imported, not copied, so the probe shape stays the
one the v2 freeze evidence used.

**Identity decides the status, and the status decides the count** (B3). A model that answers
under a different id is a substitution, which `prereg_v2`'s resolution rule forbids. The
artifact therefore carries a three-valued status, not ok/fail: `ok` (answered AND the echoed
id matches the registration's expected value), `substituted` (answered under an unexpected
id), `fail` (no usable content). Only `ok` counts toward the pinned-family margin —
`substituted` must never inflate it, since the whole question is whether the REGISTERED
models are available. Substituted entries are reported separately as possible families for a
NEW registration, which slice 4 adjudicates. qwen's known case — served on `:8083` under the
stale alias `ornith35`, where that alias IS the registered expected echo — is the worked
example of an `ok` whose requested and echoed ids differ legitimately.

**Families, not model ids.** `GOTCHAS.md` records the cycle-1 error directly: two ornith
variants were nearly counted as two independent sources. Each candidate carries an explicit
family attribution, and the count is over distinct families.

**Probing is separated from gating.** The probe spends money (Hoonify is paid) and touches
external services, so it runs ONCE behind an explicit flag and writes an artifact; the gate
validates that artifact and re-probes only when asked. A gate that re-probed on every run
would spend on every re-run and make the slice's cost unbounded.

**The verdict follows the recorded rule, not the operator's read of the number.** OQ1 fixes
it in advance: >5 families answering means M=5 is registrable; exactly 5 means M=3/M=4
primary with the fifth as a declared stretch arm; <5 means neither and slice 4 is told what
exists. The verdict script applies that rule mechanically so the number cannot be
interpreted generously after the fact.

## Risks

- **Spending on every gate run.** Mitigated by the probe/gate split above; the gate asserts
  the artifact exists and is well-formed, and never calls an endpoint.
- **A transient failure recorded as unavailability.** A single probe cannot distinguish a
  dead model from a flaky minute. This is ACCEPTED rather than mitigated by retrying: the
  request permits one attempt per endpoint, and retrying would change the measured protocol
  and multiply paid calls. The artifact instead records the single attempt with its
  sanitised error and latency, so a human can judge whether a re-probe is warranted and run
  one deliberately. A `fail` in the artifact therefore means "did not answer on one
  attempt at this timestamp", and the verdict wording must not overstate it as "unavailable".
- **Reporting a listed-but-broken model as available.** The whole reason E1 requires a
  generation; a test asserts the checker rejects a catalogue-only success.
- **Leaking experimental content.** The probe is a throwaway theory, not a corpus item; the
  gate asserts no corpus text appears in the artifact.
- **Cost surprise.** One attempt per endpoint, no retries, the paid endpoint identified, and
  the spend CALCULATED (B6) from recorded input/output token counts and the rates pinned in
  `prereg_v2.yaml` ($1.40/$4.40 per 1M), emitted as USD with a conservative upper bound where
  usage is not reported. The gate asserts the paid call count never exceeds one per candidate.
- **A stale artifact passing as today's measurement** (A1). The artifact carries a schema
  version, UTC timestamp, source commit and a digest of `prereg_v2.yaml`; the gate rejects an
  artifact whose registration digest differs from the current file, and reports its age so an
  old-but-well-formed file cannot silently serve as evidence of availability measured now.
- **Credentials in a tracked artifact** (A2). Provider error text is normalised before
  persistence: status and message retained, authorization headers, query credentials and
  provider request metadata redacted. A test plants a fake bearer token in an error and
  asserts it does not reach the artifact.

## Rollback

`git revert` the slice commit. The diff comprises four new code files
(`exp3/availability.py`, `exp3/slice3_verdict.py`, `exp3/slice3_decide.py`,
`run_slice3.sh`) and edits to two existing ones (`exp3/decide.py`,
`exp3/slice2_decide.py`, which gain the atomic-write helper), three
new test files (`tests/test_availability.py`, `tests/test_slice3_verdict.py`,
`tests/test_slice3_gate.py`), two new
artifacts (`out/slice3/availability.json`, `out/slice3/verdict.json`), and edits to
`REQUEST.md`, `PLAN.md` and `DECISIONS.md`. No paper text, no artifact under `out/v3/`, no
generation-cache entry and no tag is touched; `git diff prereg-v2-2026-08-16 HEAD -- exp/
wct/ m0/` is empty before and after, and `out/v3/` stays identical to `e63f946`.

## Tasks

```json
[
  {
    "id": "A1-probe",
    "title": "exp3/availability.py: one real generation per candidate, identity and family recorded",
    "depends_on": [],
    "files": [
      "exp3/availability.py",
      "tests/test_availability.py"
    ],
    "acceptance": [
      "ENVIRONMENT: run everything with /home/jmannings/dev/waveconv/.venv/bin/python (3.12). Bare `python` is system 3.14 without the project deps and fails at `import httpx`. No PyPI egress: never pip install, never create a venv.",
      "probes the six pinned candidates read FROM prereg_v2.yaml, AND (under --include-paid, per the 2026-08-30 human instruction) their paid-tier twins, resolved through the harness binding harness.toml [providers.deepseek_paid] kind=openrouter_paid. Twins are recorded with tier=paid and pinned_free_id; they are counted in families_reachable but never in the pinned total. Paid rates cover Hoonify (from prereg_v2.yaml) AND the four OpenRouter twins (read live from the catalogue, with a pinned fallback), and spend prefers the provider's reported usage.cost",
      "each probe is an attempted GENERATION returning usable content; a model-list or health response is NOT success, and a test asserts a catalogue-only result is rejected",
      "EXACTLY ONE attempt per endpoint, no automatic retry (B1): a retry would change the measured protocol and multiply paid calls. A re-probe is a deliberate second invocation whose artifact supersedes the first",
      "LOCAL probes run strictly sequentially with no thread pool and no overlapping requests (B4, GOTCHAS single-model-slot): a mocked transport records call windows and a test FAILS if two local calls overlap",
      "THREE-VALUED status (B3): `ok` = answered and the echoed id matches the registration's expected value; `substituted` = answered under an unexpected id; `fail` = no usable content. The schema is documented in the module docstring",
      "records per candidate: family, backend, id requested, id echoed, expected echo from the registration, resolved weights where local, status, sanitised error, latency, and token usage",
      "SANITISES error text before persistence (A2): status and message retained; authorization headers, query credentials and provider request metadata redacted. A test plants a fake bearer token in an error and asserts it never reaches the artifact",
      "CALCULATES paid spend (B6) from recorded input/output tokens and the rates pinned in prereg_v2.yaml, emitting USD plus a conservative upper bound where usage is unreported",
      "artifact carries PROVENANCE (A1): schema version, UTC timestamp, source commit, and a sha256 digest of prereg_v2.yaml",
      "reuses exp.smoke_v2's throwaway probe item by import; no corpus or experimental content is sent",
      "writes out/slice3/availability.json; requires --confirm to run, because it spends and touches external services",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked",
      "declares its ONE auxiliary request: a single GET /api/v1/models per run to read live paid rates. It is not a generation probe and is not billable, and the artifact records it under probe.auxiliary_requests"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && git diff --quiet prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/ && test -z \"$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)\"",
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_availability.py"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "A2-verdict",
    "title": "exp3/slice3_verdict.py: apply the recorded margin rule mechanically",
    "depends_on": [
      "A1-probe"
    ],
    "files": [
      "exp3/slice3_verdict.py",
      "tests/test_slice3_verdict.py"
    ],
    "acceptance": [
      "ENVIRONMENT: run everything with /home/jmannings/dev/waveconv/.venv/bin/python (3.12). Bare `python` is system 3.14 without the project deps and fails at `import httpx`. No PyPI egress: never pip install, never create a venv.",
      "counts DISTINCT FAMILIES among candidates whose status is `ok` ONLY (B3): `substituted` never counts toward the pinned margin, and a test proves it does not",
      "reports `substituted` candidates separately as possible families for a NEW registration, for slice 4 to adjudicate",
      "a test proves two variants of one family count once (the cycle-1 ornith error)",
      "applies the recorded rule from DECISIONS.md 2026-08-30 mechanically: >5 families => M=5 registrable; exactly 5 => M=3/M=4 primary with the fifth as a declared stretch arm; <5 => neither, and the available set is reported",
      "reports the MARGIN explicitly (families ok, minus five), the deciding quantity under that rule",
      "enumerates the family-disjoint M=3 subsets the ok set supports",
      "tests cover all three branches with synthetic inputs INCLUDING the exactly-five boundary and a five-ok-plus-one-substituted case that must NOT be read as six",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_slice3_verdict.py"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "A3-gate",
    "title": "run_slice3.sh: one command, fail-closed, and it never spends",
    "depends_on": [
      "A2-verdict"
    ],
    "files": [
      "run_slice3.sh",
      "exp3/slice3_decide.py",
      "tests/test_slice3_gate.py"
    ],
    "acceptance": [
      "ENVIRONMENT: run everything with /home/jmannings/dev/waveconv/.venv/bin/python (3.12). Bare `python` is system 3.14 without the project deps and fails at `import httpx`. No PyPI egress: never pip install, never create a venv.",
      "ONE COMMAND, TWO MODES (B2): `run_slice3.sh --probe` performs the probes once, emits the artifact, computes the verdict and runs every assertion below; without the flag the same script validates the existing artifact and never calls an endpoint",
      "asserts Python 3.12 and the uv pin; the tag-clean check across committed, working-tree and untracked state over exp/ wct/ m0/; and that out/v3/ plus out/e1*_summary*.json are byte-identical to their content at e63f946 via `git show`",
      "asserts out/slice3/availability.json exists, is schema-valid, covers all six pinned candidates, and carries an identity record and a status for each",
      "asserts artifact FRESHNESS (A1): its prereg_v2.yaml digest matches the current file, and its age is reported",
      "asserts the paid call count never exceeds one per candidate, and echoes the calculated spend",
      "asserts no corpus or experimental item text, and no credential-shaped string, appears in the artifact",
      "NEGATIVE INTEGRATION TESTS (B5), each proving the gate FAILS: missing artifact; malformed artifact; incomplete candidate coverage; a catalogue-only success; a missing identity record; a mismatched registration digest; a changed frozen file including an UNTRACKED addition under exp/ wct/ m0/; a paid call count above the cap",
      "appends a DECISIONS.md entry derived from the artifact and the verdict, fingerprinted so --check detects a STALE entry rather than merely a missing one, and superseding a stale entry atomically rather than wedging the gate",
      "the gate's EXIT CODE is the pass signal, not its printed output; the targeted check asserts rc=0",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && bash run_slice3.sh; test $? -eq 0",
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_slice3_gate.py"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  }
]
```

## Open questions

- OQ1, OQ2 (REQUEST): both RESOLVED at the human gate 2026-08-30 and recorded in
  `DECISIONS.md`. M=5 requires margin; additional local families may be probed at zero cost
  and reported separately as margin candidates, adopted by nobody until slice 4.
- OQ3 (new, non-blocking): if a pinned model answers under an UNEXPECTED id, that is a
  substitution and the candidate is unavailable under `prereg_v2`'s resolution rule — but it
  may still be a usable family for a NEW registration, since cycle 3 pins its own panels.
  The plan records such a case as `substituted` rather than collapsing it to `ok` or `fail`,
  and leaves the adjudication to slice 4.
