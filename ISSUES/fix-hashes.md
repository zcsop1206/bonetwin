# Frozen-file hashes differ in the public copy

Draft issue, to file once the repo has a remote.

**What:** three frozen files were edited for publication (`docs/FROZEN_CHANGES.md`): `sim/judge/judge_intake.py`, `sim/EVAL_SPEC_v1.md` and `targets/SOURCES.md`. Their hashes no longer match the values recorded during the hackathon run, so `sha256sum -c JUDGE_MANIFEST.sha256` fails for `judge_intake.py`, and anyone checking the spec hashes quoted in the addenda will see a mismatch.

**Why:** to remove a personal local path and PreForm API detail that may not be publishable. No number, rule or scoring logic changed.

**Fix options:**
1. Publish a second manifest for the public copy (`JUDGE_MANIFEST.public.sha256`) and document both, keeping the original as the record of what was frozen.
2. Or make the frozen files byte-identical again by moving the redacted text out of them in the private originals in a future version, then re-freezing.

**Priority:** low. It affects verification of this copy against the run's records, not how the code behaves.
