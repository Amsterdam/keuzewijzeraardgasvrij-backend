from decimal import Decimal

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .models import CalculationDashboard, CalculationInput, Conversie
from .calculator import EnergieCalculator
from apps.systemen.models import Subsysteem


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
        if selected_input is not None:

            def fmt(value: Decimal) -> str:
                return str(value.quantize(Decimal("0.0001")))

            def fmt_eur(value: Decimal) -> str:
                return str(value.quantize(Decimal("0.01")))

            input_rows = [
                {
                    "field": "aantal_woningen",
                    "value": str(selected_input.aantal_woningen),
                },
                {
                    "field": "gasverbruik_vve_totaal",
                    "value": fmt(selected_input.gasverbruik_vve_totaal),
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
                    "value": fmt(selected_input.bruto_vloeroppervlak),
                },
            ]

            calculator = EnergieCalculator()
            energie_full = calculator.calculate(selected_input)
            for result in energie_full.results:
                energie_rows.append(
                    {
                        "scenario": result.scenario,
                        "type": result.energie_type,
                        "vermogen_woning": fmt(result.vermogen_warmte_kw_per_woning),
                        "vermogen_vve": fmt(result.vermogen_warmte_kw_per_vve),
                        "gas": fmt(
                            result.gas_m3_per_year,
                        ),
                        "cap_kwh": fmt(
                            result.capaciteit_warmte_kwh_per_year_per_woning,
                        ),
                        "cap_gj": fmt(
                            result.capaciteit_warmte_gj_per_year_per_woning,
                        ),
                    }
                )
            for subsysteem in Subsysteem.objects.order_by("naam"):
                method = subsysteem.calculation_method
                if not method:
                    continue

                subsysteem_full = subsysteem.calculate(energie_calculation=energie_full)
                for result in subsysteem_full.results:
                    subsysteem_rows.append(
                        {
                            "naam": subsysteem.naam,
                            "scenario": result.scenario,
                            "method": result.method or method,
                            "afschrijving": fmt_eur(
                                result.berekening.afschrijving_eur_per_woning_per_jaar
                            ),
                            "onderhoud": fmt_eur(
                                result.berekening.onderhoud_eur_per_woning_per_jaar
                            ),
                        }
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
