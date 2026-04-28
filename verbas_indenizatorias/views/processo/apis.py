"""APIs POST para upload de documentos em verbas indenizatorias.

Este modulo concentra endpoints JSON usados pela interface para anexacao
de documentos em itens de verba e, quando aplicavel, na prestacao de contas.
"""

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import NoReverseMatch
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..shared.documents import (
    _obter_dados_upload_documento,
    _salvar_documento_upload,
)
from ..shared.registry import (
    _VERBA_CONFIG,
    _get_permissao_gestao_verba,
)
from ...services.documentos import obter_ou_criar_prestacao


@require_POST
def api_add_documento_verba(request, tipo_verba, pk):
    """Anexa um documento a uma verba e retorna payload JSON para a UI.

    Parametros:
        request: Requisicao HTTP POST com arquivo e tipo documental.
        tipo_verba: Chave canonica do tipo de verba registrada no catalogo.
        pk: Identificador da verba alvo para vinculacao do documento.

    Retorna:
        JsonResponse: Estrutura com `ok=True` e metadados do documento em
        sucesso; ou `ok=False` com mensagem de erro e status HTTP adequado.

    Levanta:
        PermissionDenied: Quando o usuario nao possui permissao de gestao da
        verba informada.
    """
    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        return JsonResponse({'ok': False, 'error': 'Tipo de verba invalido.'}, status=400)

    permissao = _get_permissao_gestao_verba(tipo_verba)
    if not permissao or not request.user.has_perm(permissao):
        raise PermissionDenied('Voce nao tem permissao para anexar documentos nesta verba.')

    modelo_verba = config['model']
    modelo_documento = config['doc_model']
    fk_name = config['doc_fk']
    tipo_doc_seguro = config['doc_tipo_seguro']
    verba = get_object_or_404(modelo_verba, id=pk)
    entidade_documento = obter_ou_criar_prestacao(verba) if fk_name == 'prestacao' else verba

    arquivo, tipo_id = _obter_dados_upload_documento(request)
    doc, erro = _salvar_documento_upload(
        entidade_documento,
        modelo_documento=modelo_documento,
        fk_name=fk_name,
        arquivo=arquivo,
        tipo_id=tipo_id,
    )
    if erro:
        status = 400 if 'Selecione um arquivo' in erro or 'Formato de arquivo' in erro else 500
        erro_api = erro.replace('Selecione um arquivo e um tipo de documento.', 'Arquivo e tipo de documento sao obrigatorios.')
        erro_api = erro_api.replace('Formato de arquivo não permitido. Use PDF, JPG ou PNG.', 'Formato nao permitido. Use PDF, JPG ou PNG.')
        return JsonResponse({'ok': False, 'error': erro_api}, status=status)

    try:
        arquivo_url = reverse('download_arquivo_seguro', args=[tipo_doc_seguro, doc.id])
        return JsonResponse({'ok': True, 'doc_id': doc.id, 'arquivo_url': arquivo_url, 'tipo': str(doc.tipo)})
    except NoReverseMatch as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
