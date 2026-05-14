"""Roteador raiz do projeto — agrega todos os sub-roteadores por domínio."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.pagamentos.urls')),
    path('retencoes/', include('apps.retencoes.urls')),
    path('verbas/', include('apps.verbas_indenizatorias.urls')),
    path('suprimentos/', include('apps.suprimentos.urls')),
    path('cadastros/', include('apps.cadastros.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('desenvolvedor/', include('apps.desenvolvedor.urls')),
        path('__debug__/', include(debug_toolbar.urls)),
    ]

handler403 = 'django.views.defaults.permission_denied'
