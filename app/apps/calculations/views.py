from rest_framework import generics


from .models import GebruikersInvoer
from .serializers import GebruikersInvoerCreateSerializer


class GebruikersInvoerCreateView(generics.CreateAPIView):
    queryset = GebruikersInvoer.objects.all()
    serializer_class = GebruikersInvoerCreateSerializer
