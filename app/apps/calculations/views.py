from rest_framework import viewsets
from rest_framework.response import Response

from apps.calculations.calculator import EnergieCalculator, MultiCriteriaAnalyse
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
        hoofdsystemen = Hoofdsysteem.objects.order_by("id").prefetch_related(
            "subsystemen"
        )

        rows = MultiCriteriaAnalyse().calculate(
            calculation_input=calculation_input,
            hoofdsystemen=hoofdsystemen,
            energie_calculation=energie,
        )

        output_serializer = HoofdsysteemCalculationResultSerializer(
            rows,
            many=True,
        )

        return Response(output_serializer.data, status=201)
