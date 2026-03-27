import json
import os

import requests
from requests.adapters import HTTPAdapter, Retry

AUTENTIQUE_API_URL = "https://api.autentique.com.br/v2/graphql"
AUTENTIQUE_API_TOKEN = os.getenv("AUTENTIQUE_API_TOKEN", "")


def _get_headers():
    return {"Authorization": f"Bearer {AUTENTIQUE_API_TOKEN}"}


def _get_robust_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def enviar_documento_para_assinatura(pdf_bytes, nome_doc, signatarios, entidade=None, tipo_documento=None, folder_id=None):
    """
    Sends a PDF document to the Autentique API for digital signature.
    If entidade and tipo_documento are provided, creates and returns an
    AssinaturaAutentique record. Otherwise returns the raw API response dict.
    """
    # Idempotency: return existing pending signature to prevent duplicates
    if entidade and tipo_documento:
        from django.contrib.contenttypes.models import ContentType
        from processos.models.fluxo import AssinaturaAutentique
        ct = ContentType.objects.get_for_model(entidade)
        assinatura_existente = AssinaturaAutentique.objects.filter(
            content_type=ct,
            object_id=entidade.id,
            tipo_documento=tipo_documento,
            status='PENDENTE',
        ).first()
        if assinatura_existente:
            return assinatura_existente

    # 1. The exact query from Autentique's documentation
    query = """
    mutation CreateDocumentMutation($document: DocumentInput!, $signers: [SignerInput!]!, $file: Upload!, $folderId: String) {
      createDocument(document: $document, signers: $signers, file: $file, folderId: $folderId) {
        id
        name
        signatures {
          public_id
          link {
            short_link
          }
        }
      }
    }
    """

    # 2. Use proper GraphQL variables to avoid string-escaping bugs
    variables = {
        "document": {
            "name": nome_doc
        },
        "signers": signatarios,
        "file": None
    }

    if folder_id:
        variables["folder_id"] = folder_id

    operations = json.dumps({
        "query": query,
        "variables": variables
    })

    # 3. The multipart map linking the physical file to the "file" variable
    map_dict = json.dumps({
        "0": ["variables.file"]
    })

    # 4. The multipart payload
    files = {
        "operations": (None, operations),
        "map": (None, map_dict),
        "0": (f"{nome_doc}.pdf", pdf_bytes, "application/pdf"),
    }

    response = _get_robust_session().post(
        AUTENTIQUE_API_URL,
        headers=_get_headers(),
        files=files,
        timeout=15,
    )
    
    response.raise_for_status()
    data = response.json()
    
    if "errors" in data:
        raise Exception(f"Autentique API error: {data['errors']}")

    doc = data["data"]["createDocument"]
    doc_id = doc["id"]

    url = ""
    if doc.get("signatures"):
        link = doc["signatures"][0].get("link", {})
        url = link.get("short_link", "")

    if entidade is not None and tipo_documento is not None:
        from django.contrib.contenttypes.models import ContentType
        from processos.models.fluxo import AssinaturaAutentique

        assinatura = AssinaturaAutentique.objects.create(
            content_type=ContentType.objects.get_for_model(entidade),
            object_id=entidade.id,
            tipo_documento=tipo_documento,
            autentique_id=doc_id,
            autentique_url=url,
        )
        return assinatura

    return {"id": doc_id, "url": url}


def verificar_e_baixar_documento(autentique_id):
    """
    Checks the signature status of a document on Autentique and downloads
    the signed PDF if all signatures are complete.

    Args:
        autentique_id (str): The document ID on Autentique.

    Returns:
        dict: A dict with:
            - 'assinado' (bool): True if the document is fully signed.
            - 'pdf_bytes' (bytes or None): The signed PDF bytes if assinado is True.

    Raises:
        Exception: If the API call fails or returns an error.
    """
    query = """
    query GetDocument($id: UUID!) {
      document(id: $id) {
        id
        name
        files {
          signed
        }
        signatures {
          signed {
            created_at
          }
          link {
            short_link
          }
        }
      }
    }
    """

    response = _get_robust_session().post(
        AUTENTIQUE_API_URL,
        headers=_get_headers(),
        json={"query": query, "variables": {"id": autentique_id}},
        timeout=15,
    )
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        raise Exception(f"Autentique API error: {data['errors']}")

    doc = data["data"]["document"]
    signatures = doc.get("signatures", [])

    all_signed = bool(signatures) and all(
        sig.get("signed") is not None for sig in signatures
    )

    if not all_signed:
        return {"assinado": False, "pdf_bytes": None}

    files = doc.get("files") or []
    signed_file_url = files[0].get("signed") if files else None
    if not signed_file_url:
        return {"assinado": False, "pdf_bytes": None}

    pdf_response = _get_robust_session().get(signed_file_url, timeout=15)
    pdf_response.raise_for_status()

    return {"assinado": True, "pdf_bytes": pdf_response.content}
