from django.conf.urls import include
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from django.views.generic import RedirectView

from apps.calculations.views import GebruikersInvoerCreateView
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

router = DefaultRouter()


@login_required
def admin_redirect(request):
    return redirect("/admin")


def ok(request):
    return HttpResponse("OK", status=200)


admin.site.site_header = "Keuzewijzer Aardgasvrij - Admin"
admin.site.site_title = "Keuzewijzer Aardgasvrij - Administration"
admin.site.index_title = "Keuzewijzer Aardgasvrij - keuzewijzeraardgasvrij"

router.register(
    r"calculation-inputs",
    GebruikersInvoerCreateView,
    basename="calculationinput",
)

urlpatterns = [
    path("startup/", ok),
    path("", ok),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("admin/login/", admin_redirect),
    path("admin/", admin.site.urls),
    path(
        "api/v1/calculation-inputs/prefill/<str:bagId>/",
        GebruikersInvoerCreateView.as_view({"get": "prefill"}),
        name="calculationinput-prefill",
    ),
    path("api/v1/", include(router.urls)),
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
