from django.contrib import admin
from django.utils.html import format_html, format_html_join
from decimal import Decimal

from .models import Hoofdsysteem, Subsysteem
from apps.kengetallen.models import ScenarioKeuze


def get_all_field_names(model):
    return [field.name for field in model._meta.fields]


@admin.register(Hoofdsysteem)
class HoofdsysteemAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Hoofdsysteem) + ["toon_subsystemen"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("subsystemen")

    def toon_subsystemen(self, obj):
        return ", ".join(s.naam for s in obj.subsystemen.all())

    toon_subsystemen.short_description = "Subsystemen"


@admin.register(Subsysteem)
class SubsysteemAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Subsysteem)

    readonly_fields = ("subkengetal_berekening",)
    fields = ("naam", "type", "calculation_method", "subkengetal_berekening")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("subkengetallen")

    def subkengetal_berekening(self, obj: Subsysteem | None) -> str:
        if obj is None:
            return "-"

        def fmt_eur(value: Decimal) -> str:
            return str(value.quantize(Decimal("0.0001")))

        rows: list[tuple[str, str, str]] = []
        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            try:
                result = obj.calculate(scenario)
                rows.append(
                    (
                        str(scenario),
                        # Needs to be dynamic in the future, for now just these results exist for the 'Investering' calculation method
                        fmt_eur(result["afschrijving_eur_per_woning_per_jaar"]),
                        fmt_eur(result["onderhoud_eur_per_woning_per_jaar"]),
                    )
                )
            except Exception as exc:  # admin-only display
                rows.append((str(scenario), f"ERROR: {exc}", ""))

        return format_html(
            "<table>"
            "<thead><tr><th>Scenario</th><th>Afschrijving [€/w/j]</th><th>Onderhoud [€/w/j]</th></tr></thead>"
            "<tbody>{}</tbody>"
            "</table>",
            format_html_join(
                "",
                "<tr><td>{}</td><td>{}</td><td>{}</td></tr>",
                rows,
            ),
        )

    subkengetal_berekening.short_description = "Berekening (Subkengetal)"
