from django.db import models


class Kengetal(models.Model):
    SCENARIO_KEUZES = [
        ("laag", "Laag"),
        ("midden", "Midden"),
        ("hoog", "Hoog"),
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

    cop_tap = models.FloatField()
    cop_cv = models.FloatField()
    cop_gkw = models.FloatField()

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

    investeringskosten = models.FloatField()
    levensduur = models.IntegerField()
    beheer_en_onderhoud = models.FloatField()
    verhouding_vermogen_bron = models.FloatField(blank=True, null=True)
    debiet_bron = models.IntegerField(blank=True, null=True)
    energie_bron = models.FloatField(blank=True, null=True)
    delta_temperatuur_retour = models.IntegerField(blank=True, null=True)
    onttrekkingsvermogen = models.FloatField(blank=True, null=True)

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
