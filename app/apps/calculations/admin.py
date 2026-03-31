from decimal import Decimal

from django.contrib import admin
from django.utils.html import format_html, format_html_join

from .models import CalculationInput, Conversie
from .calculator import EnergieCalculator, EnergieType
from apps.kengetallen.models import ScenarioKeuze


def get_all_field_names(model):
    return [field.name for field in model._meta.fields]


@admin.register(CalculationInput)
class CalculationInputAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(CalculationInput)

    readonly_fields = ("calculation_results",)

    def calculation_results(self, obj: CalculationInput | None) -> str:
        """Render a small table with `EnergieCalculator.calculate()` results.

        Shown on the admin change (details) page for a single CalculationInput.
        """

        if obj is None:
            return "-"

        def fmt(value: Decimal) -> str:
            return str(value.quantize(Decimal("0.0001")))

        calculator = EnergieCalculator()
        rows: list[tuple[str, str, str, str, str, str, str]] = []

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            for energie_type in (EnergieType.TAP, EnergieType.CV, EnergieType.GKW):
                try:
                    result = calculator.calculate(energie_type, scenario, obj)
                    rows.append(
                        (
                            result["Scenario"],
                            result["Type"],
                            fmt(result["Vermogen warmte [kW/woning]"]),
                            fmt(result["Vermogen warmte [kW/vve]"]),
                            fmt(result["Gas [m³/j]"]),
                            fmt(result["Capaciteit warmte [kWh/j/w]"]),
                            fmt(result["Capaciteit warmte [GJ/j/w]"]),
                        )
                    )
                except Exception as exc:  # admin-only display
                    rows.append(
                        (str(scenario), energie_type, f"ERROR: {exc}", "", "", "", "")
                    )

        return format_html(
            "<table>"
            "<thead><tr>"
            "<th>Scenario</th><th>Type</th>"
            "<th>Vermogen [kW/w]</th><th>Vermogen [kW/vve]</th>"
            "<th>Gas [m³/j]</th><th>Capaciteit [kWh/j/w]</th><th>Capaciteit [GJ/j/w]</th>"
            "</tr></thead>"
            "<tbody>{}</tbody>"
            "</table>",
            format_html_join(
                "",
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>",
                rows,
            ),
        )

    calculation_results.short_description = "Berekening energie"


@admin.register(Conversie)
class ConversieAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Conversie)
