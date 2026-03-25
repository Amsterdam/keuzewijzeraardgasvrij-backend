from rest_framework import generics


from .models import CalculationInput
from .serializers import CalculationInputCreateSerializer


class CalculationInputCreateView(generics.CreateAPIView):
    queryset = CalculationInput.objects.all()
    serializer_class = CalculationInputCreateSerializer

    # def post(self, request, *args, **kwargs):
    #     serializer = self.get_serializer(data=request.data, context={"request": request})
    #     if not serializer.is_valid():
    #         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    #     self.perform_create(serializer)
    #     calculation_input = serializer.instance

    #     calculator = EnergieCalculator()
    #     scenario = ScenarioKeuze.LAAG
    #     energie_type = EnergieType.GKW
    #     result = calculator.calculate(energie_type, scenario, calculation_input)
    #     return Response(result, status=status.HTTP_201_CREATED)
