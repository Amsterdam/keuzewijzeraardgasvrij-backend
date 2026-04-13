import math
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import GebruikersInvoer


def _validate_finite_number(value, _: str):
    if value is None:
        raise serializers.ValidationError("Must be a finite number.")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise serializers.ValidationError("Must be a finite number.")
        return value
    if not math.isfinite(value):
        raise serializers.ValidationError("Must be a finite number.")
    return value


class GebruikersInvoerCreateSerializer(serializers.ModelSerializer):
    bouwjaar = serializers.IntegerField(min_value=1, max_value=timezone.now().year)
    bruto_vloeroppervlak = serializers.DecimalField(
        max_digits=18,
        decimal_places=9,
        min_value=Decimal("0"),
        max_value=Decimal("1000000"),
    )
    aantal_woningen = serializers.IntegerField(min_value=1, max_value=100_000)

    gasverbruik_vve_totaal = serializers.DecimalField(
        max_digits=18,
        decimal_places=9,
        min_value=Decimal("0"),
        max_value=Decimal("999999999.999999999"),
    )
    elektriciteitsverbruik_per_woning = serializers.DecimalField(
        max_digits=18,
        decimal_places=9,
        min_value=Decimal("0"),
        max_value=Decimal("999999999.999999999"),
    )
    elektriciteitsverbruik_vve_totaal = serializers.DecimalField(
        max_digits=18,
        decimal_places=9,
        min_value=Decimal("0"),
        max_value=Decimal("999999999.999999999"),
    )

    gecontracteerd_vermogen = serializers.DecimalField(
        max_digits=18,
        decimal_places=9,
        min_value=Decimal("0"),
        max_value=Decimal("1000000"),
    )

    class Meta:
        model = GebruikersInvoer
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
            "gasverbruik_vve_totaal",
            "elektriciteitsverbruik_per_woning",
            "elektriciteitsverbruik_vve_totaal",
            "gecontracteerd_vermogen",
            "huidige_warmtesysteem",
            "volledig_gasloos",
            "wens_tot_koelen",
            "koken_op_gas",
        ]
        read_only_fields = ["id"]

    def validate_bruto_vloeroppervlak(self, value):
        value = _validate_finite_number(value, "bruto_vloeroppervlak")
        if value <= 0:
            raise serializers.ValidationError("Must be > 0.")
        return value

    def validate_gasverbruik_vve_totaal(self, value):
        return _validate_finite_number(value, "gasverbruik_vve_totaal")

    def validate_elektriciteitsverbruik_per_woning(self, value):
        return _validate_finite_number(value, "elektriciteitsverbruik_per_woning")

    def validate_elektriciteitsverbruik_vve_totaal(self, value):
        return _validate_finite_number(value, "elektriciteitsverbruik_vve_totaal")

    def validate_gecontracteerd_vermogen(self, value):
        return _validate_finite_number(value, "gecontracteerd_vermogen")
