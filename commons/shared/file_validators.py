"""Validadores compartilhados de arquivo para os apps de domínio."""

import magic
from django.core.exceptions import ValidationError


ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


def validar_arquivo_seguro(file):
    """
    Valida o tipo real do arquivo enviado com base em magic bytes.

    Aceita apenas arquivos PDF, JPEG e PNG. Lança ``ValidationError`` quando
    o MIME detectado não estiver na lista permitida ou quando a validação não
    puder ser executada.
    """
    if not file:
        return

    try:
        mime_type = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)
    except (magic.MagicException, OSError, TypeError, ValueError):
        raise ValidationError(
            "Não foi possível verificar o tipo do arquivo. "
            "Certifique-se de que o arquivo não está corrompido."
        )

    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"Formato de arquivo não permitido ou aparenta estar corrompido/adulterado "
            f"(tipo detectado: {mime_type}). "
            f"Apenas PDF, JPEG e PNG são aceitos."
        )


__all__ = ["ALLOWED_MIME_TYPES", "validar_arquivo_seguro"]
