"""Synthetic known-answer shapes for the goal metric. Nothing from the contest. Cage envelope 30 x 20 x 12 mm."""
import sys
from pathlib import Path

import manifold3d as m3
import numpy as np
import trimesh

L = np.array([30.0, 20.0, 12.0])


def box(lo, hi):
    lo = np.array(lo, float); hi = np.array(hi, float)
    return m3.Manifold.cube((hi - lo).tolist()).translate(lo.tolist())


def channels(wx, wy, wz, cell=2.5, select=None):
    """A block of L minus square through-channels on a cell grid. wx, wy, wz = channel widths along x, y, z;
    select(p) -> scale of the width for the channel through p (None marks the channel's own axis)."""
    B = box([0, 0, 0], L)
    cuts = []
    nc = (L / cell).astype(int)
    pad = (L - nc * cell) / 2
    centres = [pad[d] + cell * (np.arange(nc[d]) + 0.5) for d in range(3)]

    def s(p):
        return 1.0 if select is None else select(p)

    for y in centres[1]:
        for z in centres[2]:
            w = wx * s((None, y, z))
            if w > 0:
                cuts.append(box([-1, y - w / 2, z - w / 2], [L[0] + 1, y + w / 2, z + w / 2]))
    for x in centres[0]:
        for z in centres[2]:
            w = wy * s((x, None, z))
            if w > 0:
                cuts.append(box([x - w / 2, -1, z - w / 2], [x + w / 2, L[1] + 1, z + w / 2]))
    for x in centres[0]:
        for y in centres[1]:
            w = wz * s((x, y, None))
            if w > 0:
                cuts.append(box([x - w / 2, y - w / 2, -1], [x + w / 2, y + w / 2, L[2] + 1]))
    return B - m3.Manifold.batch_boolean(cuts, m3.OpType.Add)


def frame(t=1.0):
    outer = box([0, 0, 0], L)
    return (outer - box([t, t, -1], [L[0] - t, L[1] - t, L[2] + 1])
            - box([t, -1, t], [L[0] - t, L[1] + 1, L[2] - t])
            - box([-1, t, t], [L[0] + 1, L[1] - t, L[2] - t]))


def tilted_plate(t=0.6):
    """A thin flat plate spanning the envelope diagonally: its hull is itself."""
    p = box([0, 0, 0], [33.0, 20.0, t])
    p = p.rotate([0, -float(np.degrees(np.arcsin((L[2] - t) / 33.0))), 0])
    bb = p.bounding_box()
    return p.translate([-bb[0], -bb[1], -bb[2]])


def save(man, path):
    m = man.to_mesh()
    trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=False).export(str(path))


MATCHED = (1.0, 1.0, 1.9)        # balanced: alone softer than bone, fused stiffer (chosen by a coarse sweep of the metric)
ALONE_MATCH = (0.6, 0.6, 1.7)    # closest to bone with empty voids, overshoots once fused
WEAK = (2.2, 2.2, 2.2)


def core(p):
    """Channels small in the central core and larger outside: locally stiff, similar on average."""
    c = (15.0, 10.0, 6.0)
    d = max(abs((v - ci) / (li / 2)) for v, ci, li in zip(p, c, L) if v is not None)
    return 0.6 if d < 0.6 else 1.12


def shapes():
    return {
        "solid_block": box([0, 0, 0], L),
        "thin_frame": frame(1.0),
        "tilted_sliver": tilted_plate(0.6),
        "lattice_matched": channels(*MATCHED),
        "lattice_alone_match": channels(*ALONE_MATCH),
        "lattice_local_stiff": channels(*MATCHED, select=core),
        "lattice_too_weak": channels(*WEAK),
    }


if __name__ == "__main__":
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    for name, m in shapes().items():
        save(m, out / f"{name}.stl")
        print(name, round(m.volume(), 1), m.bounding_box())
