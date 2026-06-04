"""URL config racine SIRH ACEP."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls', namespace='core')),
    path('organisation/', include('apps.organization.urls', namespace='organization')),
    path('employes/', include('apps.employees.urls', namespace='employees')),
    path('pointage/', include('apps.attendance.urls', namespace='attendance')),
    path('plannings/', include('apps.planning.urls', namespace='planning')),
    path('reporting/', include('apps.reporting.urls', namespace='reporting')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
