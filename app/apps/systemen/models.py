from __future__ import annotations


from django.db import models

from apps.calculations.subsysteem_calculations import (
    SubsysteemCalculationMethod,
    SubsysteemFullResult,
    calculate_investering,
    calculate_openbron_systeem,
)


from apps.kengetallen.models import ScenarioKeuze
from apps.calculations.calculator import EnergieCalculatorFullResult, EnergieType


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
    ) -> SubsysteemFullResult:
        """Calculate subsysteem-specific values for all scenarios.

        Centralizes the scenario iteration so callers don't need to loop.
        """
        results = []
        by_scenario = {}
        for scenario in scenarios:
            single = self._calculate_single_scenario(
                scenario, energie_calculation=energie_calculation
            )
            results.append(single)
            by_scenario[str(scenario)] = single

        return {"results": results, "by_scenario": by_scenario}

    def _calculate_single_scenario(
        self,
        scenario: ScenarioKeuze,
        *,
        energie_calculation: EnergieCalculatorFullResult | None,
    ):
        """Calculate values for a single scenario."""

        if self.calculation_method == SubsysteemCalculationMethod.Investering:
            values = calculate_investering(self.subkengetallen.get(scenario=scenario))
            return {
                "Scenario": str(scenario),
                "Method": str(self.calculation_method),
                **values,
            }

        if self.calculation_method == SubsysteemCalculationMethod.Openbron:
            cv_result = energie_calculation["by_scenario"][str(scenario)][
                EnergieType.CV
            ]
            values = calculate_openbron_systeem(
                self.subkengetallen.get(scenario=scenario),
                cv_energie_calculation=cv_result,
            )
            return {
                "Scenario": str(scenario),
                "Method": str(self.calculation_method),
                **values,
            }

        raise ValueError(f"Unknown calculation method: {self.calculation_method}")
