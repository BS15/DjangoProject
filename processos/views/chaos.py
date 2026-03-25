from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def chaos_testing_view(request):
    """Developer chaos-testing tool powered by gremlins.js.

    Renders an interactive page that lets a developer:
    - Load any target URL (add_process, conferencia_processo) inside an iframe
    - Inject gremlins.js (via CDN) into that iframe and fire a configurable horde
    - Copy ready-made browser-console snippets for quick in-page injection
    - Follow the inline guide to correlate server-side 500 errors with Django logs

    Access is restricted to authenticated users only.
    """
    return render(request, 'ferramentas/chaos_testing.html')
