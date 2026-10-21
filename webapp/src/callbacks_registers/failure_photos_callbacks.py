# src/callbacks_registers/failure_photos_callbacks.py

"""
Callbacks da galeria de fotos da Análise de Falhas (DS-07 do SDD analise-falhas-fotos).

A fonte de verdade das fotos é o Mongo (campo `fotos` da análise). Os callbacks:
- semeiam `store-fa-fotos` + o id da análise + a visibilidade da área de upload no load;
- recarregam do Mongo quando o JS bumpa `store-fa-fotos-refresh` (após upload/exclusão);
- renderizam a grade de miniaturas (cada uma serve pela rota Flask, não do disco do app).

As ações (upload/excluir/legenda) são feitas por `fetch` no JS contra as rotas Flask
(Bloco B); aqui só há leitura e render.
"""

from dash import ALL, Input, Output, State, html, no_update
from flask_login import current_user

from src.utils import failure_analysis_db as fdb
from src.utils import failure_photos_storage as storage

NIVEL_UPLOAD = 2
NIVEL_ADMIN = 3


def _username() -> str:
    return str(getattr(current_user, "username", "") or "")


def _nivel() -> int:
    try:
        return int(getattr(current_user, "level", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _pode_subir(analise) -> bool:
    """Subir exige análise aberta e nível ≥ 2 (a página já é perfil manutenção)."""
    if not analise or analise.get("status") != fdb.STATUS_ABERTA:
        return False
    return _nivel() >= NIVEL_UPLOAD


def _card(foto, aid, pode_excluir):
    """Uma miniatura da grade: img servida pela rota, legenda e (se permitido) excluir."""
    fid = foto.get("id")
    # `rev` incrementa a cada edição (rotação) → cache-buster do <img>, já que o nome
    # do arquivo não muda mas o conteúdo sim.
    rev = foto.get("rev", 0)
    thumb_url = f"/api/failure-analysis/{aid}/photos/{fid}/thumb?v={rev}"
    full_url = f"/api/failure-analysis/{aid}/photos/{fid}/full?v={rev}"
    filhos = [
        html.Img(
            src=thumb_url, className="fa-foto-thumb",
            **{"data-full": full_url, "data-id": fid,
               "data-legenda": foto.get("legenda") or "",
               "data-aid": aid},
        ),
        html.Div(foto.get("legenda") or "", className="fa-foto-legenda",
                 title=foto.get("legenda") or ""),
    ]
    if pode_excluir:
        filhos.append(html.Button(
            html.I(className="bi bi-trash"), className="fa-foto-del",
            title="Excluir foto", **{"data-id": fid, "data-aid": aid}))
    return html.Div(filhos, className="fa-foto-card")


def register_failure_photos_callbacks(app):
    """Registra os callbacks da galeria de fotos."""

    @app.callback(
        Output("store-fa-fotos", "data"),
        Output("fa-fotos-aid", "children"),
        Output("fa-fotos-upload-area", "style"),
        Output("fa-fotos-ref", "children"),
        Input("store-fa-analise", "data"),
    )
    def _semear(analise):
        """No load: semeia a lista de fotos, expõe o id da análise para o JS, mostra
        ou esconde a área de upload conforme permissão/estado, e monta a referência
        discreta (pasta no file server + id) para localizar as fotos fora do app."""
        if not analise:
            return [], "", {"display": "none"}, ""
        fotos = analise.get("fotos") or []
        estilo = ({} if _pode_subir(analise)
                  else {"display": "none"})
        ref = html.Span([
            html.I(className="bi bi-folder2 me-1"),
            "pasta no servidor: ",
            html.Code(storage.subpasta_rel(analise), className="text-muted"),
            "  ·  id: ",
            html.Code(analise.get("id") or "", className="text-muted"),
        ])
        return fotos, analise.get("id") or "", estilo, ref

    @app.callback(
        Output("store-fa-fotos", "data", allow_duplicate=True),
        Input("store-fa-fotos-refresh", "data"),
        State("store-fa-analise", "data"),
        prevent_initial_call=True,
    )
    def _refresh(_bump, analise):
        """Recarrega as fotos do Mongo após upload/exclusão (o JS bumpa o refresh)."""
        if not analise or not analise.get("id"):
            return no_update
        return fdb.listar_fotos(analise["id"])

    @app.callback(
        Output("fa-fotos-grid", "children"),
        Output("fa-fotos-contador", "children"),
        Input("store-fa-fotos", "data"),
        State("store-fa-analise", "data"),
    )
    def _grid(fotos, analise):
        """Redesenha a grade a partir de `store-fa-fotos`."""
        fotos = fotos or []
        aid = (analise or {}).get("id") or ""
        contador = f"{len(fotos)}/{fdb.MAX_FOTOS}"
        if not fotos:
            vazio = html.Div("Nenhuma foto ainda.", className="text-muted small py-2")
            return vazio, contador
        usuario, nivel = _username(), _nivel()
        cards = []
        for f in fotos:
            pode_excluir = (f.get("enviada_por") == usuario) or (nivel >= NIVEL_ADMIN)
            cards.append(_card(f, aid, pode_excluir))
        return cards, contador
