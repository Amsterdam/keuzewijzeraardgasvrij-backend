from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    def changelist_view(self, request, extra_context=None):
        if "is_active__exact" not in request.GET:
            q = request.GET.copy()
            q["is_active__exact"] = "1"
            request.GET = q
            request.META["QUERY_STRING"] = q.urlencode()
        return super().changelist_view(request, extra_context)

    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "last_login",
        "date_joined",
        "is_active",
    )
