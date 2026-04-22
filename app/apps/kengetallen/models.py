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
    staffel = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        blank=True,
        null=True,
        default=None,
    )
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


class GelijktijdigheidCV(models.Model):
    n_min = models.IntegerField()
    n_max = models.IntegerField(blank=True, null=True)
    factor = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "GelijktijdigheidCV"
        verbose_name_plural = "GelijktijdigheidCV"
        ordering = ["n_min"]
        constraints = [
            models.UniqueConstraint(
                fields=["n_min", "n_max"],
                name="uniek_n_min_n_max_gelijktijdigheidcv",
            )
        ]

    def __str__(self) -> str:
        max_label = "∞" if self.n_max is None else str(self.n_max)
        return f"{self.n_min}–{max_label}: {self.factor}"


class CollectieveWarmtepompKengetal(models.Model):
    """Kengetallen for the collective warmtepomp sizing/cost formula."""

    naam = models.CharField(max_length=64, unique=True)
    omschrijving = models.CharField(max_length=255, blank=True, default="")
    waarde = models.DecimalField(max_digits=18, decimal_places=9, default=0)

    class Meta:
        verbose_name = "Collectieve warmtepomp kengetal"
        verbose_name_plural = "Collectieve warmtepomp kengetallen"

    def __str__(self) -> str:
        return f"{self.naam}={self.waarde}"


class StadsverwarmingKlantType(models.TextChoices):
    PARTICULIER = "particulier", "Particulier"
    ZAKELIJK = "zakelijk", "Zakelijk"


class StadsverwarmingProductType(models.TextChoices):
    WARMTE = "warmte", "Warmte"
    KOUDE = "koude", "Koude"
    WARMTE_KOUDE = "warmte_koude", "Warmte + koude"


class StadsverwarmingEenheid(models.TextChoices):
    VAST = "vast", "Vast"
    VARIABEL = "variabel", "Variabel"
    GECLASSIFICEERD = "geclassificeerd", "Geclassificeerd"


class StadsverwarmingInterval(models.TextChoices):
    EENMALIG = "eenmalig", "Eenmalig"
    JAARLIJKS = "jaarlijks", "Jaarlijks"
    MAANDELIJKS = "maandelijks", "Maandelijks"


class StadsverwarmingVermogenBerekenenOp(models.TextChoices):
    WARMTE = "warmte", "Warmte"
    KOUDE = "koude", "Koude"


class StadsverwarmingKengetal(models.Model):
    klanttype = models.CharField(
        max_length=20, choices=StadsverwarmingKlantType.choices
    )
    producttype = models.CharField(
        max_length=20,
        choices=StadsverwarmingProductType.choices,
    )
    kostetype = models.CharField(max_length=255)
    eenheid = models.CharField(max_length=20, choices=StadsverwarmingEenheid.choices)
    interval = models.CharField(
        max_length=20,
        choices=StadsverwarmingInterval.choices,
    )

    vermogen_berekenen_op = models.CharField(
        max_length=20,
        choices=StadsverwarmingVermogenBerekenenOp.choices,
        blank=True,
        null=True,
    )

    kw_min = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        blank=True,
        null=True,
    )
    kw_max = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        blank=True,
        null=True,
    )

    waarde_1 = models.DecimalField(max_digits=18, decimal_places=9)
    waarde_2 = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "Stadsverwarming kengetal"
        verbose_name_plural = "Stadsverwarming kengetallen"
        indexes = [
            models.Index(fields=["klanttype", "producttype"]),
            models.Index(fields=["kostetype"]),
        ]

    def __str__(self) -> str:
        kw_range = ""
        if self.kw_min is not None or self.kw_max is not None:
            kw_range = f" ({self.kw_min or 0}–{self.kw_max or '∞'} kW)"
        return f"{self.klanttype}/{self.producttype} - {self.kostetype}{kw_range}"
