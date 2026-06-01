from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response

from apps.calculations.calculator import EnergieCalculator, MultiCriteriaAnalyse
from apps.kengetallen.models import GasverbruikGegeven
from drf_spectacular.utils import OpenApiParameter, extend_schema
from .models import Conversie, GebruikersInvoer
from .pdok_client import PdokClient
from .dso_client import DsoClient
from .serializers import (
    GebruikersInvoerCreateSerializer,
    GebruikersInvoerBagResponseSerializer,
    HoofdsysteemCalculationResultSerializer,
)
import logging

logger = logging.getLogger(__name__)


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
        rows = MultiCriteriaAnalyse().calculate(
            calculation_input=calculation_input,
            energie_calculation=energie,
        )
        output_serializer = HoofdsysteemCalculationResultSerializer(
            rows,
            many=True,
        )

        return Response(output_serializer.data, status=201)

    @extend_schema(
        responses={
            200: GebruikersInvoerBagResponseSerializer,
        },
        parameters=[
            OpenApiParameter(
                name="bagId",
                description="adresseerbaarobject_id van het adres",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            )
        ],
    )
    def prefill(self, _, bagId: str | None = None):
        pdok_client = PdokClient()
        dso_client = DsoClient()
        try:
            pand_info = pdok_client.get_pand_info(bag_id=bagId)
            bruto_vloeroppervlak = dso_client.get_bruto_vloeroppervlak(
                pand_info.identificatie
            )
            bvo_factor = Conversie.objects.get(naam="bvo_factor").waarde
            bruto_vloeroppervlak = round(bruto_vloeroppervlak * bvo_factor)
        except Exception as exc:
            logger.error("Error fetching BAG info for BAG_ID %s: %s", bagId, exc)
            return Response(
                {"detail": f"Error fetching BAG info"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gasverbruik_per_woning = GasverbruikGegeven.gemiddeld_verbruik_voor_postcode(
            pand_info.postcode or ""
        )
        gasverbruik_vve_totaal = None
        if gasverbruik_per_woning is not None and pand_info.aantal_woningen is not None:
            gasverbruik_vve_totaal = round(
                gasverbruik_per_woning * pand_info.aantal_woningen
            )

        response_serializer = GebruikersInvoerBagResponseSerializer(
            data={
                "bruto_vloeroppervlak": bruto_vloeroppervlak or None,
                "aantal_woningen": pand_info.aantal_woningen or None,
                "bouwjaar": pand_info.bouwjaar or None,
                "gasverbruik_vve_totaal": gasverbruik_vve_totaal,
            }
        )
        response_serializer.is_valid(raise_exception=True)

        return Response(response_serializer.data, status=status.HTTP_200_OK)
