from __future__ import annotations

from django.db import models


class GebruikersInvoer(models.Model):
    bouwjaar = models.PositiveIntegerField()
    bruto_vloeroppervlak = models.DecimalField(max_digits=18, decimal_places=9)
    aantal_woningen = models.PositiveIntegerField()

    mechanische_ventilatie_aanwezig = models.BooleanField()
    vloerverwarming_aanwezig = models.BooleanField()
    inpandige_berging_aanwezig = models.BooleanField()
    ruimte_op_het_dak_aanwezig = models.BooleanField()

    type_dak = models.CharField(
        max_length=20,
        choices=[
            ("plat_dak", "Plat dak"),
            ("schuin_dak", "Schuin dak"),
        ],
    )

    tapwater_op_gas = models.BooleanField()
    koken_op_gas = models.BooleanField(default=False)
    gasverbruik_vve_totaal = models.DecimalField(max_digits=18, decimal_places=9)
    elektriciteitsverbruik_per_woning = models.DecimalField(
        max_digits=18, decimal_places=9
    )
    elektriciteitsverbruik_vve_totaal = models.DecimalField(
        max_digits=18, decimal_places=9
    )

    gecontracteerd_vermogen = models.DecimalField(max_digits=18, decimal_places=9)

    huidige_warmtesysteem = models.CharField(
        max_length=20,
        choices=[
            ("warmtepomp", "Warmtepomp"),
            ("cv_ketel", "Cv-ketel"),
            ("anders", "Anders"),
        ],
    )

    volledig_gasloos = models.BooleanField()
    wens_tot_koelen = models.BooleanField()
    dubbel_glas = models.BooleanField(default=False)
    wtw_aanwezig = models.BooleanField(default=False)
    buurtcode = models.CharField(max_length=20, blank=True, null=True)
    jaar_vervangen = models.PositiveIntegerField(blank=True, null=True)

    beschikbare_ruimte_in_woning_m2 = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        default=1,
    )
    beschikbare_collectieve_ruimte_binnen_m2 = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        default=20,
    )
    beschikbare_collectieve_ruimte_buiten_m2 = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        default=100,
    )

    class Meta:
        verbose_name = "Gebruikersinvoer"
        verbose_name_plural = "Gebruikersinvoer"

    def __str__(self):
        return f"GebruikersInvoer {self.pk or '-'} ({self.bouwjaar})"


class Conversie(models.Model):
    """Conversion factors used by calculation logic.

    Values are stored in the database and typically loaded via fixtures.
    """

    naam = models.CharField(max_length=64, unique=True)
    waarde = models.DecimalField(max_digits=18, decimal_places=9)

    class Meta:
        verbose_name = "Conversie"
        verbose_name_plural = "Conversies"

    def __str__(self) -> str:
        return f"{self.naam}={self.waarde}"


class EnergiePrijs(models.Model):
    """Energy price per GJ.

    Values are stored in the database and typically loaded via fixtures.

    Some prices may be unknown/not applicable; those can be stored as null.
    """

    naam = models.CharField(max_length=64, unique=True)
    prijs_eur_per_gj = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Energieprijs"
        verbose_name_plural = "Energieprijzen"

    def __str__(self) -> str:
        return (
            f"{self.naam}={self.prijs_eur_per_gj} €/GJ"
            if self.prijs_eur_per_gj is not None
            else f"{self.naam}=<null> €/GJ"
        )


class CalculationDashboard(GebruikersInvoer):
    """Proxy model used to expose a custom admin page in the sidebar."""

    class Meta:
        proxy = True
        verbose_name = "Berekeningen"
        verbose_name_plural = "Berekeningen"
