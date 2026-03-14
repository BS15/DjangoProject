from .ai_utils import extrair_dados_documento
from django.shortcuts import render
from django.http import JsonResponse

# Mapa de tipos do formulário para os identificadores usados pelo motor de extração
TIPO_DOC_MAP = {
    'nota_fiscal': 'NOTA FISCAL (NF)',
    'orcamentario': 'DOCUMENTOS ORÇAMENTÁRIOS',
    'boleto': 'BOLETO BANCÁRIO',
}

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

        tipo_extracao = TIPO_DOC_MAP.get(tipo_doc)
        if not tipo_extracao:
            return JsonResponse({'erro': 'Tipo de documento não reconhecido.'}, status=400)

        try:
            # Chama o motor de extração com o tipo correto (string)
            dados = extrair_dados_documento(arquivo, tipo_extracao)
        except Exception as e:
            return JsonResponse({'erro': f'Erro interno na extração: {str(e)}'}, status=500)

        # Retorna o JSON bruto de volta para o JavaScript imprimir na tela
        if dados:
            return JsonResponse({'sucesso': True, 'tipo': tipo_doc, 'extracao_crua': dados})
        else:
            return JsonResponse({'erro': 'A IA não conseguiu processar este arquivo ou retornou erro.'}, status=500)

    return JsonResponse({'erro': 'Método não permitido.'}, status=405)