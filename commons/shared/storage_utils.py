"""
Utilidades genéricas para gerenciamento de arquivos (upload paths, limpeza de storage).
Utilizadas por múltiplos apps (fluxo, verbas_indenizatorias, suprimentos, etc).
"""
import logging
from pathlib import PurePosixPath

from django.utils.text import get_valid_filename

logger = logging.getLogger(__name__)


def _safe_filename(filename):
	"""Normaliza o nome do arquivo para evitar caminhos aninhados acidentais."""
	base_name = PurePosixPath(filename or "arquivo").name
	clean_name = get_valid_filename(base_name)
	return clean_name or "arquivo"


def _build_upload_path(*parts):
	"""Monta caminho relativo POSIX para uso em FileField.upload_to."""
	clean_parts = []
	for part in parts:
		if part is None:
			continue
		part_str = str(part).strip().strip("/")
		if part_str:
			clean_parts.append(part_str)
	return "/".join(clean_parts)


def _processo_year(processo):
	"""Resolve ano de particionamento do processo com fallback estável."""
	if getattr(processo, "data_empenho", None):
		return processo.data_empenho.year
	return processo.ano_exercicio or 9999


def caminho_documento(instance, filename):
	"""
	Resolve o diretório de upload conforme entidade de negócio vinculada.
	
	Suporte para:
	- Processo (pagamentos)
	- Diaria (verbas indenizatórias)
	- Reembolso (verbas indenizatórias)
	- Jeton (verbas indenizatórias)
	- Auxilio (verbas indenizatórias)
	- Suprimento (suprimentos de fundos)
	- DespesaSuprimento (despesas de suprimentos)
	- Documentos avulsos
	
	Args:
		instance: objeto de modelo com relacionamento a entidade de negócio
		filename: nome do arquivo original
		
	Returns:
		str: caminho relativo para upload
	"""
	filename = _safe_filename(filename)

	if hasattr(instance, 'processo') and instance.processo:
		return _build_upload_path(
			'pagamentos',
			_processo_year(instance.processo),
			f'proc_{instance.processo.id}',
			filename,
		)

	if hasattr(instance, 'prestacao') and instance.prestacao:
		return _build_upload_path('verbasindenizatorias', 'prestacoes', f'prestacao_{instance.prestacao.id}', filename)

	if hasattr(instance, 'diaria') and instance.diaria:
		return _build_upload_path('verbasindenizatorias', 'diarias', f'diaria_{instance.diaria.id}', filename)
	if hasattr(instance, 'reembolso') and instance.reembolso:
		return _build_upload_path('verbasindenizatorias', 'reembolsos', f'reembolso_{instance.reembolso.id}', filename)
	if hasattr(instance, 'jeton') and instance.jeton:
		return _build_upload_path('verbasindenizatorias', 'jetons', f'jeton_{instance.jeton.id}', filename)
	if hasattr(instance, 'auxilio') and instance.auxilio:
		return _build_upload_path('verbasindenizatorias', 'auxilios', f'auxilio_{instance.auxilio.id}', filename)

	if instance.__class__.__name__ == 'DespesaSuprimento':
		return _build_upload_path('suprimentosdefundos', f'suprimento_{instance.suprimento.id}', 'despesas', filename)

	if hasattr(instance, 'suprimento') and instance.suprimento:
		return _build_upload_path('suprimentosdefundos', f'suprimento_{instance.suprimento.id}', filename)

	return _build_upload_path('documentos_avulsos', filename)


def _delete_file(file_field):
	"""
	Remove arquivo do storage, ignorando erros quando inexistente.
	
	Útil para cleanup de campos FileField quando registros são deletados.
	
	Args:
		file_field: campo FileField do Django
	"""
	if file_field and file_field.name:
		try:
			file_field.storage.delete(file_field.name)
		except (FileNotFoundError, OSError) as exc:
			logger.warning(
				"Falha ao remover arquivo '%s' do storage: %s",
				file_field.name,
				exc,
			)


__all__ = [
	"caminho_documento",
	"_delete_file",
]
