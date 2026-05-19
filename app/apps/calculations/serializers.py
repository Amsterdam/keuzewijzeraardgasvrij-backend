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
    beschikbare_ruimte_in_woning_m2 = serializers.DecimalField(
        max_digits=18,
        decimal_places=9,
        min_value=Decimal("0"),
        max_value=Decimal("1000000"),
        required=False,
    )
    beschikbare_collectieve_ruimte_binnen_m2 = serializers.DecimalField(
        max_digits=18,
        decimal_places=9,
        min_value=Decimal("0"),
        max_value=Decimal("1000000"),
        required=False,
    )
    beschikbare_collectieve_ruimte_buiten_m2 = serializers.DecimalField(
        max_digits=18,
        decimal_places=9,
        min_value=Decimal("0"),
        max_value=Decimal("1000000"),
        required=False,
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
            "tapwater_op_gas",
            "gasverbruik_vve_totaal",
            "beschikbare_ruimte_in_woning_m2",
            "beschikbare_collectieve_ruimte_binnen_m2",
            "beschikbare_collectieve_ruimte_buiten_m2",
            "wens_tot_koelen",
            "koken_op_gas",
            "dubbel_glas",
            "wtw_aanwezig",
            "buurtcode",
            "jaar_vervangen",
            "huidig_systeem",
        ]
        read_only_fields = ["id"]

    def validate_bruto_vloeroppervlak(self, value):
        value = _validate_finite_number(value, "bruto_vloeroppervlak")
        if value <= 0:
            raise serializers.ValidationError("Must be > 0.")
        return value

    def validate_gasverbruik_vve_totaal(self, value):
        return _validate_finite_number(value, "gasverbruik_vve_totaal")


class HoofdsysteemCalculationResultSerializer(serializers.Serializer):
    naam = serializers.CharField()
    beschrijving = serializers.CharField(allow_blank=True)
    beschrijving_url = serializers.CharField(allow_blank=True)
    tco = serializers.IntegerField()
    score = serializers.IntegerField()
    is_mogelijk = serializers.BooleanField()
    redenen_niet_mogelijk = serializers.ListField(child=serializers.CharField())
    kosten_per_woning_per_jaar = serializers.IntegerField()
    kosten_per_woning_per_jaar_laag = serializers.IntegerField()
    kosten_per_woning_per_jaar_hoog = serializers.IntegerField()
    redenen_score = serializers.ListField(child=serializers.CharField())
