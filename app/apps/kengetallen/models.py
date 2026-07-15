from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models.functions import Replace, Upper


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


def _collectieve_ruimte_constraints(*, scope: str) -> list[models.BaseConstraint]:
    return [
        models.UniqueConstraint(
            fields=["hoofdsysteem", "n_min", "n_max"],
            name=f"uniek_hoofdsysteem_n_min_n_max_collectieve_ruimte_{scope}",
        ),
        models.CheckConstraint(
            condition=models.Q(n_max__isnull=True)
            | models.Q(n_max__gte=models.F("n_min")),
            name=f"collectieve_ruimte_{scope}_n_max_gte_n_min_or_null",
        ),
    ]


class CollectieveRuimteBinnen(models.Model):
    hoofdsysteem = models.ForeignKey(
        "systemen.Hoofdsysteem",
        on_delete=models.CASCADE,
        related_name="collectieve_ruimte_binnen",
    )

    n_min = models.IntegerField()
    n_max = models.IntegerField(blank=True, null=True)
    vereiste_m2 = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "Collectieve ruimte binnen"
        verbose_name_plural = "Collectieve ruimte binnen"
        ordering = ["hoofdsysteem", "n_min"]
        constraints = _collectieve_ruimte_constraints(scope="binnen")

    def __str__(self) -> str:
        max_label = "∞" if self.n_max is None else str(self.n_max)
        return f"{self.hoofdsysteem.naam}: {self.n_min}–{max_label} woningen → {self.vereiste_m2} m²"


class CollectieveRuimteBuiten(models.Model):
    hoofdsysteem = models.ForeignKey(
        "systemen.Hoofdsysteem",
        on_delete=models.CASCADE,
        related_name="collectieve_ruimte_buiten",
    )

    n_min = models.IntegerField()
    n_max = models.IntegerField(blank=True, null=True)
    vereiste_m2 = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "Collectieve ruimte buiten"
        verbose_name_plural = "Collectieve ruimte buiten"
        ordering = ["hoofdsysteem", "n_min"]
        constraints = _collectieve_ruimte_constraints(scope="buiten")

    def __str__(self) -> str:
        max_label = "∞" if self.n_max is None else str(self.n_max)
        return f"{self.hoofdsysteem.naam}: {self.n_min}–{max_label} woningen → {self.vereiste_m2} m²"


class CollectieveRuimteTuin(models.Model):
    hoofdsysteem = models.ForeignKey(
        "systemen.Hoofdsysteem",
        on_delete=models.CASCADE,
        related_name="collectieve_ruimte_tuin",
    )

    n_min = models.IntegerField()
    n_max = models.IntegerField(blank=True, null=True)
    vereiste_m2 = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "Collectieve ruimte tuin"
        verbose_name_plural = "Collectieve ruimte tuin"
        ordering = ["hoofdsysteem", "n_min"]
        constraints = _collectieve_ruimte_constraints(scope="tuin")

    def __str__(self) -> str:
        max_label = "∞" if self.n_max is None else str(self.n_max)
        return f"{self.hoofdsysteem.naam}: {self.n_min}–{max_label} woningen → {self.vereiste_m2} m²"


class EliminatieKengetal(models.Model):
    naam = models.CharField(max_length=255, unique=True)

    woningen_min = models.IntegerField()
    woningen_max = models.IntegerField(blank=True, null=True)

    benodigde_ruimte_in_woning_m2 = models.DecimalField(max_digits=18, decimal_places=9)

    stadsverwarming_nodig = models.BooleanField(default=False)
    mechanische_ventilatie_nodig = models.BooleanField(default=False)
    kan_koelen = models.BooleanField(default=False)
    laag_energieverbruik = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Eliminatie kengetal"
        verbose_name_plural = "Eliminatie kengetallen"
        ordering = ["naam", "woningen_min"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(woningen_max__isnull=True)
                | models.Q(woningen_max__gte=models.F("woningen_min")),
                name="eliminatiekengetal_woningen_max_gte_min_or_null",
            )
        ]

    def __str__(self) -> str:
        max_label = "∞" if self.woningen_max is None else str(self.woningen_max)
        return f"{self.naam}: {self.woningen_min}–{max_label} woningen"


class MultiCriteriaAnalyseKengetal(models.Model):
    hoofdsysteem = models.OneToOneField(
        "systemen.Hoofdsysteem",
        on_delete=models.CASCADE,
        related_name="mca_kengetal",
    )

    huidig_systeem_collectief = models.DecimalField(max_digits=18, decimal_places=9)
    huidig_systeem_individueel = models.DecimalField(max_digits=18, decimal_places=9)
    vloerverwarming_aanwezig_waar = models.DecimalField(max_digits=18, decimal_places=9)
    vloerverwarming_aanwezig_onwaar = models.DecimalField(
        max_digits=18, decimal_places=9
    )

    class Meta:
        verbose_name = "Multi-criteria analyse kengetal"
        verbose_name_plural = "Multi-criteria analyse kengetallen"
        ordering = ["hoofdsysteem"]

    def __str__(self) -> str:
        return f"{self.hoofdsysteem.naam} (MCA)"


class McdaHoofdcriterium(models.Model):
    naam = models.CharField(max_length=255, unique=True)
    wegingsfactor = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "MCDA hoofdcriterium"
        verbose_name_plural = "MCDA hoofdcriteria"
        ordering = ["naam"]

    def __str__(self) -> str:
        return f"{self.naam} ({self.wegingsfactor})"


class McdaSubcriterium(models.Model):
    hoofdcriterium = models.ForeignKey(
        McdaHoofdcriterium,
        on_delete=models.CASCADE,
        related_name="subcriteria",
    )
    naam = models.CharField(max_length=255)
    relatieve_wegingsfactor = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "MCDA subcriterium"
        verbose_name_plural = "MCDA subcriteria"
        ordering = ["hoofdcriterium", "naam"]
        constraints = [
            models.UniqueConstraint(
                fields=["hoofdcriterium", "naam"],
                name="uniek_mcda_hoofcriterium_naam",
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.hoofdcriterium.naam} → {self.naam} ({self.relatieve_wegingsfactor})"
        )


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


class Warmteprogramma(models.Model):
    categorie = models.CharField(max_length=255, unique=True, blank=True, null=True)
    warmtenet_start = models.IntegerField(blank=True, null=True)
    warmtenet_stop = models.IntegerField(blank=True, null=True)
    hoofdsystemen = models.ManyToManyField(
        "systemen.Hoofdsysteem",
        blank=True,
        related_name="warmteprogrammas",
    )

    class Meta:
        verbose_name = "Warmteprogramma kengetal"
        verbose_name_plural = "Warmteprogramma kengetallen"
        indexes = [models.Index(fields=["categorie"])]

    def __str__(self) -> str:
        categorie = self.categorie or "<null>"
        return f"{categorie} ({self.warmtenet_start}–{self.warmtenet_stop})"


class BuurtcodeWarmteprogramma(models.Model):
    buurtcode = models.CharField(max_length=16, unique=True)
    warmteprogramma = models.ForeignKey(
        Warmteprogramma,
        on_delete=models.PROTECT,
        related_name="buurtcodes",
    )

    class Meta:
        verbose_name = "Buurtcode warmteprogramma"
        verbose_name_plural = "Buurtcode warmteprogramma"
        indexes = [models.Index(fields=["buurtcode"])]

    def __str__(self) -> str:
        return f"{self.buurtcode}→{self.warmteprogramma}"


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

    positieve_factor = models.DecimalField(max_digits=18, decimal_places=9)
    negatieve_factor = models.DecimalField(max_digits=18, decimal_places=9)

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


class GasverbruikGegeven(models.Model):
    postcode_start = models.CharField(max_length=7)
    postcode_eind = models.CharField(max_length=7)
    gemiddeld_verbruik = models.DecimalField(max_digits=18, decimal_places=9)

    @classmethod
    def gemiddeld_verbruik_voor_postcode(cls, postcode: str) -> Decimal | None:
        normalized_postcode = postcode.upper().replace(" ", "")
        if not normalized_postcode:
            return None

        return (
            cls.objects.annotate(
                postcode_start_normalized=Replace(
                    Upper("postcode_start"), models.Value(" "), models.Value("")
                ),
                postcode_eind_normalized=Replace(
                    Upper("postcode_eind"), models.Value(" "), models.Value("")
                ),
            )
            .filter(
                postcode_start_normalized__lte=normalized_postcode,
                postcode_eind_normalized__gte=normalized_postcode,
            )
            .order_by("postcode_start", "postcode_eind")
            .values_list("gemiddeld_verbruik", flat=True)
            .first()
        )

    class Meta:
        verbose_name = "Gasverbruikgegeven"
        verbose_name_plural = "Gasverbruikgegevens"
        ordering = ["postcode_start", "postcode_eind"]
        indexes = [
            models.Index(fields=["postcode_start"]),
            models.Index(fields=["postcode_eind"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["postcode_start", "postcode_eind"],
                name="uniek_postcode_start_postcode_eind_gasverbruik",
            )
        ]

    def __str__(self) -> str:
        return f"{self.postcode_start}–{self.postcode_eind}: {self.gemiddeld_verbruik}"
