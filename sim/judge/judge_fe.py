"""Judge FE: implant embedded in an orthotropic bone box, hex8 voxels on a rectangular grid (EVAL_SPEC.md §2-§6).

Geometry comes in as two arrays on the element grid (index order [k][j][i] = z, y, x):
  frac  : implant filled fraction per voxel (supersampled), 0..1
  hull  : bool, voxel centre inside the implant's convex hull (region R)
Element classes: bone (outside R and frac == 0), implant (frac > 0; E_imp x frac, isotropic), void (in R, frac == 0; removed).
"""
import time

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

G = 1 / np.sqrt(3)
XI = np.array([-1, 1, 1, -1, -1, 1, 1, -1]); ET = np.array([-1, -1, 1, 1, -1, -1, 1, 1]); ZE = np.array([-1, -1, -1, -1, 1, 1, 1, 1])
VOIGT = [(0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1)]


def bmat(h, a, b, c):
    dx = XI * (1 + b * ET) * (1 + c * ZE) / 8 * 2 / h
    dy = ET * (1 + a * XI) * (1 + c * ZE) / 8 * 2 / h
    dz = ZE * (1 + a * XI) * (1 + b * ET) / 8 * 2 / h
    B = np.zeros((6, 24))
    B[0, 0::3] = dx; B[1, 1::3] = dy; B[2, 2::3] = dz
    B[3, 1::3] = dz; B[3, 2::3] = dy
    B[4, 0::3] = dz; B[4, 2::3] = dx
    B[5, 0::3] = dy; B[5, 1::3] = dx
    return B


def ke(h, C):
    K = np.zeros((24, 24))
    for a in (-G, G):
        for b in (-G, G):
            for c in (-G, G):
                B = bmat(h, a, b, c)
                K += B.T @ C @ B * (h / 2) ** 3
    return K


def iso_C(E, nu):
    lam = E * nu / ((1 + nu) * (1 - 2 * nu)); mu = E / (2 * (1 + nu))
    C = np.zeros((6, 6)); C[:3, :3] = lam; C[[0, 1, 2], [0, 1, 2]] += 2 * mu; C[[3, 4, 5], [3, 4, 5]] = mu
    return C


class Box:
    def __init__(self, n, h, origin):
        self.nx, self.ny, self.nz = map(int, n); self.h = float(h); self.origin = np.asarray(origin, float)
        self.n1 = (self.nx + 1, self.ny + 1, self.nz + 1)

    def nid(self, i, j, k):
        return i + self.n1[0] * (j + self.n1[1] * k)

    def conn(self, e):
        nx, ny = self.nx, self.ny
        i = e % nx; j = (e // nx) % ny; k = e // (nx * ny)
        n = self.nid
        return np.stack([n(i, j, k), n(i + 1, j, k), n(i + 1, j + 1, k), n(i, j + 1, k),
                         n(i, j, k + 1), n(i + 1, j, k + 1), n(i + 1, j + 1, k + 1), n(i, j + 1, k + 1)], 1)

    def node_ijk(self, nodes):
        a, b = self.n1[0], self.n1[1]
        return np.stack([nodes % a, (nodes // a) % b, nodes // (a * b)], 1)


def assemble(box, frac, hullfrac, C_bone, C_imp, levels=24, graft=0.0):
    """Per voxel: a = implant fill fraction, c = convex-hull fill fraction (both supersampled).
    Stiffness = a * C_imp + (1 - c) * C_bone; the part of the voxel inside the hull but not filled (c - a) is void.
    Pure-void voxels (a = 0, c = 1) are removed. Bone voxels for the H metric: c == 0 (entirely outside R)."""
    L = levels
    fa = frac.ravel(); fc = np.maximum(hullfrac.ravel(), fa)
    ia = np.rint(fa * L).astype(int); ia[(fa > 1e-6) & (ia == 0)] = 1
    bfrac = (1 - fc) + graft * (fc - fa)       # graft option: hull voids filled with graft = graft x C_bone (spec: 0)
    ib = np.rint(bfrac * L).astype(int); ib[(bfrac > 1e-6) & (ib == 0)] = 1
    keep = (ia > 0) | (ib > 0)
    elems = np.nonzero(keep)[0]
    ia = ia[elems]; ib = ib[elems]
    isb = (fc[elems] <= 1e-6)
    q = ia * (L + 1) + ib
    Ke_bone = ke(box.h, C_bone); Ke_imp1 = ke(box.h, C_imp)
    Ke_list = [Ke_imp1 * (i / L) + Ke_bone * (j / L) for i in range(L + 1) for j in range(L + 1)]
    C_list = [C_imp * (i / L) + C_bone * (j / L) for i in range(L + 1) for j in range(L + 1)]
    cn = box.conn(elems)
    used, inv = np.unique(cn, return_inverse=True)
    cl = inv.reshape(cn.shape)
    dofs = (3 * cl[:, :, None] + np.arange(3)).reshape(len(cn), 24)
    dofs = dofs.astype(np.int32)
    nd = 3 * len(used)
    K = assemble_K(np.stack(Ke_list), q, dofs, nd)
    return {"K": K, "elems": elems, "q": q, "isb": isb, "used": used, "dofs": dofs, "Ke": Ke_list, "C": C_list, "nd": nd}


def assemble_K(Ke_stack, q, dofs, nd, scale=None, chunk=40000):
    """Chunked COO -> CSR assembly (bounded temporaries: about 0.6 GB per 40k elements at most)."""
    K = None
    for a in range(0, len(q), chunk):
        b = min(a + chunk, len(q))
        vals = Ke_stack[q[a:b]]
        if scale is not None:
            vals = vals * scale[a:b, None, None]
        d = dofs[a:b]
        rows = np.repeat(d, 24, axis=1).ravel(); cols = np.tile(d, (1, 24)).ravel()
        Kc = sp.csr_matrix((vals.reshape(-1), (rows, cols)), shape=(nd, nd))
        Kc.sum_duplicates()
        K = Kc if K is None else K + Kc
        del vals, rows, cols, Kc
    return K


def face_loads(box, used, sigma_list):
    """Consistent nodal loads for uniform tractions t = sigma . n on the 6 box faces. Returns F (nd x ncases)."""
    ijk = box.node_ijk(used)
    h = box.h; n1 = box.n1
    F = np.zeros((3 * len(used), len(sigma_list)))
    for ax in range(3):
        for side, val in ((-1, 0), (1, n1[ax] - 1)):
            on = ijk[:, ax] == val
            ids = np.nonzero(on)[0]
            others = [a for a in range(3) if a != ax]
            trib = np.ones(len(ids)) * h * h
            for o in others:
                edge = (ijk[ids, o] == 0) | (ijk[ids, o] == n1[o] - 1)
                trib *= np.where(edge, 0.5, 1.0)
            nvec = np.zeros(3); nvec[ax] = side
            for c, sig in enumerate(sigma_list):
                t = sig @ nvec
                for d in range(3):
                    np.add.at(F[:, c], 3 * ids + d, trib * t[d])
    return F


def pins(box, used):
    """3-2-1 rigid-mode suppression at three box corners."""
    loc = {int(n): k for k, n in enumerate(used)}
    A = loc[box.nid(0, 0, 0)]; B = loc[box.nid(box.nx, 0, 0)]; Cn = loc[box.nid(0, box.ny, 0)]
    return np.array([3 * A, 3 * A + 1, 3 * A + 2, 3 * B + 1, 3 * B + 2, 3 * Cn + 2])


_AMG = {}


def rigid_modes(xyz):
    Q = xyz - xyz.mean(0)
    n = len(Q)
    B = np.zeros((n, 3, 6))
    for k in range(3):
        B[:, k, k] = 1
    for r in range(3):
        w = np.zeros(3); w[r] = 1
        B[:, :, 3 + r] = np.cross(w, Q)
    return B.reshape(3 * n, 6)


def solve(K, F, pd, tol=1e-8, maxiter=4000, log=None, M=None, xyz=None, X0=None):
    """CG preconditioned by pyamg smoothed aggregation with the 6 rigid-body modes as near-nullspace."""
    nd = K.shape[0]
    mask = np.ones(nd); mask[pd] = 0
    A = (sp.diags(mask) @ K @ sp.diags(mask) + sp.diags(1 - mask)).tocsr()
    if M is None:
        import pyamg
        B = rigid_modes(xyz) if xyz is not None else None
        if B is not None:
            B[pd] = 0
        ml = pyamg.smoothed_aggregation_solver(A, B=B, strength=("symmetric", {"theta": 0.0}), max_coarse=500)
        M = ml.aspreconditioner(cycle="V")
    U = np.zeros_like(F)
    for c in range(F.shape[1]):
        rhs = mask * F[:, c]
        it = [0]
        x0 = None if X0 is None else X0[:, c] * mask
        x, info = spla.cg(A, rhs, x0=x0, rtol=tol, maxiter=maxiter, M=M, callback=lambda xk: it.__setitem__(0, it[0] + 1))
        rel = float(np.linalg.norm(rhs - A @ x) / (np.linalg.norm(rhs) or 1))
        if log is not None:
            log.append({"cg_iters": it[0], "info": int(info), "rel_residual": rel})
        U[:, c] = x
    return U, M


def element_strain(box, asm, u):
    """Strain at element centres (Voigt, engineering shear) for every kept element."""
    B0 = bmat(box.h, 0, 0, 0)
    ue = u[asm["dofs"]]
    return ue @ B0.T


def von_mises(s):
    sx, sy, sz, tyz, txz, txy = s.T
    return np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2) + 3 * (tyz ** 2 + txz ** 2 + txy ** 2))


def sigma_tensor(v):
    s = np.zeros((3, 3))
    for I, (i, j) in enumerate(VOIGT):
        s[i, j] = s[j, i] = v[I]
    return s
