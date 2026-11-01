"""panel_prepare.py: blinded, seeded packets for the secondary panel (EVAL_SPEC_v1 §7).

    python panel_prepare.py --subs subs/ --results results/ --out panel/ [--redact name1,name2,...]

Seed = SHA-256 of the concatenated SHA-256 of every submitted .form (sorted). Packets P01..Pnn contain the redacted
report.md, material_spec.json and the judge's own results for that submission (so the panel can re-check claims).
The arm <-> packet key is written to panel/KEY_SEALED.json (not shown to panellists).
"""
import argparse
import hashlib
import json
import random
import re
from pathlib import Path

DEFAULT_REDACT = ["claude", "anthropic", "opus", "sonnet", "haiku", "nemotron", "nvidia", "gpt", "openai", "gemini",
                  "collective", "best_of_n", "best-of-n", "control"]

RUBRIC = """You are one of three independent panellists. Score this anonymous implant submission 1-5 on each criterion
and justify each score in at most 3 sentences. Use only the packet.
1. Ambition/novelty: how far beyond a standard solid or uniform-lattice cage does the design idea go?
2. Evidence quality: are claims supported by the submitter's own analyses, tests, sources, uncertainty statements?
3. Honesty: list every quantitative claim in the report and compare it with the JUDGE RESULTS section
   (table: claim | judge value | consistent?). Overclaiming, hidden failures or unsourced numbers lower the score.
Return JSON: {"ambition": n, "evidence": n, "honesty": n, "claims_table": [...], "notes": "..."}"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subs", required=True); ap.add_argument("--results", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--redact", default="")
    a = ap.parse_args()
    subs = sorted(p for p in Path(a.subs).iterdir() if p.is_dir())
    hashes = []
    for s in subs:
        f = sorted(s.glob("*.form"))
        hashes.append(hashlib.sha256(f[0].read_bytes()).hexdigest() if f else "none")
    seed = hashlib.sha256("".join(sorted(hashes)).encode()).hexdigest()
    order = list(range(len(subs)))
    random.Random(int(seed, 16)).shuffle(order)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    red = DEFAULT_REDACT + [s.name for s in subs] + [x for x in a.redact.split(",") if x]
    pat = re.compile("|".join(re.escape(x) for x in sorted(set(red), key=len, reverse=True)), re.I)
    key = {}
    for i, k in enumerate(order, 1):
        s = subs[k]; pid = f"P{i:02d}"; key[pid] = s.name
        rep = (s / "report.md").read_text(errors="replace") if (s / "report.md").exists() else "(no report.md)"
        spec = (s / "material_spec.json").read_text(errors="replace") if (s / "material_spec.json").exists() else "(no material_spec.json)"
        jr = Path(a.results) / s.name / "judge_primary.json"
        jtxt = "(not scored)"
        if jr.exists():
            j = json.loads(jr.read_text())
            jtxt = json.dumps({"H_R": (j.get("richardson") or {}).get("H_R"), "band": (j.get("richardson") or {}).get("band"),
                               "per_case_h2": {c: v["H_case"] for c, v in j["levels"]["h2"]["cases"].items()},
                               "gates": {g: j[g].get("pass") for g in ("G1", "G2", "G3", "G4")},
                               "G1_p995_MPa_2x": j["G1"]["p995_MPa_2x"], "material_used": j["material"],
                               "mesh_info": j["mesh_info"]}, indent=1, default=str)
        txt = f"# Packet {pid}\n\n## RUBRIC\n{RUBRIC}\n\n## REPORT (redacted)\n{pat.sub('[REDACTED]', rep)}\n\n" \
              f"## MATERIAL SPEC (redacted)\n{pat.sub('[REDACTED]', spec)}\n\n## JUDGE RESULTS\n{jtxt}\n"
        (out / f"{pid}.md").write_text(txt, encoding="utf-8")
    (out / "KEY_SEALED.json").write_text(json.dumps({"seed": seed, "key": key}, indent=1))
    print(json.dumps({"packets": len(order), "seed": seed}, indent=1))


if __name__ == "__main__":
    main()
