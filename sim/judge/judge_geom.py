"""Judge geometry: mesh -> manifold -> supersampled voxel fraction + convex-hull mask (EVAL_SPEC_v1 §2, §6)."""
import numpy as np
import manifold3d as m3
import trimesh
from PIL import Image, ImageDraw


def load_mesh(path):
    tm = trimesh.load(str(path), force="mesh")
    tm.merge_vertices()
    return tm


def to_manifold(tm):
    mesh = m3.Mesh(vert_properties=np.asarray(tm.vertices, np.float32), tri_verts=np.asarray(tm.faces, np.uint32))
    man = m3.Manifold(mesh)
    if man.is_empty():
        raise ValueError(f"mesh is not a valid closed manifold (status {man.status()})")
    return man


def mesh_info(tm, man):
    parts = tm.split(only_watertight=False)
    lo, hi = tm.bounds
    return {"bbox_min": lo.tolist(), "bbox_max": hi.tolist(), "extent": (hi - lo).tolist(),
            "volume_mm3": float(man.volume()), "mesh_volume_mm3": float(tm.volume) if tm.is_watertight else None,
            "watertight": bool(tm.is_watertight), "shells": int(len(parts)), "triangles": int(len(tm.faces))}


def make_box(tm, h, factor=1.5, max_dof=None):
    lo, hi = tm.bounds
    c = (lo + hi) / 2; S = (hi - lo) * factor
    n = np.ceil(S / h).astype(int)
    origin = c - n * h / 2
    return n, origin


def _raster(polys, x0, y0, hs, W, H):
    acc = np.zeros((H, W), bool)
    for p in polys:
        if len(p) < 3:
            continue
        img = Image.new("1", (W, H), 0)
        pts = [((x - x0) / hs - 0.5, (y - y0) / hs - 0.5) for x, y in p]
        ImageDraw.Draw(img).polygon(pts, fill=1)
        acc ^= np.array(img, bool)           # even-odd: holes cancel
    return acc


def occupancy(man, n, origin, h, sub=1):
    """Filled fraction per voxel, array [nz][ny][nx], from sub x sub x sub point samples per voxel."""
    nx, ny, nz = map(int, n)
    hs = h / sub
    W, H = nx * sub, ny * sub
    frac = np.zeros((nz, ny, nx), np.float32)
    for k in range(nz):
        acc = np.zeros((ny, nx), np.float32)
        for s in range(sub):
            z = origin[2] + (k + (s + 0.5) / sub) * h
            polys = man.slice(z).to_polygons()
            if not polys:
                continue
            m = _raster(polys, origin[0], origin[1], hs, W, H)
            acc += m.reshape(ny, sub, nx, sub).mean(axis=(1, 3))
        frac[k] = acc / sub
    return frac


def hull_mask(man, n, origin, h):
    return occupancy(man.hull(), n, origin, h, sub=1) >= 0.5
