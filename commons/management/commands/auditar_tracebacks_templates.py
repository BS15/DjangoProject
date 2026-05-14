from __future__ import annotations

import json
import re
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client
from django.test.utils import override_settings
from django.urls import URLPattern, URLResolver, get_resolver


_PARAM_RE = re.compile(r"<(?:(?P<conv>[^>:]+):)?(?P<name>[^>]+)>")
_SAMPLE_VALUES = {
    "int": "1",
    "slug": "sample-slug",
    "str": "sample",
    "uuid": "00000000-0000-0000-0000-000000000000",
    "path": "sample/path",
}


@dataclass
class AuditResult:
    path: str
    source: str
    status: str
    http_status: int | None
    exception_type: str | None
    exception_message: str | None
    traceback_text: str | None


def _iter_patterns(prefix: str, patterns: list[URLPattern | URLResolver]):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            route = str(entry.pattern)
            yield from _iter_patterns(prefix + route, entry.url_patterns)
            continue

        if isinstance(entry, URLPattern):
            route = str(entry.pattern)
            source = f"{entry.lookup_str}"
            yield (prefix + route, source)


def _materialize_path(route: str) -> str | None:
    if route.startswith("^"):
        return None

    raw = route.replace("\\Z", "").replace("$", "")

    def _replace(match: re.Match[str]) -> str:
        converter = match.group("conv") or "str"
        return _SAMPLE_VALUES.get(converter, "sample")

    materialized = _PARAM_RE.sub(_replace, raw)
    if not materialized.startswith("/"):
        materialized = "/" + materialized
    return materialized


def _should_skip(path: str) -> bool:
    skip_prefixes = (
        "/admin/",
        "/static/",
        "/media/",
    )
    return path.startswith(skip_prefixes)


class Command(BaseCommand):
    help = (
        "Audita endpoints GET para identificar tracebacks de renderizacao/template sem navegar manualmente por cada tela."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="traceback_audit_report.json",
            help="Caminho do arquivo JSON de saida.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"])

        # Guarantee host validation compatibility with Django test client defaults.
        allowed_hosts = list(settings.ALLOWED_HOSTS)
        for host in ("testserver", "localhost", "127.0.0.1"):
            if host not in allowed_hosts:
                allowed_hosts.append(host)

        User = get_user_model()
        user, _ = User.objects.get_or_create(
            username="traceback_audit_user",
            defaults={"is_staff": True, "is_superuser": True, "email": "traceback-audit@example.com"},
        )
        if not user.is_staff or not user.is_superuser:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])

        with override_settings(ALLOWED_HOSTS=allowed_hosts):
            client = Client(HTTP_HOST="localhost")
            client.force_login(user)

            resolver = get_resolver()
            candidates = []
            seen_paths = set()

            for route, source in _iter_patterns("", resolver.url_patterns):
                path = _materialize_path(route)
                if not path or _should_skip(path):
                    continue
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                candidates.append((path, source))

            self.stdout.write(f"Auditando {len(candidates)} endpoints GET...")

            results: list[AuditResult] = []
            for path, source in candidates:
                try:
                    response = client.get(path, HTTP_HOST="localhost")
                    if response.status_code >= 500:
                        results.append(
                            AuditResult(
                                path=path,
                                source=source,
                                status="server_error",
                                http_status=response.status_code,
                                exception_type=None,
                                exception_message=f"HTTP {response.status_code} sem excecao propagada",
                                traceback_text=None,
                            )
                        )
                    elif response.status_code >= 400:
                        results.append(
                            AuditResult(
                                path=path,
                                source=source,
                                status="client_error",
                                http_status=response.status_code,
                                exception_type=None,
                                exception_message=f"HTTP {response.status_code}",
                                traceback_text=None,
                            )
                        )
                    else:
                        results.append(
                            AuditResult(
                                path=path,
                                source=source,
                                status="ok",
                                http_status=response.status_code,
                                exception_type=None,
                                exception_message=None,
                                traceback_text=None,
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        AuditResult(
                            path=path,
                            source=source,
                            status="exception",
                            http_status=None,
                            exception_type=type(exc).__name__,
                            exception_message=str(exc),
                            traceback_text=traceback.format_exc(),
                        )
                    )

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "debug": settings.DEBUG,
            "total_paths": len(results),
            "ok": sum(1 for item in results if item.status == "ok"),
            "client_error": sum(1 for item in results if item.status == "client_error"),
            "server_error": sum(1 for item in results if item.status == "server_error"),
            "exceptions": sum(1 for item in results if item.status == "exception"),
        }

        payload = {
            "summary": summary,
            "results": [item.__dict__ for item in results],
        }

        output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Relatorio salvo em: {output_path}"))
        self.stdout.write(
            self.style.WARNING(
                "Resumo: "
                f"ok={summary['ok']}, "
                f"client_error={summary['client_error']}, "
                f"server_error={summary['server_error']}, "
                f"exceptions={summary['exceptions']}"
            )
        )

        for item in results:
            if item.status == "ok":
                continue
            self.stdout.write(
                self.style.ERROR(
                    f"[{item.status}] {item.path} -> {item.exception_type or item.http_status}: {item.exception_message or ''}"
                )
            )
