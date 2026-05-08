from decimal import Decimal

from rest_framework import viewsets
from rest_framework.response import Response

from apps.calculations.calculator import Eliminatie, EnergieCalculator
from apps.kengetallen.models import ScenarioKeuze
from apps.systemen.models import Hoofdsysteem
from drf_spectacular.utils import extend_schema

from .models import GebruikersInvoer
from .serializers import (
    GebruikersInvoerCreateSerializer,
    HoofdsysteemCalculationResultSerializer,
)


class GebruikersInvoerCreateView(viewsets.GenericViewSet):
    queryset = GebruikersInvoer.objects.all()
    serializer_class = GebruikersInvoerCreateSerializer
    pagination_class = None

    @extend_schema(
        request=GebruikersInvoerCreateSerializer,
        responses={
            201: HoofdsysteemCalculationResultSerializer(many=True),
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        calculation_input: GebruikersInvoer = serializer.save()

        energie = EnergieCalculator().calculate(calculation_input)
        eliminatie = Eliminatie()

        scenario_key = str(ScenarioKeuze.MIDDEN)

        items: list[tuple[tuple[bool, Decimal], dict[str, object]]] = []
        for hoofdsysteem in Hoofdsysteem.objects.order_by("id"):
            full = hoofdsysteem.calculate(energie_calculation=energie)
            hoofdsysteem_tco = full.by_scenario[scenario_key].tco

            subsysteem_tco = Decimal("0")
            for subsysteem in hoofdsysteem.subsystemen.all():
                if not subsysteem.calculation_method:
                    continue
                subs_full = subsysteem.calculate(
                    scenarios=(ScenarioKeuze.MIDDEN,),
                    energie_calculation=energie,
                    calculation_input=calculation_input,
                )
                subsysteem_tco += subs_full.by_scenario[scenario_key].berekening.tco

            elim = eliminatie.calculate(calculation_input, hoofdsysteem.naam)
            redenen = elim.get("redenen")
            if not isinstance(redenen, list):
                redenen = []

            tco_midden = (hoofdsysteem_tco + subsysteem_tco).quantize(Decimal("0.01"))

            is_mogelijk = bool(elim.get("is_mogelijk"))

            items.append(
                (
                    (not is_mogelijk, tco_midden),
                    {
                        "naam": hoofdsysteem.naam,
                        "beschrijving": str(hoofdsysteem.beschrijving or ""),
                        "tco": float(tco_midden),
                        "kosten_per_woning_per_jaar": float(tco_midden / 30),
                        "is_mogelijk": is_mogelijk,
                        "redenen": redenen,
                    },
                )
            )

            items.sort()

            output_serializer = HoofdsysteemCalculationResultSerializer(
                [row for _, row in items],
                many=True,
            )
            return Response(output_serializer.data, status=201)
