from django.shortcuts import render


def chaos_testing_view(request):
    """Ferramenta de caos para desenvolvimento baseada em gremlins.js.

    Renderiza página interativa para:
    - carregar URL alvo em iframe;
    - injetar gremlins.js via CDN e executar horda configurável;
    - copiar snippets de console para testes rápidos;
    - orientar correlação de erros HTTP 500 com logs do Django.

    A autenticação é aplicada globalmente pelo middleware de login.
    """
    return render(request, 'ferramentas/chaos_testing.html')
