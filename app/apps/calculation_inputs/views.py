from rest_framework import generics

from .models import CalculationInput
from .serializers import CalculationInputCreateSerializer


from rest_framework.throttling import AnonRateThrottle


class DebugAnonThrottle(AnonRateThrottle):
    scope = "calculation_input"

    def get_ident(self, request):
        meta = request.META

        xff = meta.get("HTTP_X_FORWARDED_FOR")
        real_ip = meta.get("HTTP_X_REAL_IP")
        remote_addr = meta.get("REMOTE_ADDR")
        test_ip = meta.get("X-APP-USER-IP")

        ident = super().get_ident(request)

        print(
            {
                "X_FORWARDED_FOR": xff,
                "X_REAL_IP": real_ip,
                "REMOTE_ADDR": remote_addr,
                "USED_IDENT": ident,
                "TEST_IP": test_ip,
            }
        )

        return ident


class CalculationInputCreateView(generics.CreateAPIView):
    queryset = CalculationInput.objects.all()
    serializer_class = CalculationInputCreateSerializer
    throttle_classes = [DebugAnonThrottle]
