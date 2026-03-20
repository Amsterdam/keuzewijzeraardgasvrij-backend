from rest_framework import generics

from .models import CalculationInput
from .serializers import CalculationInputCreateSerializer


from rest_framework.throttling import AnonRateThrottle


class DebugAnonThrottle(AnonRateThrottle):
    scope = "calculation_input"

    def get_ident(self, request):
        http_headers = {k: v for k, v in request.META.items()}
        print(http_headers)
        return super().get_ident(request)


class CalculationInputCreateView(generics.CreateAPIView):
    queryset = CalculationInput.objects.all()
    serializer_class = CalculationInputCreateSerializer
    throttle_classes = [DebugAnonThrottle]
