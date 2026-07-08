"""ropesim.tui.app -- Textual application.

Three screens:
  * Simulate -- rope + fall parameters -> results card with sparkline
  * Ropes    -- database browser (sortable table + spec detail)
  * Risk     -- v3 fall probability and rope-life projection

Requires textual (``pip install "ropesim[tui]"``).
"""

from __future__ import annotations

import sys


def _require_textual():
    try:
        import textual  # noqa: F401
    except ImportError:
        print(
            "The ropesim TUI needs Textual:\n\n"
            '    pip install "ropesim[tui]"\n',
            file=sys.stderr,
        )
        raise SystemExit(1)


_require_textual()

from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Horizontal, Vertical, VerticalScroll  # noqa: E402
from textual.screen import Screen  # noqa: E402
from textual.widgets import (  # noqa: E402
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from ropesim.rope import Rope, RopeDatabase  # noqa: E402

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], width: int = 48) -> str:
    """Downsample a series into a unicode sparkline."""
    if not values:
        return ""
    step = max(len(values) // width, 1)
    samples = [max(values[i : i + step]) for i in range(0, len(values), step)]
    peak = max(max(samples), 1e-9)
    return "".join(SPARK_CHARS[min(int(v / peak * 7.999), 7)] for v in samples)


def verdict(peak_kn: float) -> tuple[str, str]:
    if peak_kn > 10.0:
        return "DANGER", "red"
    if peak_kn > 8.0:
        return "CAUTION", "yellow"
    return "SAFE", "green"


# ── Simulate screen ──────────────────────────────────────────────────────────

class SimulateScreen(Screen):
    """Set up and run a single fall."""

    def compose(self) -> ComposeResult:
        db = RopeDatabase()
        names = [(r.name, r.name) for r in db.load()]
        yield Header(show_clock=False)
        with Horizontal():
            with Vertical(id="sim-form"):
                yield Label("[b]rope[/b]")
                yield Select(names, id="rope", allow_blank=False)
                yield Label("climber mass (kg)")
                yield Input("80", id="mass", type="number")
                yield Label("fall distance (m)")
                yield Input("4.0", id="fall", type="number")
                yield Label("rope out (m)")
                yield Input("8.0", id="rope_out", type="number")
                yield Label("belay device")
                yield Select(
                    [(d, d) for d in (
                        "atc", "grigri", "tube", "reverso", "reverso_guide",
                        "megajul", "giga_jul", "click_up", "i_device", "sum",
                        "munter",
                    )],
                    id="device",
                    value="atc",
                    allow_blank=False,
                )
                yield Button("run simulation  ⏎", id="run", variant="success")
            yield VerticalScroll(Static(id="sim-result"), id="sim-result-holder")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self.run_simulation()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self.run_simulation()

    def run_simulation(self) -> None:
        from ropesim.fall import BelayDevice, Fall, FallConditions

        out = self.query_one("#sim-result", Static)
        try:
            rope = Rope.from_db(str(self.query_one("#rope", Select).value))
            mass = float(self.query_one("#mass", Input).value or 80)
            fall_dist = float(self.query_one("#fall", Input).value or 4)
            rope_out = float(self.query_one("#rope_out", Input).value or 8)
            device = BelayDevice(str(self.query_one("#device", Select).value))

            fall = Fall(
                rope=rope,
                conditions=FallConditions(
                    climber_mass_kg=mass,
                    fall_distance_m=fall_dist,
                    rope_out_m=rope_out,
                    belay_device=device,
                ),
            )
            result = fall.simulate()
            curve = list(fall.force_curve_numpy())
            word, color = verdict(result.peak_force_kn)

            out.update(
                f"[b]{rope.spec.name}[/b]\n\n"
                f"  fall factor     [b]{fall.fall_factor:.2f}[/b]\n"
                f"  peak force      [b]{result.peak_force_kn:.2f} kN[/b]"
                f"  ({result.peak_force_kn * 224.809:.0f} lbf)\n"
                f"  elongation      {result.elongation_m:.2f} m\n"
                f"  deceleration    {result.deceleration_g:.1f} g\n\n"
                f"  verdict         [{color} bold]{word}[/]\n\n"
                f"[dim]force curve (kN over time)[/dim]\n"
                f"[green]{sparkline(curve)}[/green]\n"
            )
        except Exception as exc:  # noqa: BLE001 — show, don't crash the TUI
            out.update(f"[red]error:[/red] {exc}")


# ── Ropes screen ─────────────────────────────────────────────────────────────

class RopesScreen(Screen):
    """Database browser."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            yield DataTable(id="rope-table", cursor_type="row")
            yield VerticalScroll(Static(id="rope-detail"), id="rope-detail-holder")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#rope-table", DataTable)
        table.add_columns("name", "⌀ mm", "g/m", "IF kN", "falls", "dry")
        for rope in RopeDatabase().load():
            s = rope
            table.add_row(
                s.name,
                f"{s.diameter_mm:.1f}",
                f"{s.weight_gpm:.0f}",
                f"{s.impact_force_kn:.1f}",
                str(s.number_of_falls),
                "✓" if s.dry_treated else "—",
                key=s.name,
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is None:
            return
        try:
            rope = Rope.from_db(str(event.row_key.value))
        except KeyError:
            return
        s = rope.spec
        violations = rope.validate_standard_compliance()
        compliance = (
            "[green]EN 892 compliant[/green]"
            if not violations
            else "[red]" + "; ".join(violations) + "[/red]"
        )
        self.query_one("#rope-detail", Static).update(
            f"[b]{s.name}[/b]\n"
            f"[dim]{s.manufacturer} · {s.rope_type}[/dim]\n\n"
            f"  diameter         {s.diameter_mm} mm\n"
            f"  weight           {s.weight_gpm} g/m\n"
            f"  impact force     {s.impact_force_kn} kN\n"
            f"  UIAA falls       {s.number_of_falls}\n"
            f"  static elong.    {s.static_elongation_pct}%\n"
            f"  dynamic elong.   {s.dynamic_elongation_pct}%\n"
            f"  sheath           {s.sheath_percentage}%\n"
            f"  length           {s.length_m} m\n"
            f"  dry treated      {'yes' if s.dry_treated else 'no'}\n\n"
            f"  stiffness (calc) {rope.effective_stiffness():.1f} kN\n"
            f"  {compliance}\n"
        )


# ── Risk screen (v3) ─────────────────────────────────────────────────────────

class RiskScreen(Screen):
    """Fall probability + rope-life projection."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            with Vertical(id="risk-form"):
                yield Label("route grade (YDS numeric, 5.12a = 12.1)")
                yield Input("12.1", id="route", type="number")
                yield Label("your redpoint grade")
                yield Input("11.4", id="climber", type="number")
                yield Label("style")
                yield Select(
                    [("sport", "sport"), ("trad", "trad"), ("boulder", "boulder")],
                    id="style",
                    value="sport",
                    allow_blank=False,
                )
                yield Label("attempts today")
                yield Input("6", id="attempts", type="integer")
                yield Label("expected peak force (kN)")
                yield Input("6.5", id="peak", type="number")
                yield Label("rope rated falls")
                yield Input("8", id="rated", type="integer")
                yield Label("falls already taken")
                yield Input("0", id="taken", type="integer")
                yield Button("project risk  ⏎", id="project", variant="success")
            yield VerticalScroll(Static(id="risk-result"), id="risk-result-holder")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "project":
            self.project()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self.project()

    def project(self) -> None:
        from ropesim.physics_v3 import cumulative_risk, fall_probability

        out = self.query_one("#risk-result", Static)
        try:
            route = float(self.query_one("#route", Input).value or 12.1)
            climber = float(self.query_one("#climber", Input).value or 11.4)
            style = str(self.query_one("#style", Select).value)
            attempts = int(self.query_one("#attempts", Input).value or 6)
            peak = float(self.query_one("#peak", Input).value or 6.5)
            rated = int(self.query_one("#rated", Input).value or 8)
            taken = int(self.query_one("#taken", Input).value or 0)

            p = fall_probability(route, climber, style)
            risk = cumulative_risk(p, attempts, peak, rated, taken)
            bar_n = int(min(risk.rope_life_consumed_pct, 100.0) / 100 * 30)
            bar = "█" * bar_n + "░" * (30 - bar_n)
            color = (
                "red" if risk.rope_life_consumed_pct > 80
                else "yellow" if risk.rope_life_consumed_pct > 50
                else "green"
            )

            out.update(
                f"[b]risk projection[/b]\n\n"
                f"  p(fall) per attempt      [b]{p:.0%}[/b]\n"
                f"  expected falls           {risk.expected_falls:.1f}\n"
                f"  expected total force     {risk.expected_total_force_kn:.0f} kN\n"
                f"  sessions to retirement   {risk.retirement_climbs_remaining}\n\n"
                f"  rope life consumed\n"
                f"  [{color}]{bar}[/] {risk.rope_life_consumed_pct:.0f}%\n\n"
                f"[dim]population model — plan rope life with it,\n"
                f"never skip a clip because of it.[/dim]"
            )
        except Exception as exc:  # noqa: BLE001
            out.update(f"[red]error:[/red] {exc}")


# ── App ──────────────────────────────────────────────────────────────────────

class RopesimTui(App):
    """ropesim terminal UI."""

    TITLE = "ropesim"
    SUB_TITLE = "climbing rope physics"
    CSS = """
    #sim-form, #risk-form { width: 44; padding: 1 2; }
    #sim-result-holder, #rope-detail-holder, #risk-result-holder {
        padding: 1 2;
    }
    #rope-table { width: 62%; }
    Input { margin-bottom: 1; }
    Select { margin-bottom: 1; }
    Button { margin-top: 1; }
    Label { color: $text-muted; }
    """

    BINDINGS = [
        Binding("s", "switch('simulate')", "simulate"),
        Binding("r", "switch('ropes')", "ropes"),
        Binding("k", "switch('risk')", "risk"),
        Binding("d", "toggle_dark", "dark mode"),
        Binding("q", "quit", "quit"),
    ]

    SCREENS = {
        "simulate": SimulateScreen,
        "ropes": RopesScreen,
        "risk": RiskScreen,
    }

    def on_mount(self) -> None:
        self.push_screen("simulate")

    def action_switch(self, screen: str) -> None:
        self.switch_screen(screen)


def main() -> int:
    RopesimTui().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
