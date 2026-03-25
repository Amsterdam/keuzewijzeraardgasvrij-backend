from __future__ import annotations


from django.db import models

from apps.calculations.subsysteem_calculations import (
    SubsysteemCalculationMethod,
    calculate_investering,
)


from apps.kengetallen.models import ScenarioKeuze


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

    def calculate(self, scenario: ScenarioKeuze):
        """Calculate subsysteem-specific values for a given scenario.

        Uses the related `Subkengetal` row for this subsysteem + scenario.
        """

        if self.calculation_method == SubsysteemCalculationMethod.Investering:
            return calculate_investering(self.subkengetallen.get(scenario=scenario))
