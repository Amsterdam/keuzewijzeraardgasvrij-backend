from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response

from apps.calculations.calculator import EnergieCalculator, MultiCriteriaAnalyse
from drf_spectacular.utils import extend_schema
from .models import GebruikersInvoer
from .pdok_client import PdokClient
from .dso_client import DsoClient
from .serializers import (
    GebruikersInvoerCreateSerializer,
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

    def retrieve(self, _, pk: str | None = None):
        pdok_client = PdokClient()
        dso_client = DsoClient()
        try:
            pand_info = pdok_client.get_pand_info(bag_id=pk)
            bruto_vloeroppervlak = dso_client.get_bruto_vloeroppervlak(
                pand_info.identificatie
            )
        except Exception as exc:
            logger.error("Error fetching BAG info for BAG_ID %s: %s", pk, exc)
            return Response(
                {"detail": f"Error fetching BAG info"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "bruto_vloeroppervlak": bruto_vloeroppervlak or None,
                "aantal_woningen": pand_info.aantal_woningen or None,
                "bouwjaar": pand_info.bouwjaar or None,
            },
            status=status.HTTP_200_OK,
        )
