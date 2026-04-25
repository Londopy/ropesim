"""
ropesim.notebook
================
Jupyter / IPython rich display integration.

Import this module in a notebook to enable ``_repr_html_()`` for all
ropesim objects::

    import ropesim.notebook   # patches classes in-place

After importing, any ropesim object displayed in a notebook cell renders
as a styled HTML card rather than a plain text repr.

Everything degrades gracefully: if matplotlib is not installed the force
curve is omitted; if the module is used outside Jupyter it is a no-op.
"""

from __future__ import annotations

import io
import base64
import html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ropesim.rope import Rope
    from ropesim.fall import FallResult
    from ropesim.simulate import SimulationResult
    from ropesim.anchor import AnchorSystem

# ── Shared style ─────────────────────────────────────────────────────────────

_CSS = """
<style>
.rs-card {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 13px;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 12px 16px;
  margin: 6px 0;
  background: #fafafa;
  max-width: 680px;
}
.rs-card h3 { margin: 0 0 8px 0; font-size: 15px; color: #222; }
.rs-card h4 { margin: 8px 0 4px 0; font-size: 13px; color: #555; }
.rs-table { border-collapse: collapse; width: 100%; }
.rs-table th {
  text-align: left; padding: 3px 8px;
  background: #eee; color: #333; font-weight: 600;
}
.rs-table td { padding: 3px 8px; border-bottom: 1px solid #eee; }
.rs-table tr:last-child td { border-bottom: none; }
.rs-pass { color: #2a7a2a; font-weight: 600; }
.rs-fail { color: #b22222; font-weight: 600; }
.rs-warn { color: #c47a00; font-weight: 600; }
.rs-neutral { color: #555; }
.rs-badge {
  display: inline-block; padding: 2px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 700; margin-left: 6px;
}
.rs-badge-green { background: #d4edda; color: #155724; }
.rs-badge-red   { background: #f8d7da; color: #721c24; }
.rs-badge-blue  { background: #d1ecf1; color: #0c5460; }
.rs-section { margin-top: 10px; }
</style>
"""


def _esc(v: object) -> str:
    return html.escape(str(v))


def _badge(label: str, kind: str = "blue") -> str:
    return f'<span class="rs-badge rs-badge-{kind}">{_esc(label)}</span>'


def _fig_to_b64(fig) -> str:
    """Render a matplotlib Figure to an inline base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=90, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


# ── Rope HTML ─────────────────────────────────────────────────────────────────

def _rope_repr_html(self) -> str:
    """Rich HTML card for a Rope object."""
    from ropesim import standards

    s = self.spec
    rows = [
        ("Name",             _esc(s.name)),
        ("Type",             _esc(s.rope_type.value)),
        ("Diameter",         f"{s.diameter_mm:.1f} mm"),
        ("Weight",           f"{s.weight_gpm:.0f} g/m"),
        ("UIAA Falls",       str(s.number_of_falls)),
        ("Impact Force",     _check_kn("Impact", s.impact_force_kn,
                                        standards.MAX_IMPACT_FORCE_KN.get(
                                            s.rope_type.value, 12.0))),
        ("Static Elong.",    f"{s.static_elongation_pct:.1f} %"),
        ("Dynamic Elong.",   _check_pct("Dynamic", s.dynamic_elongation_pct, 40.0)),
        ("Dry Certified",    ("Yes" if getattr(s, "dry_treated", False)
                              else "No")),
        ("Manufacturer",     _esc(getattr(s, "manufacturer", "—"))),
    ]

    table = _rows_to_table(rows)
    badge_colour = "green" if _rope_compliant(s) else "red"
    badge_text   = "EN 892 Compliant" if _rope_compliant(s) else "Check Required"

    return (
        _CSS
        + f'<div class="rs-card">'
        + f'<h3>🪢 {_esc(s.name)}{_badge(badge_text, badge_colour)}</h3>'
        + table
        + "</div>"
    )


def _check_kn(label: str, value: float, limit: float) -> str:
    cls = "rs-pass" if value <= limit else "rs-fail"
    return f'<span class="{cls}">{value:.2f} kN</span>'


def _check_pct(label: str, value: float, limit: float) -> str:
    cls = "rs-pass" if value <= limit else "rs-fail"
    return f'<span class="{cls}">{value:.1f} %</span>'


def _rope_compliant(spec) -> bool:
    from ropesim import standards
    limit = standards.MAX_IMPACT_FORCE_KN.get(spec.rope_type.value, 12.0)
    return spec.impact_force_kn <= limit and spec.dynamic_elongation_pct <= 40.0


# ── FallResult HTML ───────────────────────────────────────────────────────────

def _fallresult_repr_html(self) -> str:
    """Rich HTML card for a FallResult."""
    peak_cls = "rs-pass" if self.peak_force_kn <= 9.0 else (
               "rs-warn" if self.peak_force_kn <= 12.0 else "rs-fail")
    g_cls    = "rs-pass" if self.peak_deceleration_g <= 10.0 else "rs-fail"
    ff_cls   = "rs-pass" if self.fall_factor < 1.0 else (
               "rs-warn" if self.fall_factor < 1.5 else "rs-fail")

    rows = [
        ("Fall Factor",
         f'<span class="{ff_cls}">{self.fall_factor:.3f}</span>'),
        ("Peak Force",
         f'<span class="{peak_cls}">{self.peak_force_kn:.2f} kN '
         f'({self.peak_force_lbf:.0f} lbf)</span>'),
        ("Peak Deceleration",
         f'<span class="{g_cls}">{self.peak_deceleration_g:.1f} g</span>'),
        ("Fall Distance",   f"{self.fall_distance_m:.1f} m"),
        ("Rope Out",        f"{self.rope_out_m:.1f} m"),
        ("Elongation",      f"{self.elongation_m:.3f} m"),
        ("Rope Survived",   "Yes" if self.rope_survived else "No"),
    ]
    if getattr(self, "guide_mode_used", False):
        rows.append(("Belay Model", _badge("Self-locking (guide mode)", "blue")))

    table = _rows_to_table(rows)

    # Energy budget sub-table
    eb = self.energy_budget
    eb_rows = [
        ("Potential Energy",  f"{eb.potential_energy_j:.0f} J"),
        ("Rope Absorption",   f"{eb.rope_absorption_j:.0f} J"),
        ("Belay Device",      f"{eb.belay_device_j:.0f} J"),
        ("Residual (body)",   f"{eb.residual_j:.0f} J"),
    ]
    eb_table = _rows_to_table(eb_rows)

    # Force curve plot
    curve_html = ""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        fig, ax = plt.subplots(figsize=(6, 2.2))
        t = np.arange(len(self.force_curve))
        ax.plot(t, self.force_curve, color="#2270c4", linewidth=1.5)
        ax.fill_between(t, self.force_curve, alpha=0.15, color="#2270c4")
        ax.axhline(self.peak_force_kn, color="#c0392b", linewidth=0.8,
                   linestyle="--", label=f"Peak {self.peak_force_kn:.2f} kN")
        ax.set_xlabel("Timestep", fontsize=9)
        ax.set_ylabel("Force (kN)", fontsize=9)
        ax.set_title("Force–time curve", fontsize=10)
        ax.legend(fontsize=8)
        ax.tick_params(labelsize=8)
        fig.tight_layout()
        img_b64 = _fig_to_b64(fig)
        plt.close(fig)
        curve_html = (
            f'<div class="rs-section">'
            f'<img src="data:image/png;base64,{img_b64}" '
            f'style="max-width:100%;border-radius:4px;" />'
            f"</div>"
        )
    except Exception:
        pass  # matplotlib not available or headless issue — skip plot

    # Warnings
    warn_html = ""
    if self.warnings:
        items = "".join(
            f'<li class="rs-warn">{_esc(w)}</li>' for w in self.warnings
        )
        warn_html = (
            f'<div class="rs-section">'
            f'<h4>Warnings</h4><ul style="margin:0;padding-left:18px">{items}</ul>'
            f"</div>"
        )

    return (
        _CSS
        + '<div class="rs-card">'
        + f'<h3>⚡ FallResult{_badge(f"{self.peak_force_kn:.2f} kN", "green" if self.peak_force_kn <= 9.0 else "red")}</h3>'
        + table
        + '<div class="rs-section"><h4>Energy Budget</h4>' + eb_table + "</div>"
        + curve_html
        + warn_html
        + "</div>"
    )


# ── SimulationResult HTML ─────────────────────────────────────────────────────

def _simresult_repr_html(self) -> str:
    """Rich HTML card for a SimulationResult."""
    mode_badge = _badge(self.mode.value, "blue")
    type_badge = _badge(self.scenario_type.value, "blue")
    fr_html    = _fallresult_repr_html(self.fall_result)

    frame_info = ""
    if self.frame_data is not None:
        nf = len(self.frame_data.frames)
        dt = self.frame_data.dt_seconds
        ts = self.frame_data.total_time_seconds
        frame_info = (
            f'<div class="rs-section">'
            f"<h4>3D Simulation Data</h4>"
            f"<table class='rs-table'><tr><th>Frames</th><td>{nf}</td></tr>"
            f"<tr><th>dt</th><td>{dt*1000:.2f} ms</td></tr>"
            f"<tr><th>Total time</th><td>{ts:.3f} s</td></tr></table>"
            f"</div>"
        )

    return (
        _CSS
        + '<div class="rs-card">'
        + f'<h3>🎯 SimulationResult {mode_badge} {type_badge}</h3>'
        + fr_html.replace(_CSS, "")
        + frame_info
        + "</div>"
    )


# ── AnchorSystem HTML ─────────────────────────────────────────────────────────

def _anchorsystem_repr_html(self) -> str:
    """Rich HTML card with an inline SVG diagram for an AnchorSystem."""
    components = getattr(self, "components", [])
    anchor_type = getattr(self, "anchor_type", None)

    # Summary table
    rows = [
        ("Type",        _esc(anchor_type.value if anchor_type else "—")),
        ("Components",  str(len(components))),
        ("Redundant",   "Yes" if getattr(self, "redundant", True) else "No"),
    ]
    table = _rows_to_table(rows)

    # Component table
    comp_rows = []
    for i, c in enumerate(components):
        kind = type(c).__name__
        mbs  = getattr(c, "mbs_kn", getattr(c, "mbs_strength_kn", "—"))
        label = getattr(c, "label", f"#{i+1}")
        comp_rows.append((f"{kind} {label}", f"{mbs} kN" if isinstance(mbs, float) else str(mbs)))
    comp_table = _rows_to_table(comp_rows, headers=("Component", "MBS"))

    # Simple SVG anchor diagram
    svg = _anchor_svg(components)

    return (
        _CSS
        + '<div class="rs-card">'
        + f'<h3>⚓ AnchorSystem</h3>'
        + table
        + '<div class="rs-section"><h4>Components</h4>' + comp_table + "</div>"
        + '<div class="rs-section"><h4>Diagram</h4>' + svg + "</div>"
        + "</div>"
    )


def _anchor_svg(components: list) -> str:
    """Generate a simple SVG bolt-and-sling diagram."""
    n = max(len(components), 1)
    W, H = 300, 120
    cx = W // 2
    # Place components evenly across top
    xs = [int(W * (i + 1) / (n + 1)) for i in range(n)]
    bolt_y = 20

    circles = ""
    for i, x in enumerate(xs):
        c = components[i] if i < len(components) else None
        colour = "#4a90d9"
        label  = type(c).__name__[:1] if c else "?"
        circles += (
            f'<circle cx="{x}" cy="{bolt_y}" r="10" '
            f'fill="{colour}" stroke="#1a5276" stroke-width="1.5"/>'
            f'<text x="{x}" y="{bolt_y+4}" text-anchor="middle" '
            f'font-size="9" fill="white" font-weight="bold">{_esc(label)}</text>'
        )

    # Sling lines to central master point
    lines = "".join(
        f'<line x1="{x}" y1="{bolt_y+10}" x2="{cx}" y2="80" '
        f'stroke="#888" stroke-width="2"/>'
        for x in xs
    )

    # Master point
    master = (
        f'<circle cx="{cx}" cy="80" r="7" fill="#e74c3c" stroke="#922b21" stroke-width="1.5"/>'
        f'<line x1="{cx}" y1="87" x2="{cx}" y2="{H-10}" '
        f'stroke="#e74c3c" stroke-width="3"/>'
        f'<text x="{cx}" y="{H}" text-anchor="middle" font-size="9" fill="#555">Load</text>'
    )

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="border:1px solid #ddd;border-radius:4px;background:#f9f9f9">'
        + circles + lines + master +
        "</svg>"
    )


# ── Shared helper ─────────────────────────────────────────────────────────────

def _rows_to_table(rows: list[tuple[str, str]],
                   headers: tuple[str, str] | None = None) -> str:
    head = ""
    if headers:
        head = (
            f"<thead><tr>"
            f"<th>{_esc(headers[0])}</th><th>{_esc(headers[1])}</th>"
            f"</tr></thead>"
        )
    body = "".join(
        f"<tr><th>{_esc(k)}</th><td>{v}</td></tr>" for k, v in rows
    )
    return f'<table class="rs-table">{head}<tbody>{body}</tbody></table>'


# ── Patch classes ─────────────────────────────────────────────────────────────


# ── Patch classes ─────────────────────────────────────────────────────────────

def _patch() -> None:
    """Monkey-patch ``_repr_html_`` onto all ropesim display classes."""
    from ropesim.rope import Rope
    from ropesim.fall import FallResult
    from ropesim.anchor import AnchorSystem

    Rope._repr_html_ = _rope_repr_html
    FallResult._repr_html_ = _fallresult_repr_html
    AnchorSystem._repr_html_ = _anchorsystem_repr_html

    try:
        from ropesim.simulate import SimulationResult
        SimulationResult._repr_html_ = _simresult_repr_html
    except ImportError:
        pass


_patch()
