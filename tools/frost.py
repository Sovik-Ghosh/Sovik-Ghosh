"""Shared frosted-glass background for the profile SVGs.

Gradient base + large blurred colour glows + faint grain, clipped to a rounded
card. Pure SVG filters (feGaussianBlur, feTurbulence) so it renders in GitHub's
<img> sandbox. `glass()` gives the semi-transparent panel style drawn on top.
"""

THEME = {
    "dark": dict(base=("#0b0f17", "#101826", "#0b1220"), edge="#ffffff", edge_op=0.14,
                 glows=[("#76b900", 0.30), ("#3987e5", 0.30), ("#8b5cf6", 0.20)], grain=0.06,
                 panel="#ffffff", panel_op=0.05, panel_edge_op=0.12, hi_op=0.18),
    "light": dict(base=("#f7faf3", "#eef4fb", "#f5f2fb"), edge="#1f2328", edge_op=0.10,
                  glows=[("#a3d65c", 0.45), ("#8ab8f0", 0.45), ("#c4b5fd", 0.35)], grain=0.05,
                  panel="#ffffff", panel_op=0.55, panel_edge_op=0.70, hi_op=0.9),
}


def background(W, H, theme, glow_xy, rx=16):
    """glow_xy: list of (cx, cy, r) in px, one per glow colour."""
    t = THEME[theme]
    b0, b1, b2 = t["base"]
    glows = "\n".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{col}" opacity="{op}"/>'
        for (cx, cy, r), (col, op) in zip(glow_xy, t["glows"]))
    return f'''<defs>
<linearGradient id="fb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{b0}"/><stop offset="0.55" stop-color="{b1}"/><stop offset="1" stop-color="{b2}"/></linearGradient>
<filter id="fblur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="70"/></filter>
<filter id="fgrain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter>
<clipPath id="fclip"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{rx}"/></clipPath>
</defs>
<g clip-path="url(#fclip)">
<rect width="{W}" height="{H}" fill="url(#fb)"/>
<g filter="url(#fblur)">
{glows}
</g>
<rect width="{W}" height="{H}" filter="url(#fgrain)" opacity="{t["grain"]}"/>
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{rx}" fill="none" stroke="{t["edge"]}" stroke-opacity="{t["edge_op"]}"/>'''


def glass(x, y, w, h, theme, rx=12):
    """Frosted panel: translucent fill, hairline border, top highlight."""
    t = THEME[theme]
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{t["panel"]}" fill-opacity="{t["panel_op"]}" '
            f'stroke="{t["panel"] if theme == "dark" else "#ffffff"}" stroke-opacity="{t["panel_edge_op"]}"/>'
            f'<line x1="{x + rx}" x2="{x + w - rx}" y1="{y + 0.5}" y2="{y + 0.5}" stroke="#ffffff" stroke-opacity="{t["hi_op"]}"/>')
