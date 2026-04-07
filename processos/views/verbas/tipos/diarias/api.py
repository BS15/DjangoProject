from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse

from .....models import Credor, Tabela_Valores_Unitarios_Verbas_Indenizatorias


@permission_required('processos.pode_criar_diarias', raise_exception=True)
def api_valor_unitario_diaria(request, beneficiario_id):
    try:
        credor = Credor.objects.select_related('cargo_funcao').get(id=beneficiario_id)

        if not credor.cargo_funcao_id:
            return JsonResponse({'sucesso': False, 'erro': 'Beneficiario sem cargo/funcao definido', 'valor_unitario': None})

        valor_unitario = Tabela_Valores_Unitarios_Verbas_Indenizatorias.get_valor_para_cargo_diaria(credor.cargo_funcao)

        if valor_unitario is not None:
            return JsonResponse(
                {
                    'sucesso': True,
                    'valor_unitario': str(valor_unitario),
                    'cargo_funcao': str(credor.cargo_funcao),
                }
            )
        return JsonResponse(
            {
                'sucesso': False,
                'erro': 'Nenhum valor unitario cadastrado para este cargo/funcao',
                'valor_unitario': None,
            }
        )
    except Credor.DoesNotExist:
        return JsonResponse({'sucesso': False, 'erro': 'Beneficiario nao encontrado', 'valor_unitario': None})
