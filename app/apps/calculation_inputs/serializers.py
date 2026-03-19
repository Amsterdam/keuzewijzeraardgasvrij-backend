import math

from django.utils import timezone
from rest_framework import serializers

from .models import CalculationInput


def _validate_finite_number(value, _: str):
    if value is None or not math.isfinite(value):
        raise serializers.ValidationError("Must be a finite number.")
    return value


class CalculationInputCreateSerializer(serializers.ModelSerializer):
    bouwjaar = serializers.IntegerField(min_value=1, max_value=timezone.now().year)
    bruto_vloeroppervlak = serializers.FloatField(min_value=0.0, max_value=1_000_000.0)
    aantal_woningen = serializers.IntegerField(min_value=1, max_value=100_000)

    gasverbruik_per_woning = serializers.FloatField(
        min_value=0.0, max_value=1_000_000_000.0
    )
    gasverbruik_vve_totaal = serializers.FloatField(
        min_value=0.0, max_value=1_000_000_000.0
    )
    elektriciteitsverbruik_per_woning = serializers.FloatField(
        min_value=0.0, max_value=1_000_000_000.0
    )
    elektriciteitsverbruik_vve_totaal = serializers.FloatField(
        min_value=0.0, max_value=1_000_000_000.0
    )

    gecontracteerd_vermogen = serializers.FloatField(
        min_value=0.0, max_value=1_000_000.0
    )

    class Meta:
        model = CalculationInput
        fields = [
            "id",
            "bouwjaar",
            "bruto_vloeroppervlak",
            "aantal_woningen",
            "mechanische_ventilatie_aanwezig",
            "vloerverwarming_aanwezig",
            "inpandige_berging_aanwezig",
            "ruimte_op_het_dak_aanwezig",
            "type_dak",
            "tapwater_op_gas",
            "gasverbruik_per_woning",
            "gasverbruik_vve_totaal",
            "elektriciteitsverbruik_per_woning",
            "elektriciteitsverbruik_vve_totaal",
            "gecontracteerd_vermogen",
            "huidige_warmtesysteem",
            "volledig_gasloos",
            "wens_tot_koelen",
        ]
        read_only_fields = ["id"]

    def validate_bruto_vloeroppervlak(self, value):
        value = _validate_finite_number(value, "bruto_vloeroppervlak")
        if value <= 0:
            raise serializers.ValidationError("Must be > 0.")
        return value

    def validate_gasverbruik_per_woning(self, value):
        return _validate_finite_number(value, "gasverbruik_per_woning")

    def validate_gasverbruik_vve_totaal(self, value):
        return _validate_finite_number(value, "gasverbruik_vve_totaal")

    def validate_elektriciteitsverbruik_per_woning(self, value):
        return _validate_finite_number(value, "elektriciteitsverbruik_per_woning")

    def validate_elektriciteitsverbruik_vve_totaal(self, value):
        return _validate_finite_number(value, "elektriciteitsverbruik_vve_totaal")

    def validate_gecontracteerd_vermogen(self, value):
        return _validate_finite_number(value, "gecontracteerd_vermogen")
