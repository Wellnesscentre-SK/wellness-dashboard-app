"""URL configuration for the Wellness Centre Analytics Dashboard."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def index(request):
    return JsonResponse({
        "service": "Wellness Centre Analytics Dashboard",
        "status": "ok",
        "api": "/api/",
        "admin": "/admin/",
    })


urlpatterns = [
    path("", index, name="index"),
    path("health/", index, name="health"),
    path("admin/", admin.site.urls),
    path("api/", include("wellness.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
