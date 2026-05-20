from __future__ import annotations


from dataclasses import dataclass
from decimal import Decimal

from django.db import models

from apps.calculations.subsysteem_calculations import (
    SubsysteemCalculationMethod,
    SubsysteemFullResult,
    SubsysteemScenarioResult,
    calculate_stadsverwarming,
    calculate_gbs,
    calculate_investering,
    calculate_openbron_systeem,
    calculate_warmtepomp,
    calculate_staffel,
)


from apps.kengetallen.models import Hoofdkengetal, ScenarioKeuze
from apps.calculations.calculator import (
    EnergieCalculatorFullResult,
    EnergieCalculationResult,
    StadsverwarmingCalculator,
    EnergieType,
    EnergieTypeValue,
)
from apps.calculations.models import Conversie, EnergiePrijs, GebruikersInvoer


@dataclass(frozen=True, slots=True)
class HoofdsysteemScenarioResult:
    scenario: str
    by_type: dict[EnergieTypeValue, EnergieCalculationResult]
    capaciteit_warmte_kwh_per_year_per_woning_total: Decimal
    capaciteit_warmte_gj_per_year_per_woning_total: Decimal

    elektriciteit_tap_gj_per_year_per_woning: Decimal
    elektriciteit_cv_gj_per_year_per_woning: Decimal
    elektriciteit_gkw_gj_per_year_per_woning: Decimal

    prijs_tap_eur_per_gj: Decimal
    prijs_cv_eur_per_gj: Decimal
    prijs_gkw_eur_per_gj: Decimal

    elektrisch_vermogen: Decimal

    energiekosten_tap_eur_per_woning_per_jaar: Decimal
    energiekosten_cv_eur_per_woning_per_jaar: Decimal
    energiekosten_gkw_eur_per_woning_per_jaar: Decimal
    energiekosten_totaal_eur_per_woning_per_jaar: Decimal
    tco: Decimal


@dataclass(frozen=True, slots=True)
class HoofdsysteemFullResult:
    energy: EnergieCalculatorFullResult
    results: list[HoofdsysteemScenarioResult]
    by_scenario: dict[str, HoofdsysteemScenarioResult]


class Hoofdsysteem(models.Model):
    naam = models.CharField(max_length=255)
    beschrijving = models.TextField(blank=True, null=True)
    subsystemen = models.ManyToManyField("Subsysteem", related_name="hoofdsystemen")
    beschrijving_url = models.URLField(blank=True, null=True)
    beschrijving_url_title = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Hoofdsysteem"
        verbose_name_plural = "Hoofdsystemen"

    def __str__(self):
        return self.naam

    def calculate(
        self,
        *,
        energie_calculation: EnergieCalculatorFullResult,
        scenarios=(ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG),
        energie_types=(EnergieType.TAP, EnergieType.CV, EnergieType.GKW),
    ) -> HoofdsysteemFullResult:
        """Calculate values for this hoofdsysteem.

        Currently returns:
        - The full typed energy calculation output
        - Per-scenario totals based on the capaciteit fields ("cap" values)

        Additional energy cost calculation (per scenario):
        - capaciteit warmte [GJ/w/j] from `energie_calculation` (TAP/CV/GKW)
        - COPs from `Hoofdkengetal`
        - dynamic energy prices (€/GJ) based on connected subsysteem names
        """

        prijs_tap, prijs_cv, prijs_gkw = self._select_energy_prices()

        results: list[HoofdsysteemScenarioResult] = []
        by_scenario: dict[str, HoofdsysteemScenarioResult] = {}

        jaren_tco = Conversie.objects.get(naam="jaren_tco").waarde

        for scenario in scenarios:
            scenario_key = str(scenario)
            by_type = energie_calculation.by_scenario[scenario_key]

            hoofdkengetal = Hoofdkengetal.objects.get(
                hoofdsysteem=self,
                scenario=scenario_key,
            )

            single = self._calculate_scenario_result(
                scenario_key=scenario_key,
                by_type=by_type,
                hoofdkengetal=hoofdkengetal,
                energie_types=energie_types,
                prijs_tap=prijs_tap,
                prijs_cv=prijs_cv,
                prijs_gkw=prijs_gkw,
                jaren_tco=jaren_tco,
            )
            results.append(single)
            by_scenario[scenario_key] = single

        return HoofdsysteemFullResult(
            energy=energie_calculation,
            results=results,
            by_scenario=by_scenario,
        )

    def _calculate_scenario_result(
        self,
        *,
        scenario_key: str,
        by_type: dict[EnergieTypeValue, EnergieCalculationResult],
        hoofdkengetal: Hoofdkengetal,
        energie_types: tuple[EnergieTypeValue, ...],
        prijs_tap: Decimal,
        prijs_cv: Decimal,
        prijs_gkw: Decimal,
        jaren_tco: Decimal,
    ) -> HoofdsysteemScenarioResult:
        capaciteit_kwh_total = sum(
            (
                by_type[energie_type].capaciteit_warmte_kwh_per_year_per_woning
                for energie_type in energie_types
            ),
            start=Decimal("0"),
        )
        capaciteit_gj_total = sum(
            (
                by_type[energie_type].capaciteit_warmte_gj_per_year_per_woning
                for energie_type in energie_types
            ),
            start=Decimal("0"),
        )

        cap_tap = by_type[EnergieType.TAP].capaciteit_warmte_gj_per_year_per_woning
        cap_cv = by_type[EnergieType.CV].capaciteit_warmte_gj_per_year_per_woning
        cap_gkw = by_type[EnergieType.GKW].capaciteit_warmte_gj_per_year_per_woning

        elec_tap_gj = (
            cap_tap / hoofdkengetal.cop_tap if hoofdkengetal.cop_tap else Decimal("0")
        )
        elec_cv_gj = (
            cap_cv / hoofdkengetal.cop_cv if hoofdkengetal.cop_cv else Decimal("0")
        )
        elec_gkw_gj = (
            cap_gkw / hoofdkengetal.cop_gkw if hoofdkengetal.cop_gkw else Decimal("0")
        )

        vermogen_tap = by_type[EnergieType.TAP].vermogen_warmte_kw_per_vve
        vermogen_cv = by_type[EnergieType.CV].vermogen_warmte_kw_per_vve

        verbruikt_elektriciteit = "warmtelevering" not in self.naam.lower()
        elektrisch_vermogen = (
            (vermogen_tap / hoofdkengetal.cop_tap)
            + (vermogen_cv / hoofdkengetal.cop_cv)
            if verbruikt_elektriciteit
            else Decimal("0")
        )
        kosten_tap = elec_tap_gj * prijs_tap
        kosten_cv = elec_cv_gj * prijs_cv
        kosten_gkw = elec_gkw_gj * prijs_gkw
        kosten_total = kosten_tap + kosten_cv + kosten_gkw
        return HoofdsysteemScenarioResult(
            scenario=scenario_key,
            by_type=by_type,
            capaciteit_warmte_kwh_per_year_per_woning_total=capaciteit_kwh_total,
            capaciteit_warmte_gj_per_year_per_woning_total=capaciteit_gj_total,
            elektriciteit_tap_gj_per_year_per_woning=elec_tap_gj,
            elektriciteit_cv_gj_per_year_per_woning=elec_cv_gj,
            elektriciteit_gkw_gj_per_year_per_woning=elec_gkw_gj,
            prijs_tap_eur_per_gj=prijs_tap,
            prijs_cv_eur_per_gj=prijs_cv,
            prijs_gkw_eur_per_gj=prijs_gkw,
            elektrisch_vermogen=elektrisch_vermogen,
            energiekosten_tap_eur_per_woning_per_jaar=kosten_tap,
            energiekosten_cv_eur_per_woning_per_jaar=kosten_cv,
            energiekosten_gkw_eur_per_woning_per_jaar=kosten_gkw,
            energiekosten_totaal_eur_per_woning_per_jaar=kosten_total,
            tco=kosten_total * jaren_tco,
        )

    def _select_energy_prices(self) -> tuple[Decimal, Decimal, Decimal]:
        elektriciteit_prijs_default = "Elektriciteit"

        if self.subsystemen.filter(naam="Particulier Stadswarmte").exists():
            prijs_tap = self._price_eur_per_gj("SV particulier tap")
            prijs_cv = self._price_eur_per_gj("SV particulier CV")
            prijs_gkw = Decimal("0")
        elif self.subsystemen.filter(naam="Particulier Stadswarmte + koude").exists():
            prijs_tap = self._price_eur_per_gj("SV particulier tap")
            prijs_cv = self._price_eur_per_gj("SV particulier CV")
            prijs_gkw = self._price_eur_per_gj("SV particulier GKW")
        elif self.subsystemen.filter(naam="Zakelijk Stadswarmte").exists():
            prijs_tap = self._price_eur_per_gj("SV zakelijk tap (warmte)")
            prijs_cv = self._price_eur_per_gj("SV zakelijk CV (warmte)")
            prijs_gkw = Decimal("0")
        elif self.subsystemen.filter(naam="Zakelijk Stadswarmte + koude").exists():
            prijs_tap = self._price_eur_per_gj("SV zakelijk tap (warmte + Koude)")
            prijs_cv = self._price_eur_per_gj("SV zakelijk CV (warmte + Koude)")
            prijs_gkw = self._price_eur_per_gj("SV zakelijk GKW (warmte + Koude)")
        else:
            prijs_tap = self._price_eur_per_gj(elektriciteit_prijs_default)
            prijs_cv = self._price_eur_per_gj(elektriciteit_prijs_default)
            prijs_gkw = self._price_eur_per_gj(elektriciteit_prijs_default)

        return prijs_tap, prijs_cv, prijs_gkw

    def _price_eur_per_gj(self, name: str) -> Decimal:
        value = EnergiePrijs.objects.get(naam=name).prijs_eur_per_gj
        return value if value is not None else Decimal("0")


class SubsysteemType(models.TextChoices):
    KENGETAL = "kengetal", "Kengetal"
    STADSWARMTE = "stadswarmte", "Stadswarmte"


class Subsysteem(models.Model):
    naam = models.CharField(max_length=255)

    type = models.CharField(
        max_length=20, choices=SubsysteemType.choices, default=SubsysteemType.KENGETAL
    )

    calculation_method = models.CharField(
        max_length=20,
        choices=SubsysteemCalculationMethod.choices,
        default=None,
        null=True,
    )

    class Meta:
        verbose_name = "Subsysteem"
        verbose_name_plural = "Subsystemen"

    def __str__(self):
        return self.naam

    def calculate(
        self,
        *,
        scenarios=(ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG),
        energie_calculation: EnergieCalculatorFullResult | None = None,
        calculation_input: GebruikersInvoer | None = None,
    ) -> SubsysteemFullResult:
        """Calculate subsysteem-specific values for all scenarios."""
        results: list[SubsysteemScenarioResult] = []
        by_scenario: dict[str, SubsysteemScenarioResult] = {}
        for scenario in scenarios:
            single = self._calculate_single_scenario(
                scenario,
                energie_calculation=energie_calculation,
                calculation_input=calculation_input,
            )
            results.append(single)
            by_scenario[str(scenario)] = single

        return SubsysteemFullResult(results=results, by_scenario=by_scenario)

    def _calculate_single_scenario(
        self,
        scenario: ScenarioKeuze,
        *,
        energie_calculation: EnergieCalculatorFullResult | None,
        calculation_input: GebruikersInvoer | None,
    ):
        """Calculate values for a single scenario."""

        if self.calculation_method == SubsysteemCalculationMethod.Investering:
            berekening = calculate_investering(
                self.subkengetallen.get(scenario=scenario)
            )
            return SubsysteemScenarioResult(
                scenario=str(scenario),
                method=str(self.calculation_method),
                berekening=berekening,
            )

        if self.calculation_method == SubsysteemCalculationMethod.Openbron:
            if energie_calculation is None:
                raise ValueError(
                    "energie_calculation is required for Openbron calculations"
                )

            cv_result = energie_calculation.by_scenario[str(scenario)][EnergieType.CV]
            berekening = calculate_openbron_systeem(
                self.subkengetallen.get(scenario=scenario),
                cv_energie_calculation=cv_result,
            )
            return SubsysteemScenarioResult(
                scenario=str(scenario),
                method=str(self.calculation_method),
                berekening=berekening,
            )

        if self.calculation_method == SubsysteemCalculationMethod.Gbs:
            if energie_calculation is None:
                raise ValueError("energie_calculation is required for GBS calculations")
            if calculation_input is None:
                raise ValueError("calculation_input is required for GBS calculations")
            cv_result = energie_calculation.by_scenario[str(scenario)][EnergieType.CV]
            berekening = calculate_gbs(
                self.subkengetallen.get(scenario=scenario),
                cv_energie_calculation=cv_result,
                aantal_woningen=calculation_input.aantal_woningen,
            )
            return SubsysteemScenarioResult(
                scenario=str(scenario),
                method=str(self.calculation_method),
                berekening=berekening,
            )

        if self.calculation_method == SubsysteemCalculationMethod.Stadsverwarming:
            if energie_calculation is None:
                raise ValueError(
                    "energie_calculation is required for Stadsverwarming calculations"
                )
            if calculation_input is None:
                raise ValueError(
                    "calculation_input is required for Stadsverwarming calculations"
                )

            stadsverwarming_result = StadsverwarmingCalculator().calculate(
                energie_calculation=energie_calculation,
                aantal_woningen=calculation_input.aantal_woningen,
            )
            berekening = calculate_stadsverwarming(
                self.naam,
                stadsverwarming_result,
                scenario,
            )
            return SubsysteemScenarioResult(
                scenario=str(scenario),
                method=str(self.calculation_method),
                berekening=berekening,
            )

        if self.calculation_method == SubsysteemCalculationMethod.Warmtepomp:
            if energie_calculation is None:
                raise ValueError(
                    "energie_calculation is required for Warmtepomp calculations"
                )
            if calculation_input is None:
                raise ValueError(
                    "calculation_input is required for Warmtepomp calculations"
                )

            cv_result = energie_calculation.by_scenario[str(scenario)][EnergieType.CV]
            tap_result = energie_calculation.by_scenario[str(scenario)][EnergieType.TAP]
            berekening = calculate_warmtepomp(
                self.naam,
                subkengetal=self.subkengetallen.get(scenario=scenario),
                cv_energie_calculation=cv_result,
                tap_energie_calculation=tap_result,
                aantal_woningen=calculation_input.aantal_woningen,
            )
            return SubsysteemScenarioResult(
                scenario=str(scenario),
                method=str(self.calculation_method),
                berekening=berekening,
            )

        if self.calculation_method == SubsysteemCalculationMethod.Staffel:
            if calculation_input is None:
                raise ValueError(
                    "calculation_input is required for Staffel calculations"
                )

            berekening = calculate_staffel(
                self.subkengetallen.get(scenario=scenario),
                aantal_woningen=calculation_input.aantal_woningen,
            )
            return SubsysteemScenarioResult(
                scenario=str(scenario),
                method=str(self.calculation_method),
                berekening=berekening,
            )

        raise ValueError(f"Unknown calculation method: {self.calculation_method}")
