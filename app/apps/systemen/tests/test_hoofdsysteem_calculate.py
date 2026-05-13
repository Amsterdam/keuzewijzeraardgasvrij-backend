from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import EnergieType
from apps.calculations.calculator import EnergieCalculator
from apps.calculations.models import EnergiePrijs, GebruikersInvoer
from apps.kengetallen.models import Hoofdkengetal, ScenarioKeuze
from apps.systemen.models import Hoofdsysteem
from apps.systemen.models import Subsysteem


def _calculation_input(**overrides: object) -> GebruikersInvoer:
    defaults: dict[str, object] = {
        "bouwjaar": 1990,
        "bruto_vloeroppervlak": Decimal("1234.5"),
        "aantal_woningen": 200,
        "mechanische_ventilatie_aanwezig": True,
        "vloerverwarming_aanwezig": False,
        "inpandige_berging_aanwezig": True,
        "ruimte_op_het_dak_aanwezig": True,
        "type_dak": "plat_dak",
        "tapwater_op_gas": True,
        "koken_op_gas": False,
        "gasverbruik_vve_totaal": Decimal("1334.6"),
        "elektriciteitsverbruik_per_woning": Decimal("1000"),
        "elektriciteitsverbruik_vve_totaal": Decimal("10000"),
        "gecontracteerd_vermogen": Decimal("50"),
        "huidige_warmtesysteem": "cv_ketel",
        "volledig_gasloos": False,
        "wens_tot_koelen": False,
    }
    defaults.update(overrides)
    return GebruikersInvoer.objects.create(**defaults)


class HoofdsysteemCalculateTest(TestCase):
    fixtures = ["fixtures"]

    def test_calculate_returns_capacity_totals_from_energy_rows(self):
        # Use a hoofdsysteem from fixtures; the current calculation is energy-based only.
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Individuele Luchtwarmtepomp op Ventilatie"
        )
        calc_input = _calculation_input()

        energie = EnergieCalculator().calculate(calc_input)

        full = hoofdsysteem.calculate(energie_calculation=energie)

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            scenario_key = str(scenario)
            row = full.by_scenario[scenario_key]

            by_type = full.energy.by_scenario[scenario_key]
            hoofdkengetal = Hoofdkengetal.objects.get(
                hoofdsysteem=hoofdsysteem,
                scenario=scenario_key,
            )

            energieprijs_eur_per_gj = EnergiePrijs.objects.get(
                naam="Elektriciteit"
            ).prijs_eur_per_gj
            expected_kwh = (
                by_type[EnergieType.TAP].capaciteit_warmte_kwh_per_year_per_woning
                + by_type[EnergieType.CV].capaciteit_warmte_kwh_per_year_per_woning
                + by_type[EnergieType.GKW].capaciteit_warmte_kwh_per_year_per_woning
            )
            expected_gj = (
                by_type[EnergieType.TAP].capaciteit_warmte_gj_per_year_per_woning
                + by_type[EnergieType.CV].capaciteit_warmte_gj_per_year_per_woning
                + by_type[EnergieType.GKW].capaciteit_warmte_gj_per_year_per_woning
            )

            expected_elec_tap_gj = (
                by_type[EnergieType.TAP].capaciteit_warmte_gj_per_year_per_woning
                / hoofdkengetal.cop_tap
                if hoofdkengetal.cop_tap
                else Decimal("0")
            )
            expected_elec_cv_gj = (
                by_type[EnergieType.CV].capaciteit_warmte_gj_per_year_per_woning
                / hoofdkengetal.cop_cv
                if hoofdkengetal.cop_cv
                else Decimal("0")
            )
            expected_elec_gkw_gj = (
                by_type[EnergieType.GKW].capaciteit_warmte_gj_per_year_per_woning
                / hoofdkengetal.cop_gkw
                if hoofdkengetal.cop_gkw
                else Decimal("0")
            )

            expected_elektrisch_vermogen = (
                by_type[EnergieType.TAP].vermogen_warmte_kw_per_vve
                / hoofdkengetal.cop_tap
            ) + (
                by_type[EnergieType.CV].vermogen_warmte_kw_per_vve
                / hoofdkengetal.cop_cv
            )

            expected_cost_tap = expected_elec_tap_gj * energieprijs_eur_per_gj
            expected_cost_cv = expected_elec_cv_gj * energieprijs_eur_per_gj
            expected_cost_gkw = expected_elec_gkw_gj * energieprijs_eur_per_gj
            expected_cost_total = (
                expected_cost_tap + expected_cost_cv + expected_cost_gkw
            )

            self.assertEqual(
                row.capaciteit_warmte_kwh_per_year_per_woning_total,
                expected_kwh,
            )
            self.assertEqual(
                row.capaciteit_warmte_gj_per_year_per_woning_total,
                expected_gj,
            )

            self.assertEqual(
                row.elektriciteit_tap_gj_per_year_per_woning,
                expected_elec_tap_gj,
            )
            self.assertEqual(
                row.elektriciteit_cv_gj_per_year_per_woning,
                expected_elec_cv_gj,
            )
            self.assertEqual(
                row.elektriciteit_gkw_gj_per_year_per_woning,
                expected_elec_gkw_gj,
            )

            self.assertEqual(row.prijs_tap_eur_per_gj, energieprijs_eur_per_gj)
            self.assertEqual(row.prijs_cv_eur_per_gj, energieprijs_eur_per_gj)
            self.assertEqual(row.prijs_gkw_eur_per_gj, energieprijs_eur_per_gj)

            self.assertEqual(row.elektrisch_vermogen, expected_elektrisch_vermogen)

            self.assertEqual(
                row.energiekosten_tap_eur_per_woning_per_jaar,
                expected_cost_tap,
            )
            self.assertEqual(
                row.energiekosten_cv_eur_per_woning_per_jaar,
                expected_cost_cv,
            )
            self.assertEqual(
                row.energiekosten_gkw_eur_per_woning_per_jaar,
                expected_cost_gkw,
            )
            self.assertEqual(
                row.energiekosten_totaal_eur_per_woning_per_jaar,
                expected_cost_total,
            )

    def test_calculate_sets_elektrisch_vermogen_to_zero_for_warmtelevering(self):
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Particulier Externe warmtelevering"
        )
        calc_input = _calculation_input()

        energie = EnergieCalculator().calculate(calc_input)
        full = hoofdsysteem.calculate(energie_calculation=energie)

        scenario_key = str(ScenarioKeuze.MIDDEN)
        row = full.by_scenario[scenario_key]

        self.assertEqual(row.elektrisch_vermogen, Decimal("0"))

    def test_calculate_uses_zakelijk_stadswarmte_met_koude_prices(self):
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Individuele Luchtwarmtepomp op Ventilatie"
        )
        hoofdsysteem.subsystemen.add(
            Subsysteem.objects.create(
                naam="Zakelijk Stadswarmte + koude",
                type="kengetal",
            )
        )

        calc_input = _calculation_input()
        energie = EnergieCalculator().calculate(calc_input)
        full = hoofdsysteem.calculate(energie_calculation=energie)

        prijs_tap = EnergiePrijs.objects.get(
            naam="SV zakelijk tap (warmte + Koude)"
        ).prijs_eur_per_gj
        prijs_cv = EnergiePrijs.objects.get(
            naam="SV zakelijk CV (warmte + Koude)"
        ).prijs_eur_per_gj
        prijs_gkw = EnergiePrijs.objects.get(
            naam="SV zakelijk GKW (warmte + Koude)"
        ).prijs_eur_per_gj

        scenario_key = str(ScenarioKeuze.MIDDEN)
        row = full.by_scenario[scenario_key]

        self.assertEqual(row.prijs_tap_eur_per_gj, prijs_tap)
        self.assertEqual(row.prijs_cv_eur_per_gj, prijs_cv)
        self.assertEqual(row.prijs_gkw_eur_per_gj, prijs_gkw)

        self.assertEqual(
            row.energiekosten_tap_eur_per_woning_per_jaar,
            row.elektriciteit_tap_gj_per_year_per_woning * prijs_tap,
        )
        self.assertEqual(
            row.energiekosten_cv_eur_per_woning_per_jaar,
            row.elektriciteit_cv_gj_per_year_per_woning * prijs_cv,
        )
        self.assertEqual(
            row.energiekosten_gkw_eur_per_woning_per_jaar,
            row.elektriciteit_gkw_gj_per_year_per_woning * prijs_gkw,
        )

    def test_calculate_particulier_stadswarmte_has_zero_gkw_price(self):
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Individuele Luchtwarmtepomp op Ventilatie"
        )
        hoofdsysteem.subsystemen.add(
            Subsysteem.objects.create(
                naam="Particulier Stadswarmte",
                type="kengetal",
            )
        )

        calc_input = _calculation_input()
        energie = EnergieCalculator().calculate(calc_input)
        full = hoofdsysteem.calculate(energie_calculation=energie)

        scenario_key = str(ScenarioKeuze.MIDDEN)
        row = full.by_scenario[scenario_key]

        self.assertEqual(
            row.prijs_gkw_eur_per_gj,
            Decimal("0"),
        )
        self.assertEqual(row.energiekosten_gkw_eur_per_woning_per_jaar, Decimal("0"))
