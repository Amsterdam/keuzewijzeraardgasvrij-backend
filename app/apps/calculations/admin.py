from decimal import Decimal

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .models import CalculationDashboard, Conversie, EnergiePrijs, GebruikersInvoer
from .calculator import (
    EnergieCalculator,
    EnergieType,
    Eliminatie,
    StadsverwarmingCalculator,
    WarmtenetCalculator,
)
from apps.systemen.models import Hoofdsysteem, Subsysteem


def get_all_field_names(model):
    return [field.name for field in model._meta.fields]


@admin.register(GebruikersInvoer)
class GebruikersInvoerAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(GebruikersInvoer)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "dashboard/",
                self.admin_site.admin_view(self.dashboard_view),
                name="gebruikersinvoer-dashboard",
            )
        ]
        return custom + urls

    def dashboard_view(self, request):
        gebruikers_invoer = GebruikersInvoer.objects.order_by("-id")[:200]

        selected_input = None
        selected_id = request.GET.get("calculation_input_id")
        if selected_id:
            try:
                selected_input = GebruikersInvoer.objects.get(pk=selected_id)
            except GebruikersInvoer.DoesNotExist:
                selected_input = None

        input_rows = []
        energie_rows = []
        subsysteem_rows = []
        hoofdsysteem_rows = []
        hoofdsysteem_tco_sum_rows = []
        stadsverwarming_rows = []
        stadsverwarming_totals_rows = []
        eliminatie_rows = []
        warmteprogramma_row = None
        if selected_input is not None:

            def format(value: Decimal) -> str:
                return str(value.quantize(Decimal("0.0001")))

            def format_eur(value: Decimal) -> str:
                if isinstance(value, int):
                    value = Decimal(value)
                return str(value.quantize(Decimal("0.01")))

            input_rows = [
                {
                    "field": "bouwjaar",
                    "value": str(selected_input.bouwjaar),
                },
                {
                    "field": "buurtcode",
                    "value": (
                        ""
                        if selected_input.buurtcode is None
                        else str(selected_input.buurtcode)
                    ),
                },
                {
                    "field": "jaar_vervangen",
                    "value": (
                        ""
                        if selected_input.jaar_vervangen is None
                        else str(selected_input.jaar_vervangen)
                    ),
                },
                {
                    "field": "aantal_woningen",
                    "value": str(selected_input.aantal_woningen),
                },
                {
                    "field": "bruto_vloeroppervlak",
                    "value": format(selected_input.bruto_vloeroppervlak),
                },
                {
                    "field": "dubbel_glas",
                    "value": "true" if selected_input.dubbel_glas else "false",
                },
                {
                    "field": "wtw_aanwezig",
                    "value": "true" if selected_input.wtw_aanwezig else "false",
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
                    "field": "gasverbruik_vve_totaal",
                    "value": format(selected_input.gasverbruik_vve_totaal),
                },
            ]

            warmteprogramma_row = {
                "categorie": "",
                "warmtenet_start": "",
                "warmtenet_stop": "",
                "warmtenet_mogelijk": "false",
            }

            warmtenet_result = WarmtenetCalculator().calculate(selected_input)
            warmteprogramma_row["categorie"] = warmtenet_result.categorie
            warmteprogramma_row["warmtenet_start"] = (
                ""
                if warmtenet_result.warmtenet_start is None
                else str(warmtenet_result.warmtenet_start)
            )
            warmteprogramma_row["warmtenet_stop"] = (
                ""
                if warmtenet_result.warmtenet_stop is None
                else str(warmtenet_result.warmtenet_stop)
            )
            warmteprogramma_row["warmtenet_mogelijk"] = (
                "true" if warmtenet_result.warmtenet_mogelijk else "false"
            )

            calculator = EnergieCalculator()
            energie = calculator.calculate(selected_input)
            for result in energie.results:
                energie_rows.append(
                    {
                        "scenario": result.scenario,
                        "type": result.energie_type,
                        "woning_type": (
                            "" if result.woning_type is None else result.woning_type
                        ),
                        "vermogen_cv": (
                            ""
                            if result.vermogen_cv is None
                            else format(result.vermogen_cv)
                        ),
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

            stadsverwarming_result = StadsverwarmingCalculator().calculate(
                energie_calculation=energie,
                aantal_woningen=selected_input.aantal_woningen,
            )

            stadsverwarming_totals_rows = []
            for scenario_key in ("laag", "midden", "hoog"):
                totals = stadsverwarming_result.kosten_totals_by_scenario.get(
                    scenario_key
                )
                if totals is None:
                    continue
                stadsverwarming_totals_rows.append(
                    {
                        "scenario": scenario_key,
                        "stadsverwarming_kosten_particulier_warmte": format_eur(
                            totals.stadsverwarming_kosten_particulier_warmte
                        ),
                        "stadsverwarming_kosten_particulier_koude": format_eur(
                            totals.stadsverwarming_kosten_particulier_koude
                        ),
                        "stadsverwarming_kosten_zakelijk_warmte": format_eur(
                            totals.stadsverwarming_kosten_zakelijk_warmte
                        ),
                        "stadsverwarming_kosten_zakelijk_warmte_koude": format_eur(
                            totals.stadsverwarming_kosten_zakelijk_warmte_koude
                        ),
                    }
                )

            stadsverwarming_rows = []
            for r in stadsverwarming_result.results:
                stadsverwarming_rows.append(
                    {
                        "scenario": r.scenario,
                        "klanttype": str(r.klanttype),
                        "producttype": str(r.producttype),
                        "kostetype": r.kostetype,
                        "eenheid": str(r.eenheid),
                        "interval": r.interval,
                        "vermogen_berekenen_op": (
                            ""
                            if r.vermogen_berekenen_op is None
                            else str(r.vermogen_berekenen_op)
                        ),
                        "kw_min": "" if r.kw_min is None else str(r.kw_min),
                        "kw_max": "∞" if r.kw_max is None else str(r.kw_max),
                        "waarde_1": str(r.waarde_1),
                        "waarde_2": str(r.waarde_2),
                        "vermogen_cv_vve": format(r.vermogen_cv_vve),
                        "vermogen_tap_vve": format(r.vermogen_tap_vve),
                        "vermogen_koude_vve": format(r.vermogen_koude_vve),
                        "te_berekenen_vermogen": (
                            ""
                            if r.te_berekenen_vermogen is None
                            else format(r.te_berekenen_vermogen)
                        ),
                        "is_tussen_mix_max": "true" if r.is_tussen_min_max else "false",
                        "is_boven_max": "true" if r.is_boven_max else "false",
                        "waarde_vast": format_eur(r.waarde_vast),
                        "waarde_variabel": format_eur(r.waarde_variabel),
                        "waarde_geclassificeerd": format_eur(r.waarde_geclassificeerd),
                        "factor_naar_jaar": str(r.factor_naar_jaar),
                        "factor_collectief": str(r.factor_collectief),
                        "stadsverwarming_kosten_totaal": format_eur(
                            r.stadsverwarming_kosten_totaal
                        ),
                        "stadsverwarming_kosten_particulier_warmte": format_eur(
                            r.stadsverwarming_kosten_particulier_warmte
                        ),
                        "stadsverwarming_kosten_particulier_koude": format_eur(
                            r.stadsverwarming_kosten_particulier_koude
                        ),
                        "stadsverwarming_kosten_zakelijk_warmte": format_eur(
                            r.stadsverwarming_kosten_zakelijk_warmte
                        ),
                        "stadsverwarming_kosten_zakelijk_warmte_koude": format_eur(
                            r.stadsverwarming_kosten_zakelijk_warmte_koude
                        ),
                    }
                )

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
                            "tco": format_eur(result.berekening.tco),
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
                            "tco": format_eur(result.tco),
                            "cap_totaal_gj": format(
                                result.capaciteit_warmte_gj_per_year_per_woning_total
                            ),
                        }
                    )

            hoofdsysteem_tco_sum_rows = []
            for hoofdsysteem in Hoofdsysteem.objects.order_by("id").prefetch_related(
                "subsystemen"
            ):
                full = hoofdsysteem.calculate(energie_calculation=energie)
                subsystems = list(hoofdsysteem.subsystemen.all())
                subsysteem_results_by_id = {}
                for subsysteem in subsystems:
                    if not subsysteem.calculation_method:
                        continue
                    subsysteem_results_by_id[subsysteem.id] = subsysteem.calculate(
                        energie_calculation=energie,
                        calculation_input=selected_input,
                    )

                def _subsystemen_tco_for_scenario(scenario_key: str) -> Decimal:
                    subsysteem_total = Decimal("0")
                    for subsysteem in subsystems:
                        subs_full = subsysteem_results_by_id.get(subsysteem.id)
                        if subs_full is None:
                            continue
                        subsysteem_total += subs_full.by_scenario[
                            scenario_key
                        ].berekening.tco
                    return subsysteem_total

                def _hoofdsysteem_tco_for_scenario(scenario_key: str) -> Decimal:
                    return full.by_scenario[scenario_key].tco

                def _totaal_tco_for_scenario(scenario_key: str) -> Decimal:
                    return _hoofdsysteem_tco_for_scenario(
                        scenario_key
                    ) + _subsystemen_tco_for_scenario(scenario_key)

                hoofdsysteem_tco_sum_rows.append(
                    {
                        "hoofdsysteem_id": hoofdsysteem.id,
                        "naam": hoofdsysteem.naam,
                        "subsystemen": ", ".join(
                            s.naam for s in subsystems if s.calculation_method
                        ),
                        "hoofdsysteem_tco_laag": format_eur(
                            _hoofdsysteem_tco_for_scenario("laag")
                        ),
                        "subsystemen_tco_laag": format_eur(
                            _subsystemen_tco_for_scenario("laag")
                        ),
                        "tco_laag": format_eur(_totaal_tco_for_scenario("laag")),
                        "hoofdsysteem_tco_midden": format_eur(
                            _hoofdsysteem_tco_for_scenario("midden")
                        ),
                        "subsystemen_tco_midden": format_eur(
                            _subsystemen_tco_for_scenario("midden")
                        ),
                        "tco_midden": format_eur(_totaal_tco_for_scenario("midden")),
                        "hoofdsysteem_tco_hoog": format_eur(
                            _hoofdsysteem_tco_for_scenario("hoog")
                        ),
                        "subsystemen_tco_hoog": format_eur(
                            _subsystemen_tco_for_scenario("hoog")
                        ),
                        "tco_hoog": format_eur(_totaal_tco_for_scenario("hoog")),
                    }
                )

            hoofdsysteem_tco_sum_rows.sort(
                key=lambda row: row.get("hoofdsysteem_id", 0)
            )

            hoofdsysteem_rows.sort(
                key=lambda row: (
                    scenario_order.get(row.get("scenario"), 99),
                    row.get("hoofdsysteem_id", 0),
                )
            )

            eliminatie_rows = []
            eliminatie = Eliminatie()
            for hoofdsysteem in Hoofdsysteem.objects.order_by("id"):
                try:
                    result = eliminatie.calculate(selected_input, hoofdsysteem.naam)
                    is_mogelijk = bool(result.get("is_mogelijk"))
                    redenen = result.get("redenen")
                    if not isinstance(redenen, list):
                        redenen = []
                except Exception as exc:  # keep dashboard robust
                    is_mogelijk = False
                    redenen = [str(exc)]

                eliminatie_rows.append(
                    {
                        "hoofdsysteem": hoofdsysteem.naam,
                        "is_mogelijk": "true" if is_mogelijk else "false",
                        "redenen": redenen,
                    }
                )

        context = {
            **self.admin_site.each_context(request),
            "gebruikers_invoer": gebruikers_invoer,
            "selected_input": selected_input,
            "selected_id": (
                int(selected_id) if selected_id and selected_id.isdigit() else None
            ),
            "input_rows": input_rows,
            "energie_rows": energie_rows,
            "subsysteem_rows": subsysteem_rows,
            "hoofdsysteem_rows": hoofdsysteem_rows,
            "hoofdsysteem_tco_sum_rows": hoofdsysteem_tco_sum_rows,
            "stadsverwarming_rows": stadsverwarming_rows,
            "stadsverwarming_totals_rows": stadsverwarming_totals_rows,
            "eliminatie_rows": eliminatie_rows,
            "warmteprogramma_row": warmteprogramma_row,
            "title": "Berekeningen",
        }
        return TemplateResponse(
            request,
            "admin/dashboard.html",
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
        return HttpResponseRedirect(reverse("admin:gebruikersinvoer-dashboard"))


@admin.register(Conversie)
class ConversieAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Conversie)


@admin.register(EnergiePrijs)
class EnergiePrijsAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(EnergiePrijs)
