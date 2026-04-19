"""Regras de acesso para prestação de contas de diárias."""


def _pode_acessar_prestacao(request_user, diaria):
	"""Retorna True para credor vinculado ou operador financeiro autorizado."""
	credor = diaria.beneficiario
	if hasattr(credor, 'usuario') and credor.usuario and credor.usuario == request_user:
		return True
	return request_user.has_perm('verbas_indenizatorias.operar_prestacao_contas')


__all__ = ["_pode_acessar_prestacao"]
