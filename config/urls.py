from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

handler404 = "apps.core.views.custom_404_view"
handler403 = "apps.core.views.custom_403_view"
handler500 = "apps.core.views.custom_500_view"

admin.site.site_header = "FindIt Administration"
admin.site.site_title = "FindIt Admin"
admin.site.index_title = "Moderation and management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("apps.users.urls")),
    path("", include("apps.chat.urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.listings.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0]
    )

if settings.DEBUG or settings.SERVE_MEDIA_LOCALLY:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
