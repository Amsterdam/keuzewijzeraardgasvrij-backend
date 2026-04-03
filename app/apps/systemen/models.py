from __future__ import annotations


from django.db import models

from apps.calculations.subsysteem_calculations import (
    SubsysteemCalculationMethod,
    SubsysteemFullResult,
    SubsysteemScenarioResult,
    calculate_gbs,
    calculate_investering,
    calculate_openbron_systeem,
)


from apps.kengetallen.models import ScenarioKeuze
from apps.calculations.calculator import EnergieCalculatorFullResult, EnergieType
from apps.calculations.models import CalculationInput


class Hoofdsysteem(models.Model):
    naam = models.CharField(max_length=255)
    beschrijving = models.TextField(blank=True, null=True)
    subsystemen = models.ManyToManyField("Subsysteem", related_name="hoofdsystemen")
    beschrijving_url = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = "Hoofdsysteem"
        verbose_name_plural = "Hoofdsystemen"

    def __str__(self):
        return self.naam


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
        calculation_input: CalculationInput | None = None,
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
        calculation_input: CalculationInput | None,
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
        raise ValueError(f"Unknown calculation method: {self.calculation_method}")
