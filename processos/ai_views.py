from .ai_utils import extrair_dados_documento
from django.shortcuts import render
from django.http import JsonResponse
from .models import NotaFiscal

# 1. Apenas renderiza a página HTML
def ai_extraction_page_view(request):
    return render(request, 'ai_extraction_tool.html')

# 2. O endpoint da API que o JavaScript vai acessar
def api_testar_extracao(request):
    if request.method == 'POST':
        arquivo = request.FILES.get('documento')
        tipo_doc = request.POST.get('doc_type')

        if not arquivo:
            return JsonResponse({'erro': 'Nenhum arquivo recebido.'}, status=400)

        # Mapeia o texto do select do HTML para a Classe real do seu models.py
        modelo_alvo = None
        if tipo_doc == 'nota_fiscal':
            modelo_alvo = NotaFiscal
        else:
            return JsonResponse({'erro': 'Modelo não reconhecido.'}, status=400)

        # Chama o motor pesado no utils.py
        dados = extrair_dados_documento(arquivo, modelo_alvo)

        # Retorna o JSON bruto de volta para o JavaScript imprimir na tela
        if dados:
            return JsonResponse({'sucesso': True, 'modelo': tipo_doc, 'extracao_crua': dados})
        else:
            return JsonResponse({'erro': 'A IA não conseguiu processar este arquivo ou retornou erro.'}, status=500)

    return JsonResponse({'erro': 'Método não permitido.'}, status=405)