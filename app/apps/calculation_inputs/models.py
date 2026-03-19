from django.db import models


class CalculationInput(models.Model):
    bouwjaar = models.PositiveIntegerField()
    bruto_vloeroppervlak = models.FloatField()
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

    gasverbruik_per_woning = models.FloatField()
    gasverbruik_vve_totaal = models.FloatField()
    elektriciteitsverbruik_per_woning = models.FloatField()
    elektriciteitsverbruik_vve_totaal = models.FloatField()

    gecontracteerd_vermogen = models.FloatField()

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

    class Meta:
        verbose_name = "Calculation input"
        verbose_name_plural = "Calculation inputs"

    def __str__(self):
        return f"CalculationInput {self.pk or '-'} ({self.bouwjaar})"
