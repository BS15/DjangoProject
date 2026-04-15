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


@require_POST
def api_add_documento_verba(request, tipo_verba, pk):
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

    arquivo, tipo_id = _obter_dados_upload_documento(request)
    doc, erro = _salvar_documento_upload(
        verba,
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
