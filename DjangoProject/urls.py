from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('DjangoProject.urlconf.core')),
    path('', include('DjangoProject.urlconf.fiscal')),
    path('', include('DjangoProject.urlconf.verbas')),
    path('', include('DjangoProject.urlconf.backoffice')),
    path('accounts/', include('django.contrib.auth.urls')),
]

if settings.DEBUG:
    urlpatterns += [path('', include('DjangoProject.urlconf.debug'))]

handler403 = 'django.views.defaults.permission_denied'
