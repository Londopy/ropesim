"""
ropesim.viz
===========
Matplotlib-based visualization functions for ropesim results.

All functions return ``(fig, ax)`` so the caller can further customise or save.
Dark theme is applied by default (pass ``dark=False`` to use the active style).

Usage::

    from ropesim import viz
    fig, ax = viz.plot_force_curve(result)
    fig.savefig("force_curve.png", dpi=150)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.figure import Figure
from matplotlib.axes import Axes

if TYPE_CHECKING:
    from ropesim.fall import FallResult, EnergyBudget
    from ropesim.rope import Rope
    from ropesim.anchor import AnchorSystem

# ── Theme helpers ─────────────────────────────────────────────────────────────

_DARK_BG    = "#1a1a2e"
_PANEL_BG   = "#16213e"
_ACCENT     = "#0f3460"
_HIGHLIGHT  = "#e94560"
_GREEN      = "#4caf50"
_YELLOW     = "#ffb300"
_TEXT       = "#e0e0e0"
_GRID       = "#2a2a4a"

_COMPONENT_COLORS = [
    "#4fc3f7", "#81c784", "#ffb74d", "#e57373",
    "#ba68c8", "#4dd0e1", "#aed581", "#f06292",
]


def _apply_dark(fig: Figure, ax: Axes) -> None:
    """Apply ropesim dark theme to a figure/axes pair."""
    fig.patch.set_facecolor(_DARK_BG)
    ax.set_facecolor(_PANEL_BG)
    ax.tick_params(colors=_TEXT, labelsize=9)
    ax.xaxis.label.set_color(_TEXT)
    ax.yaxis.label.set_color(_TEXT)
    ax.title.set_color(_TEXT)
    ax.spines[:].set_color(_GRID)
    ax.grid(True, color=_GRID, linewidth=0.6, linestyle="--", alpha=0.7)


def _new_fig(dark: bool = True, figsize=(9, 5)) -> tuple[Figure, Axes]:
    fig, ax = plt.subplots(figsize=figsize)
    if dark:
        _apply_dark(fig, ax)
    return fig, ax


# ── 1. Force-time curve ───────────────────────────────────────────────────────

def plot_force_curve(
    result: "FallResult",
    *,
    dark: bool = True,
    overlay: Optional[list["FallResult"]] = None,
    overlay_labels: Optional[list[str]] = None,
    label: str = "Primary",
) -> tuple[Figure, Axes]:
    """
    Plot rope force (kN) vs time (ms) for a FallResult.

    Parameters
    ----------
    result:
        Primary simulation result.
    overlay:
        Additional results to overlay on the same axes.
    label:
        Legend label for the primary result.
    """
    fig, ax = _new_fig(dark)

    def _plot_curve(res: "FallResult", lbl: str, color: str, alpha: float = 1.0) -> None:
        curve = np.array(res.force_curve)
        t_ms  = np.arange(len(curve))
        ax.plot(t_ms, curve, color=color, linewidth=1.8, label=lbl, alpha=alpha)
        peak_idx = int(np.argmax(curve))
        ax.annotate(
            f"  Peak\n  {res.peak_force_kn:.1f} kN",
            xy=(peak_idx, curve[peak_idx]),
            xytext=(peak_idx + max(5, len(t_ms) // 15), curve[peak_idx] * 0.95),
            color=color,
            fontsize=8,
            arrowprops=dict(arrowstyle="->", color=color, lw=0.8),
        )

    _plot_curve(result, label, _HIGHLIGHT)

    if overlay:
        labels = overlay_labels or [f"Scenario {i+2}" for i in range(len(overlay))]
        for i, (res, lbl) in enumerate(zip(overlay, labels)):
            color = _COMPONENT_COLORS[i % len(_COMPONENT_COLORS)]
            _plot_curve(res, lbl, color, alpha=0.80)

    ax.set_xlabel("Time (ms)", fontsize=10)
    ax.set_ylabel("Rope Force (kN)", fontsize=10)
    ax.set_title(
        f"Fall Force–Time Curve   |   FF = {result.fall_factor:.2f}   "
        f"|   Peak = {result.peak_force_kn:.2f} kN  ({result.peak_force_lbf:.0f} lbf)",
        fontsize=10,
        color=_TEXT if dark else "black",
    )
    ax.axhline(0, color=_GRID, linewidth=0.8)
    ax.legend(fontsize=8, facecolor=_ACCENT if dark else "white",
              labelcolor=_TEXT if dark else "black")
    ax.yaxis.set_major_locator(mticker.MultipleLocator(1.0))
    fig.tight_layout()
    return fig, ax


# ── 2. Anchor force distribution ──────────────────────────────────────────────

def plot_anchor_distribution(
    anchor: "AnchorSystem",
    load_kn: float,
    angle_range: tuple[float, float] = (-90.0, 90.0),
    steps: int = 180,
    *,
    dark: bool = True,
) -> tuple[Figure, Axes]:
    """
    Plot per-component force (kN) vs load angle (°) for an AnchorSystem.

    A horizontal dashed line marks each component's effective MBS.
    """
    fig, ax = _new_fig(dark)

    sweep = anchor.load_sweep(load_kn, angle_range, steps)  # (steps × n)
    angles = np.linspace(angle_range[0], angle_range[1], steps)
    n_comp = sweep.shape[1]

    for i in range(n_comp):
        color = _COMPONENT_COLORS[i % len(_COMPONENT_COLORS)]
        comp  = anchor.components[i]
        label = f"Component {i}  (MBS {comp.effective_mbs():.1f} kN)"
        ax.plot(angles, sweep[:, i], color=color, linewidth=1.8, label=label)
        ax.axhline(
            comp.effective_mbs(),
            color=color,
            linewidth=0.9,
            linestyle="--",
            alpha=0.60,
        )

    ax.set_xlabel("Load Angle (°)", fontsize=10)
    ax.set_ylabel("Component Force (kN)", fontsize=10)
    ax.set_title(
        f"Anchor Load Distribution   |   {anchor.anchor_type.value}   "
        f"|   Load = {load_kn:.1f} kN",
        fontsize=10,
        color=_TEXT if dark else "black",
    )
    ax.axvline(0, color=_GRID, linewidth=0.9, linestyle=":")
    ax.legend(fontsize=8, facecolor=_ACCENT if dark else "white",
              labelcolor=_TEXT if dark else "black")
    fig.tight_layout()
    return fig, ax


# ── 3. Energy budget ──────────────────────────────────────────────────────────

def plot_energy_budget(
    result: "FallResult",
    *,
    dark: bool = True,
) -> tuple[Figure, Axes]:
    """Horizontal stacked bar chart of energy partitioning."""
    fig, ax = _new_fig(dark, figsize=(9, 3.5))

    eb = result.energy_budget
    categories = ["Potential Energy", "Rope Absorption", "Belay Device", "Residual"]
    values      = [
        eb.potential_energy_j,
        eb.rope_absorption_j,
        eb.belay_device_j,
        eb.residual_j,
    ]
    colors = [_HIGHLIGHT, _GREEN, _YELLOW, _COMPONENT_COLORS[3]]

    left = 0.0
    for cat, val, col in zip(categories, values, colors):
        bar = ax.barh(0, val, left=left, color=col, height=0.5, label=f"{cat}: {val:.0f} J")
        left += val

    ax.set_xlabel("Energy (J)", fontsize=10)
    ax.set_yticks([])
    ax.set_title("Fall Energy Budget", fontsize=10, color=_TEXT if dark else "black")
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.45),
        ncol=2,
        fontsize=8,
        facecolor=_ACCENT if dark else "white",
        labelcolor=_TEXT if dark else "black",
    )
    fig.tight_layout()
    return fig, ax


# ── 4. Rope elongation curve ──────────────────────────────────────────────────

def plot_rope_elongation(
    rope: "Rope",
    force_range: tuple[float, float] = (0.0, 15.0),
    steps: int = 200,
    *,
    dark: bool = True,
) -> tuple[Figure, Axes]:
    """Applied force (kN) vs elongation (%) with EN reference lines."""
    fig, ax = _new_fig(dark)

    try:
        from ropesim._rustcore import compute_elongation
        forces = np.linspace(force_range[0], force_range[1], steps)
        lengths = np.array([
            compute_elongation(
                rope.spec.static_elongation_pct,
                rope.spec.dynamic_elongation_pct,
                f,
                100.0,  # reference length 100 m → output is %
            )
            for f in forces
        ])
        elongation_pct = lengths - 100.0
    except ImportError:
        forces = np.linspace(force_range[0], force_range[1], steps)
        elongation_pct = np.linspace(
            0, rope.spec.dynamic_elongation_pct, steps
        )

    ax.plot(forces, elongation_pct, color=_HIGHLIGHT, linewidth=2.0, label="Elongation")
    ax.axhline(
        rope.spec.static_elongation_pct,
        color=_GREEN, linestyle="--", linewidth=1.0,
        label=f"Static ({rope.spec.static_elongation_pct:.1f}%)"
    )
    ax.axhline(
        rope.spec.dynamic_elongation_pct,
        color=_YELLOW, linestyle="--", linewidth=1.0,
        label=f"Dynamic ({rope.spec.dynamic_elongation_pct:.1f}%)"
    )

    ax.set_xlabel("Applied Force (kN)", fontsize=10)
    ax.set_ylabel("Elongation (%)", fontsize=10)
    ax.set_title(
        f"Rope Elongation Curve — {rope.spec.name}",
        fontsize=10, color=_TEXT if dark else "black"
    )
    ax.legend(fontsize=8, facecolor=_ACCENT if dark else "white",
              labelcolor=_TEXT if dark else "black")
    fig.tight_layout()
    return fig, ax


# ── 5. Diameter under load ────────────────────────────────────────────────────

def plot_diameter_under_load(
    rope: "Rope",
    force_range: tuple[float, float] = (0.0, 15.0),
    steps: int = 200,
    *,
    dark: bool = True,
) -> tuple[Figure, Axes]:
    """Applied force (kN) vs estimated rope diameter (mm)."""
    fig, ax = _new_fig(dark)

    forces = np.linspace(force_range[0], force_range[1], steps)
    try:
        from ropesim._rustcore import compute_diameter_under_load
        diameters = np.array([
            compute_diameter_under_load(
                rope.spec.diameter_mm,
                rope.spec.sheath_percentage,
                f,
            )
            for f in forces
        ])
    except ImportError:
        diameters = np.full(steps, rope.spec.diameter_mm)

    ax.plot(forces, diameters, color=_COMPONENT_COLORS[0], linewidth=2.0)
    ax.axhline(rope.spec.diameter_mm, color=_GRID, linestyle="--", linewidth=0.8,
               label=f"Nominal {rope.spec.diameter_mm:.1f} mm")
    ax.set_xlabel("Applied Force (kN)", fontsize=10)
    ax.set_ylabel("Diameter (mm)", fontsize=10)
    ax.set_title(
        f"Rope Diameter Under Load — {rope.spec.name}",
        fontsize=10, color=_TEXT if dark else "black"
    )
    ax.legend(fontsize=8, facecolor=_ACCENT if dark else "white",
              labelcolor=_TEXT if dark else "black")
    fig.tight_layout()
    return fig, ax


# ── 6. Anchor heatmap ─────────────────────────────────────────────────────────

def plot_anchor_heatmap(
    sweep_data: np.ndarray,
    angle_range: tuple[float, float],
    component_names: list[str],
    *,
    dark: bool = True,
) -> tuple[Figure, Axes]:
    """
    2-D heatmap: angle (y-axis) vs component (x-axis), colour = force (kN).

    ``sweep_data`` should be shape ``(steps, n_components)``.
    """
    fig, ax = _new_fig(dark, figsize=(8, 6))

    im = ax.imshow(
        sweep_data,
        aspect="auto",
        origin="lower",
        extent=[
            -0.5, sweep_data.shape[1] - 0.5,
            angle_range[0], angle_range[1],
        ],
        cmap="plasma",
        interpolation="bilinear",
    )
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("Force (kN)", color=_TEXT if dark else "black", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color=_TEXT if dark else "black")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=_TEXT if dark else "black")

    ax.set_xticks(range(len(component_names)))
    ax.set_xticklabels(component_names, fontsize=8)
    ax.set_xlabel("Component", fontsize=10)
    ax.set_ylabel("Load Angle (°)", fontsize=10)
    ax.set_title("Anchor Force Heatmap", fontsize=10, color=_TEXT if dark else "black")
    fig.tight_layout()
    return fig, ax


# ── 7. Fall scenario schematic ────────────────────────────────────────────────

def plot_fall_scenario(
    protection_heights: list[float],
    climber_height_m: float,
    peak_forces: Optional[list[float]] = None,
    *,
    dark: bool = True,
) -> tuple[Figure, Axes]:
    """
    Schematic route diagram showing protection placement and forces.

    ``protection_heights`` — heights of gear placements (m above belay)
    ``peak_forces``        — force (kN) at each piece (optional, for colouring)
    """
    fig, ax = _new_fig(dark, figsize=(5, 9))

    max_h = max(protection_heights + [climber_height_m]) * 1.1

    # Route line
    ax.plot([0, 0], [0, max_h], color=_GRID, linewidth=3, zorder=1)

    # Belay anchor at bottom
    ax.scatter([0], [0], color=_GREEN, s=150, zorder=5, marker="s", label="Belay")

    # Protection pieces
    mbs_kn = 25.0  # default
    for i, h in enumerate(protection_heights):
        force = peak_forces[i] if peak_forces else None
        if force is None:
            color = _COMPONENT_COLORS[i % len(_COMPONENT_COLORS)]
        elif force < mbs_kn * 0.5:
            color = _GREEN
        elif force < mbs_kn * 0.7:
            color = _YELLOW
        else:
            color = _HIGHLIGHT

        ax.scatter([0], [h], color=color, s=120, zorder=5, marker="D")
        label_txt = f"  P{i+1}  h={h:.1f}m"
        if force:
            label_txt += f"  {force:.1f}kN"
        ax.text(0.1, h, label_txt, color=_TEXT if dark else "black", fontsize=8, va="center")

    # Climber
    ax.scatter([0], [climber_height_m], color=_HIGHLIGHT, s=200, zorder=6,
               marker="^", label=f"Climber  h={climber_height_m:.1f}m")

    ax.set_xlim(-0.5, 2.0)
    ax.set_ylim(-0.5, max_h)
    ax.set_xlabel("")
    ax.set_ylabel("Height above belay (m)", fontsize=10)
    ax.set_title("Fall Scenario", fontsize=10, color=_TEXT if dark else "black")
    ax.set_xticks([])
    ax.legend(fontsize=8, facecolor=_ACCENT if dark else "white",
              labelcolor=_TEXT if dark else "black", loc="upper right")
    fig.tight_layout()
    return fig, ax


# ── 8. Comparison overlay ─────────────────────────────────────────────────────

def plot_comparison(
    results: list["FallResult"],
    labels: list[str],
    *,
    dark: bool = True,
) -> tuple[Figure, Axes]:
    """Overlay force curves for multiple FallResult scenarios."""
    if not results:
        raise ValueError("results must not be empty")
    primary = results[0]
    rest    = results[1:] if len(results) > 1 else []
    rest_labels = labels[1:] if len(labels) > 1 else []
    return plot_force_curve(
        primary,
        dark=dark,
        overlay=rest,
        overlay_labels=rest_labels,
        label=labels[0] if labels else "Scenario 1",
    )


# ── 9. Fall history / rope life ───────────────────────────────────────────────

def plot_fall_history(
    rope: "Rope",
    falls_log: list[dict],
    *,
    dark: bool = True,
) -> tuple[Figure, Axes]:
    """
    Cumulative falls vs remaining rated life.

    ``falls_log`` — list of dicts with at least ``{'falls': int}``.
    """
    fig, ax = _new_fig(dark)

    rated = rope.spec.number_of_falls
    cumulative = np.cumsum([entry.get("falls", 1) for entry in falls_log])
    remaining  = np.maximum(rated - cumulative, 0)

    ax.fill_between(
        range(len(remaining)), remaining,
        alpha=0.35, color=_GREEN, label="Remaining falls"
    )
    ax.plot(range(len(remaining)), remaining, color=_GREEN, linewidth=2.0)
    ax.axhline(0, color=_HIGHLIGHT, linewidth=1.5, linestyle="--", label="Retirement threshold")

    # Colour zones
    ax.axhspan(0, rated * 0.2, alpha=0.08, color=_HIGHLIGHT)
    ax.axhspan(rated * 0.2, rated * 0.5, alpha=0.05, color=_YELLOW)

    ax.set_xlabel("Event number", fontsize=10)
    ax.set_ylabel("Remaining rated falls", fontsize=10)
    ax.set_title(
        f"Rope Service Life — {rope.spec.name}  (rated {rated} falls)",
        fontsize=10, color=_TEXT if dark else "black"
    )
    ax.legend(fontsize=8, facecolor=_ACCENT if dark else "white",
              labelcolor=_TEXT if dark else "black")
    fig.tight_layout()
    return fig, ax
