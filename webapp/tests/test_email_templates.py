"""Testes do módulo de e-mail baseado em template (utils/email_templates.py).

Render-only não toca em rede. Os testes de envio mockam `send_email`.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.utils.email_templates import (
    render_email,
    enviar_email_template,
    TemplateLoadError,
)


# ---------- Render (sem rede) ----------

def test_render_inclui_titulo_e_paragrafos():
    """Título e parágrafos passados aparecem no HTML."""
    html = render_email({"titulo": "Aviso X", "paragrafos": ["linha um", "linha dois"]})
    assert "Aviso X" in html
    assert "linha um" in html
    assert "linha dois" in html


def test_render_tabela_itens():
    """Itens (label/valor) aparecem como linhas da tabela de detalhes."""
    html = render_email({"titulo": "T", "itens": [{"label": "Equip", "valor": "LCT08"}]})
    assert "Equip" in html
    assert "LCT08" in html


def test_render_escapa_html():
    """Segurança: valores do contexto são escapados (sem injeção de tags)."""
    html = render_email({"titulo": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_blocos_opcionais_ausentes():
    """Só com `titulo` não levanta e omite tabela/CTA."""
    html = render_email({"titulo": "Só título"})
    assert "Só título" in html
    assert "href=" not in html  # sem botão de ação


def test_render_cta():
    """Ação com url gera botão com href e texto."""
    html = render_email({"titulo": "T", "acao": {"texto": "Abrir", "url": "http://x/y"}})
    assert 'href="http://x/y"' in html
    assert "Abrir" in html


def test_render_template_inexistente_levanta():
    """Template inexistente vira TemplateLoadError com o nome tentado."""
    with pytest.raises(TemplateLoadError) as exc:
        render_email({"titulo": "T"}, template="nao_existe.html")
    assert exc.value.template == "nao_existe.html"


def test_render_rodape_default():
    """Sem `rodape` no contexto, o template cai no rodapé disclaimer padrão (MVP)."""
    html = render_email({"titulo": "T"})
    assert "validação de um MVP" in html
    assert "rodolfo@tekmont.com.br" in html


# ---------- Envio (mock de send_email) ----------

def test_enviar_email_template_chama_send_email_html():
    """Renderiza e delega para send_email com html=True e corpo renderizado."""
    with patch("src.utils.email_templates.send_email", return_value=True) as m:
        ok = enviar_email_template("[AMG] T", {"titulo": "Título Teste"})

    assert ok is True
    m.assert_called_once()
    assert m.call_args.kwargs["html"] is True
    assert "Título Teste" in m.call_args.kwargs["corpo"]


def test_enviar_email_template_falha_template_retorna_false():
    """Template inexistente com raise_on_error=False → False e não chama send_email."""
    with patch("src.utils.email_templates.send_email") as m:
        ok = enviar_email_template("[AMG] T", {"titulo": "T"}, template="nope.html")

    assert ok is False
    m.assert_not_called()
