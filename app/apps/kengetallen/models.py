from __future__ import annotations


from django.db import models


class ScenarioKeuze(models.TextChoices):
    LAAG = "laag", "Laag"
    MIDDEN = "midden", "Midden"
    HOOG = "hoog", "Hoog"


class Kengetal(models.Model):
    SCENARIO_KEUZES = [
        (ScenarioKeuze.LAAG, "Laag"),
        (ScenarioKeuze.MIDDEN, "Midden"),
        (ScenarioKeuze.HOOG, "Hoog"),
    ]

    scenario = models.CharField(max_length=10, choices=SCENARIO_KEUZES)

    class Meta:
        abstract = True


class Hoofdkengetal(Kengetal):
    hoofdsysteem = models.ForeignKey(
        "systemen.Hoofdsysteem",
        on_delete=models.CASCADE,
        related_name="hoofdkengetallen",
    )

    cop_tap = models.DecimalField(max_digits=18, decimal_places=9)
    cop_cv = models.DecimalField(max_digits=18, decimal_places=9)
    cop_gkw = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "Hoofdkengetal"
        verbose_name_plural = "Hoofdkengetallen"
        constraints = [
            models.UniqueConstraint(
                fields=["scenario", "hoofdsysteem"],
                name="uniek_scenario_hoofdsysteem",
            )
        ]

    def __str__(self):
        return f"{self.hoofdsysteem.naam} - {self.scenario}"


class Subkengetal(Kengetal):
    subsysteem = models.ForeignKey(
        "systemen.Subsysteem",
        on_delete=models.CASCADE,
        related_name="subkengetallen",
    )

    investeringskosten = models.DecimalField(max_digits=18, decimal_places=9)
    levensduur = models.IntegerField()
    beheer_en_onderhoud = models.DecimalField(max_digits=18, decimal_places=9)
    verhouding_vermogen_bron = models.DecimalField(
        max_digits=18, decimal_places=9, blank=True, null=True
    )
    debiet_bron = models.IntegerField(blank=True, null=True)
    energie_bron = models.DecimalField(
        max_digits=18, decimal_places=9, blank=True, null=True
    )
    delta_temperatuur_retour = models.IntegerField(blank=True, null=True)
    onttrekkingsvermogen = models.DecimalField(
        max_digits=18, decimal_places=9, blank=True, null=True
    )

    class Meta:
        verbose_name = "Subkengetal"
        verbose_name_plural = "Subkengetallen"
        constraints = [
            models.UniqueConstraint(
                fields=["scenario", "subsysteem"],
                name="uniek_scenario_subsysteem",
            )
        ]

    def __str__(self):
        return f"{self.subsysteem.naam} - {self.scenario}"


class AlgemeenKengetal(Kengetal):

    naam = models.CharField(max_length=255)
    omschrijving = models.CharField(max_length=255)
    waarde = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "Algemeen kengetal"
        verbose_name_plural = "Algemene kengetallen"
