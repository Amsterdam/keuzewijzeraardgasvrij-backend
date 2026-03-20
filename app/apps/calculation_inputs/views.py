from rest_framework import generics, throttling

from .models import CalculationInput
from .serializers import CalculationInputCreateSerializer


class CalculationInputThrottle(throttling.AnonRateThrottle):
    scope = "calculation_input"


class CalculationInputCreateView(generics.CreateAPIView):
    queryset = CalculationInput.objects.all()
    serializer_class = CalculationInputCreateSerializer
    throttle_classes = [CalculationInputThrottle]
