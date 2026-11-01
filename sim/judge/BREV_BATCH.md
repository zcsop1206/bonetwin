# Judge batch on Brev (judge_* runs; shared $10 pool)

The compute agent verified Brev at about 03:15: an L40S boots in 86 s, and shell, docker and NGC public containers work. This recipe is the plan for when a box comes up. **The laptop fallback is the same `judge_batch.py`**, run with `--workers 1` after 07:00.

1. **Prepare on the laptop.** PreFormServer and the hash check run only here.
   - For each run: `python judge_submission.py --folder submissions/<run> --grounding grounding/<run>.json --out results/<run> --prepare-only`
   - Bundle the judge code, the targets and the prepared results: `tar czf judge_bundle.tgz -C bonetwin sim/judge sim/calibration.json targets results`
2. **Start a box and copy the bundle.**
   - `python compute/bt_compute.py start --arm judge --run final --type A6000 --name judge --hours 2`
     Use the `judge_final` naming per FAIRSHARE. Check the start and `--arm` syntax with the compute agent first.
   - `python compute/bt_compute.py copy-to ... judge_bundle.tgz /home/ubuntu/`
3. **Set up the box.** Use a container. Per the compute agent at about 03:15, L40S boots in 86 s and docker works, but pip Warp and PhysicsNeMo imports failed on the host. The judge needs no Warp and no GPU:
   ```
   tar xzf judge_bundle.tgz
   docker run --rm -v $PWD:/w -w /w/sim/judge python:3.11-slim bash -c      "pip install -q numpy scipy pyamg trimesh manifold3d pillow && python judge_batch.py /w/results --threads 2"
   ```
4. **Run.** This is the `docker run` line above. Without docker, use a `uv` Python 3.11 venv with the same pip list.
   - The worker count is set automatically to min(12, jobs, CPUs/2, free RAM / 6 GB).
   - Each process takes about 1 GB per million DOF. h2 = 0.2 on a 25 x 12 x 10 mm cage is about 3.7 M DOF, or 4-5 GB.
5. **Copy back and stop.** `copy-from` the `results/` folder, then `stop`. Rank on the laptop: `python judge_rank.py results --out ranking.json`.

The solver runs on the CPU (CG preconditioned with pyamg smoothed aggregation and rigid-body modes). The GPU is not used: a diagonal-preconditioned GPU CG converges poorly at the implant-bone stiffness contrast (up to 500x for Ti). An instance is therefore chosen for its CPU count and RAM, not for its GPU.
