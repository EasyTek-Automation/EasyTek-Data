# src/utils/email_templates.py

"""
Camada genérica de e-mail baseada em template (Jinja2).

Fina camada de renderização por cima de `email_sender.send_email`: você passa
um `assunto` + um `dict` de parâmetros (`contexto`) e envia um e-mail HTML
informativo. Um único template genérico (`email_base.html`) atende vários
tipos de e-mail só mudando o contexto; para um layout próprio, aponte um
template nomeado via `template=`.

Config do Gmail e SMTP são reaproveitados de `email_sender`/`email_config` —
aqui só se cuida da renderização do corpo.

Exemplo:
    from src.utils.email_templates import enviar_email_template

    enviar_email_template(
        assunto="[AMG] Parada atingiu o gatilho — LCT08",
        contexto={
            "titulo": "Parada crítica detectada",
            "paragrafos": ["Uma parada atingiu o gatilho configurado."],
            "itens": [{"label": "Equipamento", "valor": "LCT08"}],
        },
    )
"""

import os
import logging
from functools import lru_cache

from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
    TemplateNotFound,
    TemplateSyntaxError,
    UndefinedError,
)

from src.utils.email_sender import send_email

logger = logging.getLogger(__name__)

# Caminho relativo ao CWD do processo (no container é /app), mesmo padrão do
# template DOCX do KPIReport. Override por env cobre CWD diferente.
TEMPLATES_DIR_DEFAULT = "src/assets/templates"
EMAIL_TEMPLATE_DEFAULT = "email_base.html"
ENV_TEMPLATES_DIR = "EMAIL_TEMPLATES_DIR"

# Rodapé padrão (disclaimer de MVP) injetado em todo e-mail templated que não
# passar um `rodape` próprio no contexto.
RODAPE_PADRAO = (
    "Este é um e-mail de teste, apenas para validação de um MVP. "
    "Os valores aqui contidos não devem ser considerados oficiais e precisam "
    "ser revisados. Dúvidas: rodolfo@tekmont.com.br ou rgustavo32@hotmail.com."
)


class TemplateLoadError(Exception):
    """Falha ao localizar ou renderizar um template de e-mail HTML."""

    def __init__(self, template, original):
        super().__init__(
            f"Falha no template de e-mail '{template}' ({type(original).__name__})"
        )
        self.template = template
        self.original = original


def _resolve_templates_dir() -> str:
    """Diretório dos templates: env EMAIL_TEMPLATES_DIR se for dir válido, senão o default."""
    override = os.environ.get(ENV_TEMPLATES_DIR, "").strip()
    if override and os.path.isdir(override):
        return override
    return TEMPLATES_DIR_DEFAULT


@lru_cache(maxsize=1)
def _get_env() -> Environment:
    """
    Environment Jinja2 cacheado (autoescape ligado → valores do contexto escapados).

    Em testes que trocam EMAIL_TEMPLATES_DIR, chame `_get_env.cache_clear()` para
    forçar a reconstrução apontando para o novo diretório.
    """
    return Environment(
        loader=FileSystemLoader(_resolve_templates_dir()),
        autoescape=select_autoescape(["html", "htm", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_email(contexto: dict, template: str | None = None) -> str:
    """
    Renderiza um template HTML de e-mail com o `contexto` e retorna a string HTML.

    Função pura (não envia nada) — permite testar a renderização isolada.
    `template` None usa o genérico `email_base.html`. Falhas de template
    (inexistente, sintaxe, variável indefinida) viram `TemplateLoadError`.
    """
    nome = template or EMAIL_TEMPLATE_DEFAULT
    try:
        tmpl = _get_env().get_template(nome)
        return tmpl.render(**contexto)
    except (TemplateNotFound, TemplateSyntaxError, UndefinedError) as exc:
        raise TemplateLoadError(nome, exc) from exc


def enviar_email_template(
    assunto: str,
    contexto: dict,
    to: str | None = None,
    template: str | None = None,
    raise_on_error: bool = False,
) -> bool:
    """
    Renderiza um template HTML com `contexto` e envia via `send_email(html=True)`.

    Ponto único de entrada para e-mails informativos: passe assunto + um dict de
    parâmetros e (opcional) o nome de um template. Sem `template` usa o genérico.

    Não levanta por padrão (falha de template OU de SMTP → loga e retorna False),
    para não derrubar o fluxo de quem chama. `raise_on_error=True` propaga.
    Herda de `send_email`: `to=None` usa EMAIL_TO_DEFAULT; EMAIL_ENABLED=0 não envia.
    O rodapé disclaimer (RODAPE_PADRAO) entra por default se `contexto` não trouxer
    `rodape` próprio.
    """
    contexto = {**(contexto or {})}
    contexto.setdefault("rodape", RODAPE_PADRAO)
    try:
        corpo_html = render_email(contexto, template)
    except TemplateLoadError as exc:
        logger.error(
            "Falha ao renderizar template de e-mail '%s': %s",
            template or EMAIL_TEMPLATE_DEFAULT, exc,
        )
        if raise_on_error:
            raise
        return False

    return send_email(
        assunto=assunto, corpo=corpo_html, to=to,
        html=True, raise_on_error=raise_on_error,
    )
