"""Apply the recorded margin rule to the measured availability. Mechanically.

The rule was fixed by human decision BEFORE the measurement (DECISIONS.md, 2026-08-30), so
the number cannot be read generously after the fact:

    > 5 families answering  ->  M=5 is registrable
    = 5 families answering  ->  M=3/M=4 primary, the fifth family a DECLARED STRETCH ARM
    < 5 families answering  ->  neither; slice 4 is told what exists

Margin is the deciding quantity, because this programme has twice lost models mid-flight.
Registering M=5 on exactly five means one disappearance forces an unregistered substitution
or an abandoned arm -- what prereg_v2's "exact pinned id or the panel is DROPPED" rule exists
to prevent.

Only `ok` counts. A `substituted` candidate answered under an id the registration did not
expect, so the REGISTERED model is not available; counting it would inflate the margin and
defeat the measurement. Substitutions are reported separately as possible families for a NEW
registration, which slice 4 adjudicates.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

REQUIRED_FAMILIES = 5


def panel_reproducibility(art: dict, root=None) -> dict:
    """Which REGISTERED panels can still be run, decided per panel from the statuses.

    An earlier version hard-coded "neither panel is reproducible". That was false: panel A's
    three members all answered; only panel B lost members. A claim about the registration
    must be derived from the measurement, not written alongside it.
    """
    import yaml
    from pathlib import Path as _P
    spec = yaml.safe_load((_P(root or ".") / "prereg_v2.yaml").read_text())["panels"]
    status = {c["agent"]: c.get("status") for c in art.get("candidates") or []
              if c.get("tier") != "paid"}
    out = {}
    for pname, pdef in spec.items():
        members = list(pdef.get("cross_family") or {})
        broken = [m for m in members if status.get(m) != "ok"]
        out[pname] = {"members": members, "broken": broken,
                      "reproducible": not broken}
    return out


def verdict(art: dict) -> dict:
    """Two counts, deliberately NOT merged.

    `families_pinned_ok` -- families whose REGISTERED id answered. This is what cycle 2's
    panels can still be run with, and it is the honest answer to "do the pinned six still
    work".

    `families_reachable` -- families reachable by ANY probed id, including paid-tier twins
    of a withdrawn `:free` id. This is what CYCLE 3 can register, because cycle 3 pins its
    own panels and may pin the paid id directly.

    Collapsing these into one number was an error: it reported six families answering while
    two pinned ids had failed, which would have told slice 4 that cycle 2's panel B is
    reproducible when it is not. The margin rule is applied to `families_reachable`, since
    that is what a NEW registration can draw on, and the pinned count is reported beside it
    so the difference is visible rather than averaged away.
    """
    cands = art.get("candidates") or []
    pinned = [c for c in cands if c.get("tier") != "paid"]
    ok_pinned = [c for c in pinned if c.get("status") == "ok"]
    ok_any = [c for c in cands if c.get("status") == "ok"]
    sub = [c for c in cands if c.get("status") == "substituted"]
    failed = [c for c in pinned if c.get("status") == "fail"]

    fams_pinned = sorted({c["family"] for c in ok_pinned})
    fams_reach = sorted({c["family"] for c in ok_any})
    n = len(fams_reach)
    margin = n - REQUIRED_FAMILIES
    # a family reachable ONLY via a non-pinned id: usable by cycle 3, not by cycle 2
    via_alt = sorted(set(fams_reach) - set(fams_pinned))

    if n > REQUIRED_FAMILIES:
        reg, rationale = "M=5 registrable", (
            f"{n} families are reachable, {margin} more than the five required, so one "
            f"disappearance mid-run still leaves five.")
    elif n == REQUIRED_FAMILIES:
        reg, rationale = "M=3/M=4 primary, fifth family a declared stretch arm", (
            "exactly five families are reachable, leaving zero margin. Under the recorded "
            "rule M=5 is not registrable: one disappearance would force an unregistered "
            "substitution or an abandoned arm.")
    else:
        reg, rationale = "neither M=5 nor a five-family design", (
            f"only {n} families are reachable, {REQUIRED_FAMILIES - n} short of five. "
            f"Slice 4 registers what exists.")

    verified = sorted({c["family"] for c in ok_any if c.get("identity_verified")})
    return {
        "panel_reproducibility": panel_reproducibility(art),
        "families_identity_verified": verified,
        "n_families_identity_verified": len(verified),
        "identity_note": (
            f"{len(verified)} of {len(fams_reach)} reachable families answered under the id "
            f"expected for them. Expected identity DEFAULTS to the id requested; "
            f"prereg_v2.yaml pins an explicit alias override for one endpoint only (qwen on "
            f":8083, which legitimately answers as `ornith35`). A local candidate whose "
            f"/props weights cannot be read counts as unverified, because that registration "
            f"pins weights rather than an alias. Cycle 3 should pin an expected echo per "
            f"panel member so its exact-id rule has an explicit target rather than a "
            f"default."),
        "families_pinned_ok": fams_pinned,
        "n_families_pinned_ok": len(fams_pinned),
        "families_reachable": fams_reach,
        "n_families_reachable": n,
        "reachable_only_via_non_pinned_id": via_alt,
        "reachable_note": (
            "families in `reachable_only_via_non_pinned_id` answered under an id the "
            "registration does not pin (a paid-tier twin of a withdrawn :free id). Cycle 3 "
            "may pin that id directly; cycle 2's panels may NOT, because prereg_v2's rule is "
            "'exact pinned id or the panel is DROPPED'."),
        "required": REQUIRED_FAMILIES,
        "margin": margin,
        "margin_basis": "families_reachable",
        "registrable": reg,
        "rationale": rationale,
        "m3_subsets": ["+".join(s) for s in itertools.combinations(fams_reach, 3)],
        "n_m3_subsets": len(list(itertools.combinations(fams_reach, 3))),
        "substituted": [{"agent": c["agent"], "family": c["family"],
                         "note": c.get("note", "")} for c in sub],
        "substituted_note": (
            "answered under an unexpected id; the REGISTERED model is unavailable under "
            "prereg_v2's resolution rule. Not counted toward the pinned total."),
        "failed_pinned": [{"agent": c["agent"], "family": c["family"],
                           "error": ((c.get("error") or "").splitlines() or [""])[0][:80]}
                          for c in failed],
        "failed_note": (
            "did not answer on ONE attempt at the artifact's timestamp. Not 'unavailable': "
            "one probe cannot distinguish a dead model from a flaky minute, and a re-probe "
            "is a deliberate second invocation."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    art = json.loads((root / "out/slice3/availability.json").read_text())
    v = verdict(art)
    out = root / "out/slice3/verdict.json"
    out.write_text(json.dumps(v, indent=2, sort_keys=True))
    print(f"pinned ids answering:  {v['n_families_pinned_ok']} families "
          f"({', '.join(v['families_pinned_ok'])})")
    print(f"families reachable:    {v['n_families_reachable']} "
          f"({', '.join(v['families_reachable'])})")
    if v["reachable_only_via_non_pinned_id"]:
        print(f"  reachable ONLY via a non-pinned id: "
              f"{', '.join(v['reachable_only_via_non_pinned_id'])}")
    print(f"margin vs five (on reachable): {v['margin']:+d}")
    print(f"VERDICT: {v['registrable']}")
    print(f"  {v['rationale']}")
    if v["substituted"]:
        print(f"  substituted (not counted): {[s['agent'] for s in v['substituted']]}")
    if v["failed_pinned"]:
        print(f"  pinned ids that failed: {[s['agent'] for s in v['failed_pinned']]}")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
