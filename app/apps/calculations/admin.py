from decimal import Decimal

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .models import CalculationDashboard, CalculationInput, Conversie, EnergyPrice
from .calculator import EnergieCalculator, EnergieType
from apps.systemen.models import Hoofdsysteem, Subsysteem


def get_all_field_names(model):
    return [field.name for field in model._meta.fields]


@admin.register(CalculationInput)
class CalculationInputAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(CalculationInput)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "dashboard/",
                self.admin_site.admin_view(self.dashboard_view),
                name="calculationinput-dashboard",
            )
        ]
        return custom + urls

    def dashboard_view(self, request):
        calculation_inputs = CalculationInput.objects.order_by("-id")[:200]

        selected_input = None
        selected_id = request.GET.get("calculation_input_id")
        if selected_id:
            try:
                selected_input = CalculationInput.objects.get(pk=selected_id)
            except CalculationInput.DoesNotExist:
                selected_input = None

        input_rows = []
        energie_rows = []
        subsysteem_rows = []
        hoofdsysteem_rows = []
        if selected_input is not None:

            def format(value: Decimal) -> str:
                return str(value.quantize(Decimal("0.0001")))

            def format_eur(value: Decimal) -> str:
                if isinstance(value, int):
                    value = Decimal(value)
                return str(value.quantize(Decimal("0.01")))

            input_rows = [
                {
                    "field": "aantal_woningen",
                    "value": str(selected_input.aantal_woningen),
                },
                {
                    "field": "gasverbruik_vve_totaal",
                    "value": format(selected_input.gasverbruik_vve_totaal),
                },
                {
                    "field": "tapwater_op_gas",
                    "value": "true" if selected_input.tapwater_op_gas else "false",
                },
                {
                    "field": "koken_op_gas",
                    "value": "true" if selected_input.koken_op_gas else "false",
                },
                {
                    "field": "bruto_vloeroppervlak",
                    "value": format(selected_input.bruto_vloeroppervlak),
                },
            ]

            calculator = EnergieCalculator()
            energie = calculator.calculate(selected_input)
            for result in energie.results:
                energie_rows.append(
                    {
                        "scenario": result.scenario,
                        "type": result.energie_type,
                        "vermogen_woning": format(result.vermogen_warmte_kw_per_woning),
                        "vermogen_vve": format(result.vermogen_warmte_kw_per_vve),
                        "gas": format(
                            result.gas_m3_per_year,
                        ),
                        "cap_kwh": format(
                            result.capaciteit_warmte_kwh_per_year_per_woning,
                        ),
                        "cap_gj": format(
                            result.capaciteit_warmte_gj_per_year_per_woning,
                        ),
                    }
                )

            scenario_order = {"laag": 0, "midden": 1, "hoog": 2}

            for subsysteem in Subsysteem.objects.order_by("naam"):
                method = subsysteem.calculation_method
                if not method:
                    continue

                subsysteem_calculations = subsysteem.calculate(
                    energie_calculation=energie,
                    calculation_input=selected_input,
                )
                for result in subsysteem_calculations.results:
                    subsysteem_rows.append(
                        {
                            "subsysteem_id": subsysteem.id,
                            "naam": subsysteem.naam,
                            "scenario": result.scenario,
                            "method": result.method or method,
                            "afschrijving": format_eur(
                                result.berekening.afschrijving_eur_per_woning_per_jaar
                            ),
                            "onderhoud": format_eur(
                                result.berekening.onderhoud_eur_per_woning_per_jaar
                            ),
                        }
                    )
            for hoofdsysteem in Hoofdsysteem.objects.order_by("id"):
                full = hoofdsysteem.calculate(energie_calculation=energie)
                for result in full.results:
                    by_type = result.by_type
                    hoofdsysteem_rows.append(
                        {
                            "hoofdsysteem_id": hoofdsysteem.id,
                            "naam": hoofdsysteem.naam,
                            "scenario": result.scenario,
                            "cap_tap_gj": format(
                                by_type[
                                    EnergieType.TAP
                                ].capaciteit_warmte_gj_per_year_per_woning
                            ),
                            "cap_cv_gj": format(
                                by_type[
                                    EnergieType.CV
                                ].capaciteit_warmte_gj_per_year_per_woning
                            ),
                            "cap_gkw_gj": format(
                                by_type[
                                    EnergieType.GKW
                                ].capaciteit_warmte_gj_per_year_per_woning
                            ),
                            "elek_tap_gj": format(
                                result.elektriciteit_tap_gj_per_year_per_woning
                            ),
                            "elek_cv_gj": format(
                                result.elektriciteit_cv_gj_per_year_per_woning
                            ),
                            "elek_gkw_gj": format(
                                result.elektriciteit_gkw_gj_per_year_per_woning
                            ),
                            "prijs_tap": format_eur(result.prijs_tap_eur_per_gj),
                            "prijs_cv": format_eur(result.prijs_cv_eur_per_gj),
                            "prijs_gkw": format_eur(result.prijs_gkw_eur_per_gj),
                            "kosten_tap": format_eur(
                                result.energiekosten_tap_eur_per_woning_per_jaar
                            ),
                            "kosten_cv": format_eur(
                                result.energiekosten_cv_eur_per_woning_per_jaar
                            ),
                            "kosten_gkw": format_eur(
                                result.energiekosten_gkw_eur_per_woning_per_jaar
                            ),
                            "kosten_totaal": format_eur(
                                result.energiekosten_totaal_eur_per_woning_per_jaar
                            ),
                            "cap_totaal_gj": format(
                                result.capaciteit_warmte_gj_per_year_per_woning_total
                            ),
                        }
                    )

            hoofdsysteem_rows.sort(
                key=lambda row: (
                    scenario_order.get(row.get("scenario"), 99),
                    row.get("hoofdsysteem_id", 0),
                )
            )

        context = {
            **self.admin_site.each_context(request),
            "calculation_inputs": calculation_inputs,
            "selected_input": selected_input,
            "selected_id": (
                int(selected_id) if selected_id and selected_id.isdigit() else None
            ),
            "input_rows": input_rows,
            "energie_rows": energie_rows,
            "subsysteem_rows": subsysteem_rows,
            "hoofdsysteem_rows": hoofdsysteem_rows,
            "title": "Berekeningen",
        }
        return TemplateResponse(
            request,
            "admin/calculation_inputs/calculationinput/dashboard.html",
            context,
        )


@admin.register(CalculationDashboard)
class CalculationDashboardAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse("admin:calculationinput-dashboard"))


@admin.register(Conversie)
class ConversieAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Conversie)


@admin.register(EnergyPrice)
class EnergyPriceAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(EnergyPrice)
