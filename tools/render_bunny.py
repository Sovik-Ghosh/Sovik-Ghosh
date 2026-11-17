"""Render a rotating sparse point cloud of the Bonn bunny dataset.

Points: SIFT matches between neighbouring views, triangulated with the dataset's
calibrated projection matrices (not an SfM pose estimate), filtered by
silhouette and reprojection error. Output: bunny-rig.gif (cameras + cloud), bunny-cloud.gif (close-up).

usage: python render_bunny.py <bunny_dir> <out_dir>
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from frost import background

data, out = Path(sys.argv[1]), Path(sys.argv[2])
N = 36
imgs = [cv2.imread(str(data / "images" / f"{i:04d}.ppm")) for i in range(N)]
masks = [cv2.imread(str(data / "silhouettes" / f"{i:04d}.pgm"), 0) == 0 for i in range(N)]
Ps = [np.loadtxt(data / "calib" / f"{i:04d}.txt", skiprows=1) for i in range(N)]

sift = cv2.SIFT_create(nfeatures=12000)
feats = []
for im, m in zip(imgs, masks):
    mk = cv2.dilate(m.astype(np.uint8) * 255, np.ones((9, 9), np.uint8))
    kp, de = sift.detectAndCompute(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), mk)
    feats.append((np.float32([k.pt for k in kp]), de))

matcher = cv2.BFMatcher(cv2.NORM_L2)
pts, cols = [], []
for i in range(N):
    for d in (1, 2, 3):
        j = (i + d) % N
        (pa, da), (pb, db) = feats[i], feats[j]
        good = [m for m, n in matcher.knnMatch(da, db, k=2) if m.distance < 0.8 * n.distance]
        if len(good) < 8:
            continue
        a = pa[[m.queryIdx for m in good]].T
        b = pb[[m.trainIdx for m in good]].T
        X = cv2.triangulatePoints(Ps[i], Ps[j], a, b)
        X = (X[:3] / X[3]).T
        ok = np.ones(len(X), bool)
        for P, uv in ((Ps[i], a.T), (Ps[j], b.T)):
            h = np.c_[X, np.ones(len(X))] @ P.T
            ok &= (h[:, 2] > 0) & (np.linalg.norm(h[:, :2] / h[:, 2:] - uv, axis=1) < 1.5)
        X, a = X[ok], a[:, ok]
        u, v = np.round(a).astype(int)
        pts.append(X)
        cols.append(imgs[i][v, u, ::-1])
pts, cols = np.vstack(pts), np.vstack(cols).astype(np.float32)

c = np.median(pts, 0)
r = np.linalg.norm(pts - c, axis=1)
keep = r < np.percentile(r, 98)
pts, cols = pts[keep] - c, cols[keep]
centres = np.array([-np.linalg.inv(P[:, :3]) @ P[:, 3] for P in Ps]) - c
print(f"{len(pts)} points, {N} cameras")

# up axis = normal of the camera ring plane, oriented towards the camera side
_, _, Vt = np.linalg.svd(centres - centres.mean(0))
up = Vt[2] * np.sign(Vt[2] @ centres.mean(0))
x0 = np.cross(up, [1, 0, 0]); x0 /= np.linalg.norm(x0)
y0 = np.cross(up, x0)
ring = np.linalg.norm(centres, axis=1).max()
cloud = np.percentile(np.linalg.norm(pts, axis=1), 95)
BG, GREEN = (13, 17, 23), (96, 150, 0)
fwd_cam = np.array([np.linalg.inv(P[:, :3]) @ np.array([0, 0, 1.0]) for P in Ps])
fwd_cam = fwd_cam / np.linalg.norm(fwd_cam, axis=1, keepdims=True)
fwd_cam *= np.sign(np.sum(fwd_cam * -centres, axis=1, keepdims=True))


def render(path, D, look_at, cams, dot, W=420, H=420, F=90, el=22):
    FOC = 0.9 * H
    frames = []
    for f in range(F):
        t = 2 * np.pi * f / F
        e = np.deg2rad(el)
        eye = look_at + D * (np.cos(e) * (np.cos(t) * x0 + np.sin(t) * y0) + np.sin(e) * up)
        fz = look_at - eye; fz /= np.linalg.norm(fz)
        fx = np.cross(fz, up); fx /= np.linalg.norm(fx)
        R = np.stack([fx, np.cross(fz, fx), fz])

        def proj(X):
            Y = (X - eye) @ R.T
            return W / 2 + FOC * Y[:, 0] / Y[:, 2], H / 2 + FOC * Y[:, 1] / Y[:, 2], Y[:, 2]

        img = Image.new("RGB", (W, H), BG)
        dr = ImageDraw.Draw(img)
        if cams:
            _, _, cz = proj(centres)
            for k in np.argsort(-cz):
                fwd = fwd_cam[k]
                a = np.cross(fwd, up); a /= np.linalg.norm(a)
                b = np.cross(fwd, a)
                base = centres[k] + 6 * fwd + 2.6 * np.array([a + b, a - b, -a - b, -a + b])
                px, py, _ = proj(np.vstack([centres[k], base]))
                quad = list(zip(px[1:], py[1:]))
                for q in quad:
                    dr.line([(px[0], py[0]), q], fill=GREEN, width=1)
                dr.polygon(quad, outline=GREEN)
        x, y, z = proj(pts)
        for idx in np.argsort(-z):
            col = tuple(int(v) for v in np.clip(cols[idx] * 1.25 + 20, 0, 255))
            dr.rectangle([x[idx] - dot, y[idx] - dot, x[idx] + dot, y[idx] + dot], fill=col)
        frames.append(img.quantize(colors=96, method=Image.Quantize.MEDIANCUT))
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=60, loop=0, optimize=True)
    print(path, f"{Path(path).stat().st_size / 1e6:.2f} MB")


out.mkdir(parents=True, exist_ok=True)
render(out / "bunny-rig.gif", D=2.3 * ring, look_at=(centres @ up).mean() * 0.2 * up, cams=True, dot=1)
render(out / "bunny-cloud.gif", D=3.4 * cloud, look_at=np.zeros(3), cams=False, dot=1, el=15)


# ---------------- profile banner (dark + light SVG) ----------------
def banner(path, dark):
    fg, sub, mono = ("#f0f6fc", "#c9d1d9", "#8b949e") if dark else ("#1f2328", "#424a53", "#57606a")
    bg0, bg1, edge = ("#0d1117", "#161b22", "#30363d") if dark else ("#ffffff", "#f6f8fa", "#d0d7de")
    green = "#76b900" if dark else "#5a8f00"
    sans = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
    monof = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace"
    # side view of the cloud, cameras on an arc above it
    t = np.deg2rad(180)
    right = np.cos(t) * x0 + np.sin(t) * y0
    fwd = np.cross(up, right)
    P2 = np.stack([right, -up])
    rng = np.random.default_rng(0)
    sel = rng.choice(len(pts), min(1500, len(pts)), replace=False)
    uv = pts[sel] @ P2.T
    depth = pts[sel] @ fwd
    s = 175 / np.ptp(uv[:, 1])
    cxp, cyp = 905, 205
    u, v = cxp + s * (uv[:, 0] - uv[:, 0].mean()), cyp + s * (uv[:, 1] - uv[:, 1].mean())
    o = 0.35 + 0.65 * (depth - depth.min()) / np.ptp(depth)
    el = []
    cams = [(cxp + 175 * np.cos(a), cyp - 40 - 120 * np.sin(a)) for a in np.deg2rad(np.linspace(160, 20, 7))]
    for i, (x, y) in enumerate(cams):
        for j in rng.choice(len(u), 3, replace=False):
            el.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{u[j]:.1f}" y2="{v[j]:.1f}" stroke="{green}" stroke-width="0.8" opacity="0.22"/>')
    for k in np.argsort(-o):
        el.append(f'<circle cx="{u[k]:.1f}" cy="{v[k]:.1f}" r="1.3" fill="{green}" opacity="{o[k]:.2f}"/>')
    for i, (x, y) in enumerate(cams):
        d = np.array([cxp - x, cyp - y]); d /= np.linalg.norm(d); n = np.array([-d[1], d[0]])
        b1, b2 = np.array([x, y]) + 18 * d + 8 * n, np.array([x, y]) + 18 * d - 8 * n
        el.append(f'<path class="cam" style="animation-delay:{i * 0.35:.2f}s" d="M{x:.1f} {y:.1f} L{b1[0]:.1f} {b1[1]:.1f} L{b2[0]:.1f} {b2[1]:.1f} Z" '
                  f'fill="none" stroke="{fg}" stroke-width="1.6" stroke-linejoin="round"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 320" width="1200" height="320" role="img" aria-label="Sovik Ghosh: computer vision and GPU inference">
<style>.cam{{animation:pulse 2.45s ease-in-out infinite}}@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.35}}}}
.cur{{animation:blink 1.1s steps(1) infinite}}@keyframes blink{{50%{{opacity:0}}}}</style>
{background(1200, 320, "dark" if dark else "light", [(180, 30, 230), (920, 200, 210), (560, 330, 200)])}
{chr(10).join(el)}
<text x="72" y="140" font-family="{sans}" font-size="80" font-weight="800" letter-spacing="-2" fill="{fg}">Sovik Ghosh</text>
<rect x="76" y="164" width="64" height="5" rx="2.5" fill="{green}"/>
<text x="74" y="210" font-family="{sans}" font-size="28" font-weight="600" fill="{sub}">Computer Vision · 3D Geometry · GPU Inference</text>
<text x="74" y="252" font-family="{monof}" font-size="19" fill="{mono}">pixels → geometry → real-time on the edge<tspan class="cur" fill="{green}"> ▍</tspan></text>
</svg>
'''
    Path(path).write_text(svg)
    print(path)


banner(out / "banner-dark.svg", True)
banner(out / "banner-light.svg", False)
