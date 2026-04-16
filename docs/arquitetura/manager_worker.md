# O Padrão Manager-Worker

No PaGé, as views são divididas por responsabilidade HTTP e de negócio.

## Panels (Manager)
- Arquivo padrão: `panels.py`.
- Responsabilidade: responder `GET` e montar contexto de tela.
- Regra: não mutar banco de dados.

## Actions (Router para Workers)
- Arquivo padrão: `actions.py`.
- Responsabilidade: responder `POST`, validar entrada e acionar serviços.
- Regra: não renderizar template; sempre redirecionar após sucesso/erro.

## Services/Helpers (Worker)
- Diretório padrão: `services/`.
- Responsabilidade: centralizar mutações, transições de estado e regras de domínio.
- Benefício: regras testáveis, reuso e menor acoplamento com camada web.
