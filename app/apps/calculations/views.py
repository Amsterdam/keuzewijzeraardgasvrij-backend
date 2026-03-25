from rest_framework import generics


from .models import CalculationInput
from .serializers import CalculationInputCreateSerializer


class CalculationInputCreateView(generics.CreateAPIView):
    queryset = CalculationInput.objects.all()
    serializer_class = CalculationInputCreateSerializer
