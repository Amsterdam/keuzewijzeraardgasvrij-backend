from django.conf.urls import include
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from django.views.generic import RedirectView

from apps.calculations.views import CalculationInputCreateView


router = DefaultRouter()


def ok(request):
    return HttpResponse("OK", status=200)


admin.site.site_header = "Keuzewijzer Aardgasvrij - Admin"
admin.site.site_title = "Keuzewijzer Aardgasvrij - Administration"
admin.site.index_title = "Keuzewijzer Aardgasvrij - keuzewijzeraardgasvrij"


urlpatterns = [
    path("startup/", ok),
    path("", ok),
    path("admin/", admin.site.urls),
    path("api/v1/", include(router.urls)),
    path(
        "api/v1/calculation-inputs/",
        CalculationInputCreateView.as_view(),
        name="calculationinput-create",
    ),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        ".well-known/security.txt",
        RedirectView.as_view(url="https://www.amsterdam.nl/.well-known/security.txt"),
    ),
]
