"""Cliente de integração com a API da Autentique (módulo compartilhado)."""

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
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def enviar_documento_para_assinatura(pdf_bytes, nome_doc, signatarios, folder_id=None):
    """Envia PDF para assinatura digital na API da Autentique."""
    query = """
    mutation CreateDocumentMutation($document: DocumentInput!, $signers: [SignerInput!]!, $file: Upload!, $folder_id: UUID) {
        createDocument(document: $document, signers: $signers, file: $file, folder_id: $folder_id) {
            id
            name
            signatures {
                public_id
                name
                email
                link {
                    short_link
                }
            }
        }
    }
    """

    variables = {
        "document": {"name": nome_doc},
        "signers": signatarios,
        "file": None,
    }
    if folder_id:
        variables["folder_id"] = folder_id

    operations = json.dumps({"query": query, "variables": variables})
    map_dict = json.dumps({"0": ["variables.file"]})
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

    signers_data = {}
    for sig in doc.get("signatures", []):
        email = sig.get("email")
        link_obj = sig.get("link") or {}
        if email:
            signers_data[email] = {
                "public_id": sig.get("public_id"),
                "name": sig.get("name"),
                "short_link": link_obj.get("short_link", ""),
            }

    url = ""
    if doc.get("signatures"):
        link = doc["signatures"][0].get("link") or {}
        url = link.get("short_link", "")

    return {"id": doc_id, "url": url, "signers_data": signers_data}


def verificar_e_baixar_documento(autentique_id):
    """Verifica status de assinatura de um documento na Autentique."""
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
    all_signed = bool(signatures) and all(sig.get("signed") is not None for sig in signatures)
    if not all_signed:
        return {"assinado": False, "pdf_bytes": None}

    files = doc.get("files") or []
    signed_file_url = files[0].get("signed") if files else None
    if not signed_file_url:
        return {"assinado": False, "pdf_bytes": None}

    pdf_response = _get_robust_session().get(signed_file_url, timeout=15)
    pdf_response.raise_for_status()

    return {"assinado": True, "pdf_bytes": pdf_response.content}


__all__ = ["enviar_documento_para_assinatura", "verificar_e_baixar_documento"]
