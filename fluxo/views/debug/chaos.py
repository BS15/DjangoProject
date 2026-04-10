from django.shortcuts import render


def chaos_testing_view(request):
    """Ferramenta de caos para desenvolvimento baseada em gremlins.js."""
    return render(request, 'ferramentas/chaos_testing.html')
