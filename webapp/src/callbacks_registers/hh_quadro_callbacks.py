# -*- coding: utf-8 -*-
"""Callbacks do quadro semanal de Hora-Homem (aba do backlog) — Bloco B5.

Render server-side do quadro (disciplina→técnico×dia + a-planejar), navegação de semana,
persistência do drag-and-drop (grava hh_planejamento — estado local), injeção do nível do
usuário (gating de edição — SP-11) e "Atualizar agora" (dispara os jobs hh_* — SP-10.6).
Estado local nunca vai ao SAP (BR-11).
"""
from datetime import datetime

import pytz
import dash_bootstrap_components as dbc
from dash import Output, Input, State, ctx, dcc, html, no_update, ALL
from dash.exceptions import PreventUpdate
from flask_login import current_user

try:
    from src.utils import hh_data
    from src.utils import plano_semanal_pdf
    from src.utils import plano_semanal_xlsx
    from src.pages.maintenance import hh_quadro
    from src.sap_scheduler.manual_trigger import inserir_job_manual
    from src.database.connection import get_mongo_connection
except ImportError:
    from utils import hh_data
    from utils import plano_semanal_pdf
    from utils import plano_semanal_xlsx
    from pages.maintenance import hh_quadro
    from sap_scheduler.manual_trigger import inserir_job_manual
    from database.connection import get_mongo_connection

_TZ = "America/Sao_Paulo"
_MIN_LEVEL_EDIT = 2        # PCM (atribuir/replanejar) — SP-11

# "Atualizar agora" (BR-09): dispara a coleta que alimenta o quadro. O universo do quadro vem do
# `sap_backlog` (B13), então **backlog é obrigatório** aqui — sem ele, ordem/nota nova editada pelo
# PCM não aparece mesmo clicando Atualizar (o PCM nível 2 não acessa a página do sap-scheduler para
# disparar o backlog à mão). Ordem = dependência: backlog primeiro (universo), hh_entregas por
# último (precisa do sap_backlog fresco — BR-20).
_JOBS_ATUALIZAR = ("backlog", "hh_planejado", "hh_realizado", "hh_entregas")
_LIMITE_FRESCOR_H = 26

# --- Toast de progresso da coleta (B28) ------------------------------------------------
_LABEL_LOTE = {"backlog": "Backlog", "hh_planejado": "HH Planejado",
               "hh_realizado": "HH Realizado", "hh_entregas": "HH Entregas"}
# status do job (core/mongo.py): pendente → executando → concluido | falhou
_STATUS_TXT = {"pendente": ("na fila", "muted"), "executando": ("coletando…", "run"),
               "concluido": ("concluído ✓", "ok"), "falhou": ("falhou ✗", "err")}
_TOAST_VERDE_SEG = 10       # verde fica visível por 10s e some sozinho


def _ids_lote(db, tipos) -> list:
    """_id (str) do job **ativo** (pendente/executando) de cada tipo — o que o "Atualizar agora"
    acabou de enfileirar (pendente) ou o que já estava rodando/travado (o caso `ja_em_andamento`).

    Corrigido 2026-07-28: antes pegava o job **mais recente por `criado_em`**, que podia ser um
    job **concluído** antigo — a UI então mostrava "concluído ✓" para uma coleta que nem foi
    disparada (bug do backlog órfão). Agora só acompanha o job ativo; um tipo sem job ativo não
    entra no lote (não inventa "concluído")."""
    ids = []
    for t in tipos:
        d = db["sap_jobs"].find_one(
            {"tipo": t, "status": {"$in": ["pendente", "executando"]}},
            sort=[("criado_em", -1)], projection={"_id": 1})
        if d:
            ids.append(str(d["_id"]))
    return ids


def _status_lote(db, ids) -> list:
    """[(tipo, status)] dos jobs do lote, preservando a ordem de `ids`."""
    from bson import ObjectId  # noqa: PLC0415
    oids = []
    for i in ids or []:
        try:
            oids.append(ObjectId(i))
        except Exception:
            pass
    docs = {str(d["_id"]): d for d in
            db["sap_jobs"].find({"_id": {"$in": oids}}, {"tipo": 1, "status": 1})}
    out = []
    for i in ids or []:
        d = docs.get(i)
        if d:
            out.append((d.get("tipo"), d.get("status") or "pendente"))
    return out


def _toast_body(estado: str, itens: list):
    """Corpo do toast: cabeçalho + uma linha por job (rótulo → status colorido)."""
    cab = {"andamento": "Coleta em andamento…", "ok": "Coleta concluída",
           "falha": "Falha na coleta"}[estado]
    linhas = []
    for t, s in itens:
        txt, cls = _STATUS_TXT.get(s, (s, "muted"))
        linhas.append(html.Div([
            html.Span(_LABEL_LOTE.get(t, t), className="hh-jobs-t"),
            html.Span(txt, className="hh-jobs-s " + cls),
        ], className="hh-jobs-row"))
    return [html.Div(cab, className="hh-jobs-h")] + linhas


def _nivel_usuario() -> int:
    """Nível do usuário logado (1 se anônimo). Usado para gating de edição."""
    try:
        return int(getattr(current_user, "level", 1) or 1)
    except Exception:
        return 1


def _fmt_frescor(coletado_em) -> str:
    """Selo 'dados de até DD/MM HH:MM' + aviso se passou de 26h da última coleta OK."""
    if not coletado_em:
        return "Aguardando primeira coleta de HH."
    brt = pytz.timezone(_TZ)
    dt = coletado_em
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    dt = dt.astimezone(brt)
    txt = f"dados de até {dt.strftime('%d/%m %H:%M')}"
    idade_h = (datetime.now(tz=pytz.UTC) - (coletado_em if coletado_em.tzinfo else pytz.UTC.localize(coletado_em))).total_seconds() / 3600
    if idade_h > _LIMITE_FRESCOR_H:
        return f"⚠ {txt} (desatualizado)"
    return txt


def register_hh_quadro_callbacks(app):
    """Registra os callbacks do quadro semanal HH. Chamado em callbacks.py."""

    # garante os índices da collection de atribuição (idempotente)
    try:
        hh_data.ensure_indexes_atrib()
    except Exception:
        pass

    @app.callback(
        Output("hh-semana", "data"),
        Output("hh-user-level", "data"),
        Input("hh-interval-load", "n_intervals"),
        State("hh-semana", "data"),
        prevent_initial_call=False,
    )
    def _init(_n, semana_atual_store):
        """No load: fixa a semana corrente (se vazia) e injeta o nível do usuário."""
        semana = semana_atual_store or hh_data.semana_atual()
        return semana, _nivel_usuario()

    @app.callback(
        Output("hh-download-pdf", "data"),
        Output("hh-pdf-msg", "children"),
        Input("hh-btn-pdf", "n_clicks"),
        State("hh-semana", "data"),
        prevent_initial_call=True,
    )
    def _emitir_pdf(n, semana):
        """Emite o PDF do planejamento da semana ativa (1 página por técnico — read-only, SP-01/07).

        Sem efeito colateral: só lê o quadro e devolve bytes. "Nada a imprimir" / falha → alerta
        no `#hh-pdf-msg` (sempre no DOM), sem download. Acesso é o da aba (herda gate
        /maintenance/backlog); emitir é leitura.
        """
        if not n:
            raise PreventUpdate

        def _aviso(texto, cor="warning"):
            return dbc.Alert(texto, color=cor, dismissable=True, className="shadow")

        semana = semana or hh_data.semana_atual()
        try:
            modelo = plano_semanal_pdf.montar_paginas_da_semana(semana)
        except Exception:
            return no_update, _aviso("Falha ao gerar o PDF. Tente novamente.", "danger")
        if modelo is None:
            return no_update, _aviso("Dados indisponíveis (banco offline). Tente mais tarde.", "danger")
        paginas = modelo["paginas"]
        if not paginas:
            return no_update, _aviso(f"Nada a imprimir na semana {semana} (nenhum técnico com plano).")
        try:
            pdf = plano_semanal_pdf.gerar_pdf(paginas, semana, modelo["coletado_em"], modelo["hoje"])
        except Exception:
            return no_update, _aviso("Falha ao gerar o PDF. Tente novamente.", "danger")
        fname = f"plano-semanal_{semana}.pdf"
        return dcc.send_bytes(lambda b: b.write(pdf), fname), None

    @app.callback(
        Output("hh-download-xlsx", "data"),
        Output("hh-pdf-msg", "children", allow_duplicate=True),
        Input("hh-btn-xlsx", "n_clicks"),
        State("hh-semana", "data"),
        prevent_initial_call=True,
    )
    def _exportar_xlsx(n, semana):
        """Exporta a planilha da semana ativa (B55 — análise gerencial/auditoria). Read-only.

        Mesma fonte do quadro (`montar_quadro`), então os números batem com a tela. Falha →
        alerta no `#hh-pdf-msg` (área de aviso compartilhada com o PDF), sem download.
        """
        if not n:
            raise PreventUpdate
        semana = semana or hh_data.semana_atual()

        def aviso(texto):
            return dbc.Alert(texto, color="danger", dismissable=True, className="shadow")

        try:
            modelo = plano_semanal_xlsx.montar_planilha_da_semana(
                semana, exportado_por=getattr(current_user, "username", "") or "")
            if modelo is None:
                return no_update, aviso("Dados indisponíveis (banco offline). Tente mais tarde.")
            xlsx = plano_semanal_xlsx.gerar_xlsx(modelo)
        except Exception:
            return no_update, aviso("Falha ao gerar a planilha. Tente novamente.")
        return dcc.send_bytes(lambda b: b.write(xlsx), modelo["nome_arquivo"]), None

    @app.callback(
        Output("hh-semana", "data", allow_duplicate=True),
        Input("hh-sem-prev", "n_clicks"),
        Input("hh-sem-next", "n_clicks"),
        State("hh-semana", "data"),
        prevent_initial_call=True,
    )
    def _navegar(_p, _n, semana):
        """Navega semana anterior/próxima."""
        semana = semana or hh_data.semana_atual()
        if ctx.triggered_id == "hh-sem-prev":
            return hh_data.semana_shift(semana, -1)
        if ctx.triggered_id == "hh-sem-next":
            return hh_data.semana_shift(semana, 1)
        raise PreventUpdate

    # espelha a semana no DOM para o JS de drag-drop ler
    app.clientside_callback(
        "function(s){ return s || ''; }",
        Output("hh-semana-dom", "children"),
        Input("hh-semana", "data"),
    )

    @app.callback(
        Output("hh-board", "children"),
        Output("hh-sem-label", "children"),
        Output("hh-frescor", "children"),
        Input("hh-semana", "data"),
        Input("hh-refresh-board", "data"),
        Input("hh-filtro", "data"),
        State("hh-collapsed", "data"),   # State: colapso é client-side, não dispara re-render
        State("hh-layout", "data"),      # State: modo leitura/planejamento é client-side
        State("hh-f-estado", "value"),   # B52: escolha lembrada pelo navegador (persistence local)
        prevent_initial_call=False,
    )
    def _render(semana, _refresh, filtro, collapsed, layout, estados_ctrl):
        """Render do quadro. A persistência do drop é feita em `_on_drop` (que decide se abre o
        modal de parcela ou grava inteira) e sinaliza aqui via `hh-refresh-board`.

        B52: o store `hh-filtro` só ganha a chave `estados` quando o planejador clica "Aplicar", mas
        as caixinhas de Estado são restauradas pelo navegador já no carregamento. Sem esta ponte, a
        escolha lembrada só valeria depois do primeiro Aplicar da sessão."""
        if not semana:
            semana = hh_data.semana_atual()
        filtro = dict(filtro or {})
        if "estados" not in filtro:
            filtro["estados"] = (estados_ctrl if estados_ctrl is not None
                                 else hh_quadro.ESTADOS_DEFAULT)
        nivel = _nivel_usuario()
        can_edit = nivel >= _MIN_LEVEL_EDIT

        quadro = hh_data.montar_quadro(semana)
        label = semana if semana else "—"
        frescor = _fmt_frescor(quadro.get("coletado_em") if quadro else None)
        return (hh_quadro.render_board(quadro, can_edit, collapsed or {}, filtro or {},
                                       layout or "planejamento"), label, frescor)

    @app.callback(
        Output("hh-modal-comprometido", "is_open"),
        Output("hh-comprom-ctx", "data"),
        Output("hh-comprom-body", "children"),
        Output("hh-drop-confirmed", "data"),
        Output("hh-modal-bloqueio", "is_open"),
        Output("hh-bloqueio-body", "children"),
        Input("hh-drop-event", "data"),
        State("hh-semana", "data"),
        prevent_initial_call=True,
    )
    def _gate_avisos(drop, semana):
        """Gate do drop (B32/B33): reúne os avisos "moles" da atribuição (disciplina cruzada +
        técnico comprometido no Gantt) num único modal de confirmação. Sem avisos → encaminha o
        drop direto para `hh-drop-confirmed` (fluxo normal do `_on_drop`).

        Bloqueio DURO que permanece: `pode_atribuir` recusa ordem não classificada (BR-07) — nesse
        caso nem abre modal (PreventUpdate). Disciplina cruzada Elé↔Mec deixou de bloquear (o técnico
        do quadro-destino é válido) e passou a ser aviso confirmável (decisão 2026-07-16)."""
        if not drop or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        semana = semana or hh_data.semana_atual()
        if drop.get("semana") != semana:
            raise PreventUpdate
        ordem = str(drop.get("ordem"))
        func = str(drop.get("funcionario_id"))
        dia = int(drop.get("dia", 0))
        disc = drop.get("disc")
        if not hh_data.pode_atribuir(ordem, func, disc, semana=semana):
            raise PreventUpdate     # não classificada / inválida → bloqueio duro (BR-07)

        # B49: ordem SEM tempo planejado (planejado 0 no IW37) não pode ser planejada — planejá-la
        # contaria 0h e polui o indicador (trabalho invisível). Bloqueio duro COM mensagem.
        base = hh_data.montar_ordens()
        planejado = int(((base or {}).get("ordens", {}).get(ordem) or {}).get("planejado_min") or 0)
        if planejado <= 0:
            corpo = html.Div([
                html.P(["A ordem ", html.B(ordem), " não tem tempo planejado no SAP (IW37)."],
                       className="mb-1"),
                html.P("Cadastre o tempo da operação no SAP antes de planejá-la aqui.",
                       className="mb-0 text-muted small"),
            ])
            # comprom fechado, drop NÃO liberado (bloqueio); abre o modal de bloqueio com a mensagem
            return False, no_update, no_update, no_update, True, corpo

        avisos = []
        # (1) disciplina cruzada (B33): ordem Mec/Elé caindo no quadro da outra disciplina
        disc_ordem = hh_data.disciplina_da_ordem(ordem)
        if (disc in ("Mecanica", "Eletrica") and disc_ordem in ("Mecanica", "Eletrica")
                and disc_ordem != disc):
            avisos.append(html.Li([
                "A ordem ", html.B(ordem), f" é {hh_quadro.LABEL_DISC[disc_ordem]} e vai para o "
                f"quadro de {hh_quadro.LABEL_DISC[disc]}."]))
        # (2) técnico comprometido no Gantt no dia-alvo (B32)
        comps = hh_data.comprometimentos(func, semana, dia)
        if comps:
            nomes = {str(f.get("_id")): f.get("nome") for f in hh_data._carregar_funcionarios()}
            nome = nomes.get(func, "O técnico")
            try:
                dia_lbl = hh_data.datas_da_semana(semana)[dia].strftime("%d/%m")
            except Exception:
                dia_lbl = "neste dia"
            avisos.append(html.Li([
                html.B(nome), f" está comprometido no dia {dia_lbl} com: ", ", ".join(comps)]))

        if not avisos:
            return False, no_update, no_update, drop, False, no_update   # sem aviso → segue direto
        body = html.Div([
            html.P("Confirmar esta atribuição?", className="mb-2"),
            html.Ul(avisos, className="mb-0"),
        ])
        return True, drop, body, no_update, False, no_update             # tem aviso → espera confirmação

    @app.callback(
        Output("hh-modal-comprometido", "is_open", allow_duplicate=True),
        Output("hh-drop-confirmed", "data", allow_duplicate=True),
        Input("hh-comprom-ok", "n_clicks"),
        State("hh-comprom-ctx", "data"),
        prevent_initial_call=True,
    )
    def _confirmar_comprometido(n, ctx_drop):
        """OK do modal de comprometido → libera o drop guardado para o `_on_drop` (segue o fluxo
        normal, inclusive o modal de parcela de 70% se aplicável)."""
        if not n or not ctx_drop or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        return False, ctx_drop

    @app.callback(
        Output("hh-modal-comprometido", "is_open", allow_duplicate=True),
        Input("hh-comprom-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def _cancelar_comprometido(n):
        """Cancelar → fecha o modal sem gravar (o drop não vira atribuição)."""
        if not n:
            raise PreventUpdate
        return False

    @app.callback(
        Output("hh-modal-bloqueio", "is_open", allow_duplicate=True),
        Input("hh-bloqueio-ok", "n_clicks"),
        prevent_initial_call=True,
    )
    def _fechar_bloqueio(n):
        """B49: 'Entendi' fecha o modal de bloqueio (ordem sem tempo planejado). O drop não virou
        atribuição — a ordem permanece na fila."""
        if not n:
            raise PreventUpdate
        return False

    @app.callback(
        Output("hh-modal-parcela", "is_open"),
        Output("hh-parcela-ctx", "data"),
        Output("hh-parcela-titulo", "children"),
        Output("hh-parcela-info", "children"),
        Output("hh-parcela-opcoes", "options"),
        Output("hh-parcela-opcoes", "value"),
        Output("hh-refresh-board", "data", allow_duplicate=True),
        Input("hh-drop-confirmed", "data"),
        State("hh-semana", "data"),
        State("hh-refresh-board", "data"),
        prevent_initial_call=True,
    )
    def _on_drop(drop, semana, refresh):
        """Ao soltar uma ordem num slot (após o gate de comprometimento — B32): se a carga do
        técnico/dia continua ≤ meta (70%), grava inteira sem modal; se cruza a meta, abre o modal
        de parcela para o PCM dividir (SP-04.3/SP-13). Blindagem server-side de nível + disciplina.

        Lê `hh-drop-confirmed` (não `hh-drop-event`): o gate `_gate_comprometido` encaminha para
        cá o drop de técnico livre direto, ou o de técnico comprometido só após confirmação."""
        if not drop or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        semana = semana or hh_data.semana_atual()
        if drop.get("semana") != semana:
            raise PreventUpdate
        ordem = str(drop.get("ordem")); func = str(drop.get("funcionario_id"))
        dia = int(drop.get("dia", 0)); disc = drop.get("disc")
        if not hh_data.pode_atribuir(ordem, func, disc, semana=semana):
            raise PreventUpdate

        base = hh_data.montar_ordens()
        ordens = base["ordens"] if base else {}
        o = ordens.get(ordem, {})
        planejado = int(o.get("planejado_min") or 0)
        atribs = hh_data.listar_atribuicoes(semana)
        ja_tem = any(str(a.get("ordem")) == ordem for a in atribs)
        restante = hh_data.restante_ordem(atribs, ordem, planejado)
        a_colocar = restante if ja_tem else planejado    # o que ESTE drop coloca no slot

        cfg = hh_data.carregar_config_capacidade()
        emp = next((f for f in hh_data._carregar_funcionarios()
                    if str(f.get("_id")) == func), {})
        disp = hh_data.jornada_min(emp, cfg["disponivel_min"])
        carga = hh_data.carga_tecnico_dia(atribs, ordens, func, dia)
        meta = disp * cfg["meta_pct"] if disp else 0
        _vazio = (no_update,) * 6

        def _grava(parcela_min):
            hh_data.atribuir(semana=semana, ordem=ordem, funcionario_id=func, dia=dia,
                             parcela_min=parcela_min, por=getattr(current_user, "username", "?"),
                             disciplina_quadro=disc)
            return (*_vazio, (refresh or 0) + 1)

        # B48: ordem já 100% alocada em outro slot (restante 0) → NUNCA gravar card fantasma de 0h.
        if a_colocar <= 0 and ja_tem:
            alvo_ja_tem = any(str(a.get("ordem")) == ordem and str(a.get("funcionario_id")) == func
                              and int(a.get("dia", -1)) == dia for a in atribs)
            # re-drop no mesmo slot, ou ordem sem tempo planejado → nada a repartir
            if alvo_ja_tem or planejado <= 0:
                raise PreventUpdate
            # B48b: soltou a ordem cheia num slot NOVO → modal mover/dividir (opções contra o TOTAL,
            # pois o restante é 0). "Mover tudo" = pegar o planejado inteiro; parcial = o resto fica
            # com a origem. A confirmação chama hh_data.repartir_ordem.
            opcoes_min = hh_data.opcoes_parcela(planejado)
            nomes = {str(f.get("_id")): f.get("nome") for f in hh_data._carregar_funcionarios()}
            orig = next((a for a in atribs if str(a.get("ordem")) == ordem), None)
            nome_orig = nomes.get(str(orig.get("funcionario_id")), "outro técnico") if orig else "outro técnico"

            def _lbl(m):
                return (f"Mover tudo — {hh_quadro._fmt_min(m)}" if m >= planejado
                        else f"{hh_quadro._fmt_min(m)} aqui · {hh_quadro._fmt_min(planejado - m)} com {nome_orig}")

            options = [{"label": _lbl(m), "value": m} for m in opcoes_min]
            info = f"Essa ordem já está 100% planejada em {nome_orig}. Quanto vem para cá?"
            ctx_data = {"ordem": ordem, "func": func, "dia": dia, "disc": disc, "semana": semana,
                        "planejado": planejado, "cheia": True}
            default_val = opcoes_min[-1] if opcoes_min else planejado   # default = mover tudo
            return True, ctx_data, f"Ordem {ordem} — mover ou dividir", info, options, default_val, no_update
        # sem horas para dividir (ordem sem planejado) ou sem meta calculável → grava direto
        if a_colocar <= 0 or meta <= 0:
            return _grava(None if not ja_tem else a_colocar)
        # cabe na meta → grava direto (None se ordem nova inteira; senão parcela numérica)
        if carga + a_colocar <= meta:
            return _grava(None if not ja_tem else a_colocar)

        # cruza a meta → abre o modal para o PCM escolher quanto vai neste slot
        opcoes_min = hh_data.opcoes_parcela(a_colocar)
        options = [{"label": hh_quadro._fmt_min(m), "value": m} for m in opcoes_min]
        nomes = {str(f.get("_id")): f.get("nome") for f in hh_data._carregar_funcionarios()}
        nome = nomes.get(func, "técnico")
        info = f"O tempo total dessa ordem extrapola a meta de {nome}."
        ctx_data = {"ordem": ordem, "func": func, "dia": dia, "disc": disc, "semana": semana,
                    "planejado": planejado, "a_colocar": a_colocar, "carga": carga,
                    "disp": disp, "ja_tem": ja_tem, "meta_pct": cfg["meta_pct"]}
        default_val = opcoes_min[-1] if opcoes_min else a_colocar   # default = distribuir tudo
        return True, ctx_data, f"Dividir ordem {ordem}", info, options, default_val, no_update

    @app.callback(
        Output("hh-modal-parcela", "is_open", allow_duplicate=True),
        Output("hh-refresh-board", "data", allow_duplicate=True),
        Input("hh-parcela-ok", "n_clicks"),
        State("hh-parcela-opcoes", "value"),
        State("hh-parcela-ctx", "data"),
        State("hh-refresh-board", "data"),
        prevent_initial_call=True,
    )
    def _confirmar_parcela(n, valor, ctx_data, refresh):
        """Confirma a divisão: grava a parcela escolhida. Ordem nova com valor == planejado inteiro
        vira `None` (retrocompat B18); parcial vira número. Revalida nível server-side."""
        if not n or not ctx_data or valor is None or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        valor = int(valor)
        # B48b: ordem cheia re-repartida — tira das origens e grava o destino (repartir_ordem)
        if ctx_data.get("cheia"):
            hh_data.repartir_ordem(ctx_data["semana"], str(ctx_data["ordem"]),
                                   str(ctx_data["func"]), int(ctx_data["dia"]), valor,
                                   ctx_data.get("disc"), getattr(current_user, "username", "?"))
            return False, (refresh or 0) + 1
        parcela = None if (not ctx_data.get("ja_tem")
                           and valor >= int(ctx_data.get("planejado") or 0)) else valor
        hh_data.atribuir(semana=ctx_data["semana"], ordem=str(ctx_data["ordem"]),
                         funcionario_id=str(ctx_data["func"]), dia=int(ctx_data["dia"]),
                         parcela_min=parcela, por=getattr(current_user, "username", "?"),
                         disciplina_quadro=ctx_data.get("disc"))
        return False, (refresh or 0) + 1

    @app.callback(
        Output("hh-modal-parcela", "is_open", allow_duplicate=True),
        Input("hh-parcela-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def _cancelar_parcela(n):
        """Fecha o modal de parcela sem gravar (o drop não vira atribuição)."""
        if not n:
            raise PreventUpdate
        return False

    @app.callback(
        Output("hh-modal-parcela", "is_open", allow_duplicate=True),
        Output("hh-parcela-ctx", "data", allow_duplicate=True),
        Output("hh-parcela-titulo", "children", allow_duplicate=True),
        Output("hh-parcela-info", "children", allow_duplicate=True),
        Output("hh-parcela-opcoes", "options", allow_duplicate=True),
        Output("hh-parcela-opcoes", "value", allow_duplicate=True),
        Input({"type": "hh-split", "atrib": ALL, "ordem": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _abrir_split(_clicks):
        """Botão ✂ num card já colocado: reabre o modal para dividir a ordem — o PCM reduz o que
        fica neste slot e o resto volta pra fila. Split manual, independe do gatilho de 70%
        (SP-04.2: divisão por dia/técnico a qualquer momento)."""
        if not any(_clicks or []) or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        tid = ctx.triggered_id
        if not isinstance(tid, dict):
            raise PreventUpdate
        atrib = hh_data.get_atribuicao(tid.get("atrib"))
        if not atrib:
            raise PreventUpdate
        semana = atrib.get("semana"); func = str(atrib.get("funcionario_id"))
        dia = int(atrib.get("dia", 0)); ordem = str(atrib.get("ordem"))
        base = hh_data.montar_ordens()
        ordens = base["ordens"] if base else {}
        o = ordens.get(ordem, {})
        disc = atrib.get("disciplina_quadro") or o.get("disciplina")
        planejado = int(o.get("planejado_min") or 0)
        atribs = hh_data.listar_atribuicoes(semana)
        cur = atrib.get("parcela_min")
        cur_here = int(cur) if cur is not None else planejado
        # máximo que pode ficar NESTE slot = tudo que não está em outros slots da mesma ordem
        a_colocar = hh_data.restante_ordem(atribs, ordem, planejado, excluir_func_dia=(func, dia))
        if a_colocar <= 0:
            raise PreventUpdate
        cfg = hh_data.carregar_config_capacidade()
        emp = next((f for f in hh_data._carregar_funcionarios()
                    if str(f.get("_id")) == func), {})
        disp = hh_data.jornada_min(emp, cfg["disponivel_min"])
        # carga do dia SEM esta ordem (a barra soma a parcela escolhida por cima)
        carga_base = max(0, hh_data.carga_tecnico_dia(atribs, ordens, func, dia) - cur_here)
        opcoes_min = hh_data.opcoes_parcela(a_colocar)
        options = [{"label": hh_quadro._fmt_min(m), "value": m} for m in opcoes_min]
        default_val = cur_here if cur_here in opcoes_min else (opcoes_min[-1] if opcoes_min else a_colocar)
        nomes = {str(f.get("_id")): f.get("nome") for f in hh_data._carregar_funcionarios()}
        nome = nomes.get(func, "técnico")
        dia_lbl = hh_quadro.DIAS[dia] if 0 <= dia < 7 else "?"
        info = (f"Divida a ordem {ordem}: quanto fica com {nome} em {dia_lbl}? "
                f"O que sobrar volta pra fila para você distribuir.")
        ctx_data = {"ordem": ordem, "func": func, "dia": dia, "disc": disc, "semana": semana,
                    "planejado": planejado, "a_colocar": a_colocar, "carga": carga_base,
                    "disp": disp, "ja_tem": True, "meta_pct": cfg["meta_pct"]}
        return True, ctx_data, f"Dividir ordem {ordem}", info, options, default_val

    # ---- B19: config de capacidade (nível 2+) ----------------------------------------
    @app.callback(
        Output("hh-col-capacidade", "style"),
        Input("hh-user-level", "data"),
    )
    def _gate_cap_btn(level):
        """Mostra o botão 'Capacidade' só para nível ≥ 2 (config é do PCM/gestor)."""
        try:
            lv = int(level or 1)
        except (TypeError, ValueError):
            lv = 1
        return {} if lv >= _MIN_LEVEL_EDIT else {"display": "none"}

    # ---- GantManagement BR-25: mão de obra temporária (incluir / retirar) -------------
    def _usuario():
        """Quem fez a ação, para a auditoria do Gantt."""
        return {"id": getattr(current_user, "id", None), "nome": getattr(current_user, "username", None)}

    @app.callback(
        Output("hh-col-incluir-temp", "style"),
        Output("hh-btn-incluir-temp", "disabled"),
        Output("hh-btn-incluir-temp", "title"),
        Input("hh-user-level", "data"),
        Input("hh-semana", "data"),
    )
    def _gate_incluir_temp(level, semana):
        """Botão 'Incluir mão de obra temporária': só nível ≥ 2; desabilitado em semana encerrada."""
        try:
            lv = int(level or 1)
        except (TypeError, ValueError):
            lv = 1
        if lv < _MIN_LEVEL_EDIT:
            return {"display": "none"}, True, ""
        if not hh_data.semana_atual_ou_futura(semana or hh_data.semana_atual()):
            return {}, True, "semana encerrada"
        return {}, False, "Incluir mão de obra temporária no planejamento a partir desta semana"

    @app.callback(
        Output("hh-modal-incluir-temp", "is_open"),
        Output("hh-incluir-temp-titulo", "children"),
        Output("hh-incluir-temp-sel", "options"),
        Output("hh-incluir-temp-sel", "value"),
        Output("hh-incluir-temp-vazio", "children"),
        Output("hh-incluir-temp-msg", "children"),
        Input("hh-btn-incluir-temp", "n_clicks"),
        Input("hh-incluir-temp-cancel", "n_clicks"),
        State("hh-semana", "data"),
        prevent_initial_call=True,
    )
    def _abrir_incluir_temp(n, _cancel, semana):
        """Abre o modal com os temporários ATIVOS que não contam na semana exibida."""
        if ctx.triggered_id == "hh-incluir-temp-cancel":
            return False, no_update, no_update, no_update, no_update, ""
        if not n or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        semana = semana or hh_data.semana_atual()
        opts = sorted(
            ({"label": f"{f.get('nome')} — Turno {f.get('turno_padrao') or '?'}", "value": str(f.get("_id"))}
             for f in hh_data._carregar_funcionarios()
             if f.get("temporario") and f.get("ativo", True)
             and not hh_data.periodos_quadro.conta_na_semana(f, semana)),
            key=lambda o: o["label"].lower())
        vazio = ("" if opts else "Nenhuma mão de obra temporária disponível — marque a caixinha "
                                 "no cadastro do funcionário (Gantt).")
        return True, f"Incluir mão de obra temporária — semana {semana}", opts, None, vazio, ""

    @app.callback(
        Output("hh-modal-incluir-temp", "is_open", allow_duplicate=True),
        Output("hh-incluir-temp-msg", "children", allow_duplicate=True),
        Output("hh-refresh-board", "data", allow_duplicate=True),
        Input("hh-incluir-temp-ok", "n_clicks"),
        State("hh-incluir-temp-sel", "value"),
        State("hh-semana", "data"),
        State("hh-refresh-board", "data"),
        prevent_initial_call=True,
    )
    def _confirmar_incluir_temp(n, func_id, semana, refresh):
        """Grava a inclusão (servidor revalida tudo) e re-renderiza o quadro."""
        if not n or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        if not func_id:
            return True, dbc.Alert("Escolha um funcionário.", color="warning", className="py-1 mb-0"), no_update
        ok, msg = hh_data.incluir_temporario(func_id, semana or hh_data.semana_atual(), _usuario())
        if not ok:
            return True, dbc.Alert(msg, color="danger", className="py-1 mb-0"), no_update
        return False, "", (refresh or 0) + 1

    @app.callback(
        Output("hh-modal-retirar-temp", "is_open"),
        Output("hh-retirar-temp-body", "children"),
        Output("hh-retirar-temp-ok", "style"),
        Output("hh-retirar-temp-cancel", "children"),
        Output("hh-retirar-temp-ctx", "data"),
        Input({"type": "hh-temp-ret", "func": ALL}, "n_clicks"),
        Input("hh-retirar-temp-cancel", "n_clicks"),
        State("hh-semana", "data"),
        prevent_initial_call=True,
    )
    def _pedir_retirar_temp(clicks, _cancel, semana):
        """Clique em 'retirar': com ordem da semana em diante → só o bloqueio; senão confirmação."""
        tid = ctx.triggered_id
        if tid == "hh-retirar-temp-cancel":
            return False, no_update, no_update, no_update, None
        if not isinstance(tid, dict) or not any(clicks or []) or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        semana = semana or hh_data.semana_atual()
        func = tid["func"]
        nomes = {str(f.get("_id")): f.get("nome") for f in hh_data._carregar_funcionarios()}
        nome = nomes.get(func, "O funcionário")
        futuras = hh_data.atribuicoes_desde(func, semana)
        if futuras:
            return (True, hh_data._msg_ordens_atribuidas(nome, futuras, "retirar"),
                    {"display": "none"}, "Entendi", None)
        txt = (f"Retirar {nome} do planejamento a partir de {semana}? "
               "As semanas anteriores não mudam.")
        return True, txt, {}, "Cancelar", {"func": func, "nome": nome}

    @app.callback(
        Output("hh-modal-retirar-temp", "is_open", allow_duplicate=True),
        Output("hh-retirar-temp-body", "children", allow_duplicate=True),
        Output("hh-retirar-temp-ok", "style", allow_duplicate=True),
        Output("hh-refresh-board", "data", allow_duplicate=True),
        Input("hh-retirar-temp-ok", "n_clicks"),
        State("hh-retirar-temp-ctx", "data"),
        State("hh-semana", "data"),
        State("hh-refresh-board", "data"),
        prevent_initial_call=True,
    )
    def _confirmar_retirar_temp(n, ctx_ret, semana, refresh):
        """Grava a retirada — servidor checa de novo (ordem pode ter sido arrastada no meio-tempo)."""
        if not n or not ctx_ret or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        ok, msg = hh_data.retirar_temporario(ctx_ret["func"], semana or hh_data.semana_atual(), _usuario())
        if not ok:
            return True, msg, {"display": "none"}, no_update
        return False, "", no_update, (refresh or 0) + 1

    @app.callback(
        Output("hh-modal-capacidade", "is_open"),
        Output("hh-cap-A", "value"), Output("hh-cap-B", "value"),
        Output("hh-cap-C", "value"), Output("hh-cap-ADM", "value"),
        Output("hh-cap-meta", "value"), Output("hh-cap-msg", "children"),
        Input("hh-btn-capacidade", "n_clicks"),
        prevent_initial_call=True,
    )
    def _abrir_capacidade(n):
        """Abre o modal de capacidade pré-preenchido com a config atual (horas por turno + meta%)."""
        if not n or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        cfg = hh_data.carregar_config_capacidade()
        d = cfg["disponivel_min"]
        def h(t):
            return round(d.get(t, 0) / 60, 2)
        return True, h("A"), h("B"), h("C"), h("ADM"), round(cfg["meta_pct"] * 100), ""

    @app.callback(
        Output("hh-modal-capacidade", "is_open", allow_duplicate=True),
        Output("hh-cap-msg", "children", allow_duplicate=True),
        Output("hh-refresh-board", "data", allow_duplicate=True),
        Input("hh-cap-salvar", "n_clicks"),
        State("hh-cap-A", "value"), State("hh-cap-B", "value"),
        State("hh-cap-C", "value"), State("hh-cap-ADM", "value"),
        State("hh-cap-meta", "value"), State("hh-refresh-board", "data"),
        prevent_initial_call=True,
    )
    def _salvar_capacidade(n, a, b_, c, adm, meta, refresh):
        """Persiste a config (revalida nível server-side) e re-renderiza o quadro (barra recalibra)."""
        if not n or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        def m(x):
            try:
                return int(round(float(x) * 60))
            except (TypeError, ValueError):
                return None
        disp = {"A": m(a), "B": m(b_), "C": m(c), "ADM": m(adm)}
        if any(v is None or v < 0 for v in disp.values()):
            return no_update, "Informe horas válidas (≥ 0) para todos os turnos.", no_update
        try:
            mp = float(meta) / 100
        except (TypeError, ValueError):
            mp = None
        if mp is None or not (0 <= mp <= 1):
            return no_update, "A meta deve estar entre 0 e 100%.", no_update
        r = hh_data.salvar_config_capacidade(disp, mp)
        if not r.get("ok"):
            return no_update, "Não foi possível salvar (banco indisponível).", no_update
        return False, "", (refresh or 0) + 1

    @app.callback(
        Output("hh-modal-capacidade", "is_open", allow_duplicate=True),
        Input("hh-cap-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def _cancelar_capacidade(n):
        """Fecha o modal de capacidade sem salvar."""
        if not n:
            raise PreventUpdate
        return False

    # barrinha ao vivo: ocupação do dia com a parcela escolhida. Verde ≤ meta(70%), amarelo
    # meta–100%, vermelho > 100% (client-side, sem round-trip).
    app.clientside_callback(
        """
        function(valor, ctx){
            var nou = window.dash_clientside.no_update;
            if(valor==null || !ctx || !(ctx.disp>0)){ return [nou, nou, ""]; }
            var pct = (ctx.carga + Number(valor)) / ctx.disp * 100;
            var meta = Math.round((ctx.meta_pct||0.7)*100);
            var zona = pct <= meta ? "ok" : (pct <= 100 ? "warn" : "over");
            var w = Math.max(3, Math.min(pct, 100));
            var txt = Math.round(pct) + "% da jornada do dia"
                      + (pct > 100 ? " — acima do disponível" : (pct > meta ? " — acima da meta" : ""));
            return [{width: w + "%"}, "hh-parcela-bar-fill " + zona, txt];
        }
        """,
        Output("hh-parcela-bar-fill", "style"),
        Output("hh-parcela-bar-fill", "className"),
        Output("hh-parcela-pct", "children"),
        Input("hh-parcela-opcoes", "value"),
        State("hh-parcela-ctx", "data"),
    )

    @app.callback(
        Output("hh-refresh-board", "data", allow_duplicate=True),
        Input({"type": "hh-tec-rem", "disc": ALL, "func": ALL}, "n_clicks"),
        Input({"type": "hh-tec-add", "disc": ALL}, "value"),
        State("hh-refresh-board", "data"),
        prevent_initial_call=True,
    )
    def _config_tecnico_disc(rem_clicks, add_vals, refresh):
        """Adiciona/remove um técnico de uma disciplina (Mec/Elé configuráveis). Só PCM+ (nível 2)."""
        if _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        tid = ctx.triggered_id
        if not isinstance(tid, dict):
            raise PreventUpdate
        if tid.get("type") == "hh-tec-rem":
            if not any(rem_clicks or []):
                raise PreventUpdate
            hh_data.set_disciplina_funcionario(tid["func"], tid["disc"], incluir=False)
        elif tid.get("type") == "hh-tec-add":
            # valor do Select que disparou
            val = ctx.triggered[0]["value"] if ctx.triggered else None
            if not val:
                raise PreventUpdate
            hh_data.set_disciplina_funcionario(val, tid["disc"], incluir=True)
        else:
            raise PreventUpdate
        return (refresh or 0) + 1

    def _opcoes_assoc(opcoes):
        """Converte ordens em options de RadioItems (label = nº — descrição)."""
        return [{"label": f"{o['ordem']} — {(o.get('descricao') or '')[:70]}", "value": o["ordem"]}
                for o in opcoes]

    @app.callback(
        Output("hh-modal-assoc", "is_open"),
        Output("hh-assoc-ctx", "data"),
        Output("hh-assoc-titulo", "children"),
        Output("hh-assoc-busca", "value"),
        Output("hh-assoc-results", "options"),
        Output("hh-assoc-results", "value"),
        Output("hh-assoc-erro", "children"),
        Input("hh-slot-context", "data"),
        prevent_initial_call=True,
    )
    def _abrir_assoc(ctx_slot):
        """Botão direito num slot livre → abre o modal de associação (só PCM+)."""
        if not ctx_slot or _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        disc = ctx_slot.get("disc")
        if disc not in ("Mecanica", "Eletrica"):
            raise PreventUpdate     # slot de disciplina não atribuível
        semana = ctx_slot.get("semana") or hh_data.semana_atual()
        nomes = {str(f.get("_id")): f.get("nome") for f in hh_data._carregar_funcionarios()}
        nome = nomes.get(str(ctx_slot.get("tecnico")), "técnico")
        dia = int(ctx_slot.get("dia", 0))
        dia_lbl = hh_quadro.DIAS[dia] if 0 <= dia < 7 else "?"
        titulo = f"{hh_quadro.LABEL_DISC.get(disc, disc)} · {nome} · {dia_lbl}"
        opcoes = hh_data.opcoes_a_planejar(semana, disc, "", 50)
        return True, ctx_slot, titulo, "", _opcoes_assoc(opcoes), None, ""

    @app.callback(
        Output("hh-assoc-results", "options", allow_duplicate=True),
        Input("hh-assoc-busca", "value"),
        State("hh-assoc-ctx", "data"),
        prevent_initial_call=True,
    )
    def _buscar_assoc(busca, ctx_slot):
        """Filtra as ordens a planejar (da disciplina do slot) pela busca."""
        if not ctx_slot:
            raise PreventUpdate
        opcoes = hh_data.opcoes_a_planejar(ctx_slot.get("semana") or hh_data.semana_atual(),
                                           ctx_slot.get("disc"), busca or "", 50)
        return _opcoes_assoc(opcoes)

    @app.callback(
        Output("hh-modal-assoc", "is_open", allow_duplicate=True),
        Output("hh-assoc-erro", "children", allow_duplicate=True),
        Output("hh-drop-event", "data", allow_duplicate=True),
        Input("hh-assoc-ok", "n_clicks"),
        Input("hh-assoc-cancel", "n_clicks"),
        State("hh-assoc-results", "value"),
        State("hh-assoc-ctx", "data"),
        prevent_initial_call=True,
    )
    def _confirmar_assoc(_ok, _cancel, ordem_sel, ctx_slot):
        """OK → encaminha a ordem selecionada para o mesmo pipeline do drag-drop (B32): emite um
        `hh-drop-event`, que passa pelo gate de comprometimento e pelo modal de parcela (70%) antes
        de gravar. Assim o path fallback (dropdown) ganha o aviso de técnico comprometido de graça."""
        if ctx.triggered_id == "hh-assoc-cancel":
            return False, "", no_update
        if _nivel_usuario() < _MIN_LEVEL_EDIT or not ctx_slot:
            raise PreventUpdate
        if not ordem_sel:
            return True, "Selecione uma ordem na lista.", no_update
        if not hh_data.pode_atribuir(str(ordem_sel), str(ctx_slot.get("tecnico")),
                                     ctx_slot.get("disc"),
                                     semana=ctx_slot.get("semana") or hh_data.semana_atual()):
            return True, "Essa ordem não é desta disciplina/técnico.", no_update
        drop = {"ordem": str(ordem_sel), "funcionario_id": str(ctx_slot.get("tecnico")),
                "dia": int(ctx_slot.get("dia", 0)),
                "semana": ctx_slot.get("semana") or hh_data.semana_atual(),
                "disc": ctx_slot.get("disc"), "ts": _ok}
        return False, "", drop

    @app.callback(
        Output("hh-modal-detalhe", "is_open"),
        Output("hh-detalhe-body", "children"),
        Input("hh-card-click", "data"),
        prevent_initial_call=True,
    )
    def _abrir_detalhe(click):
        """Clique simples num card → abre o modal de detalhe da ordem (B9)."""
        if not click or not click.get("ordem"):
            raise PreventUpdate
        det = hh_data.detalhe_ordem(str(click["ordem"]))
        return True, hh_quadro.modal_detalhe(det)

    @app.callback(
        Output("hh-modal-replan", "is_open"),
        Output("hh-pending-remove", "data"),
        Output("hh-motivo", "options"),
        Output("hh-motivo", "value"),
        Output("hh-replan-resumo", "children"),
        Output("hh-motivo-texto", "value"),
        Output("hh-replan-erro", "children"),
        Input({"type": "hh-remove", "atrib": ALL, "ordem": ALL}, "n_clicks"),
        State("hh-semana", "data"),
        prevent_initial_call=True,
    )
    def _abrir_replan(cliques, semana):
        """Abre o modal de justificativa ao clicar em remover uma ordem do plano (BR-16)."""
        if not cliques or not any(cliques):
            raise PreventUpdate
        if _nivel_usuario() < _MIN_LEVEL_EDIT:
            raise PreventUpdate
        tid = ctx.triggered_id
        if not isinstance(tid, dict):
            raise PreventUpdate
        opts = [{"label": m, "value": m} for m in hh_data.listar_motivos()]
        pend = {"atrib_id": tid["atrib"], "ordem": tid["ordem"], "semana": semana}
        resumo = f"Remover a ordem {tid['ordem']} do plano da semana {semana}."
        return True, pend, opts, None, resumo, "", ""

    @app.callback(
        Output("hh-modal-replan", "is_open", allow_duplicate=True),
        Output("hh-refresh-board", "data"),
        Output("hh-replan-erro", "children", allow_duplicate=True),
        Input("hh-replan-confirm", "n_clicks"),
        Input("hh-replan-cancel", "n_clicks"),
        State("hh-pending-remove", "data"),
        State("hh-motivo", "value"),
        State("hh-motivo-texto", "value"),
        State("hh-refresh-board", "data"),
        prevent_initial_call=True,
    )
    def _confirmar_replan(_ok, _cancel, pend, motivo, texto, refresh):
        """Confirma a remoção: registra justificativa (BR-16) e remove a atribuição."""
        if ctx.triggered_id == "hh-replan-cancel":
            return False, no_update, ""
        if _nivel_usuario() < _MIN_LEVEL_EDIT or not pend:
            raise PreventUpdate
        por = getattr(current_user, "username", "?")
        reg = hh_data.registrar_replanejamento(
            semana=pend["semana"], ordem=pend["ordem"], tipo="remover",
            de={"atrib_id": pend["atrib_id"]}, para=None,
            categoria=motivo, texto=texto, por=por,
        )
        if not reg["ok"]:
            return True, no_update, reg["motivo"]      # mantém modal aberto + erro
        hh_data.remover_atribuicao(pend["atrib_id"], por=por)
        return False, (refresh or 0) + 1, ""           # fecha + dispara re-render

    @app.callback(
        Output("hh-modal-filtro", "is_open"),
        Input("hh-btn-filtro", "n_clicks"),
        Input("hh-f-aplicar", "n_clicks"),
        prevent_initial_call=True,
    )
    def _toggle_modal_filtro(_abrir, _aplicar):
        """Abre o modal de filtro (botão) e fecha ao aplicar."""
        return ctx.triggered_id == "hh-btn-filtro"

    @app.callback(
        Output("hh-filtro", "data"),
        Output("hh-f-busca", "value"),
        Output("hh-f-flags", "value"),
        Output("hh-f-ordenar", "value"),
        Output("hh-f-linha", "value"),
        Output("hh-f-estado", "value"),
        Input("hh-f-aplicar", "n_clicks"),
        Input("hh-f-limpar", "n_clicks"),
        State("hh-f-busca", "value"),
        State("hh-f-flags", "value"),
        State("hh-f-ordenar", "value"),
        State("hh-f-linha", "value"),
        State("hh-f-estado", "value"),
        prevent_initial_call=True,
    )
    def _aplicar_filtro(_ap, _lp, busca, flags, ordenar, linhas, estados):
        """Aplica (lê os controles → store hh-filtro) ou limpa o filtro. `linhas` (B16) e `estados`
        (B31, status do usuário) filtram o quadro inteiro (fila + cards atribuídos)."""
        if ctx.triggered_id == "hh-f-limpar":
            # B52: "Limpar" devolve o Estado ao default (tudo marcado), não a "nada marcado" —
            # caixinha desmarcada agora significa "não quero ver", e limpar não pode esvaziar a tela.
            return {}, "", [], "relevancia", [], hh_quadro.ESTADOS_DEFAULT
        flags = flags or []
        filtro = {
            "busca": busca or "",
            "planejado_pos": "plan_pos" in flags,
            "nao_100": "nao_100" in flags,
            "com_realizado": "com_real" in flags,
            "so_pendentes": "pendente" in flags,
            "linhas": linhas or [],
            "estados": estados or [],   # [] = tudo desmarcado → nada passa (B52)
            "ordenar": ordenar or "relevancia",
        }
        return filtro, no_update, no_update, no_update, no_update, no_update

    @app.callback(
        Output("hh-refresh-board", "data", allow_duplicate=True),
        Input("hh-btn-recarregar", "n_clicks"),
        State("hh-refresh-board", "data"),
        prevent_initial_call=True,
    )
    def _recarregar(_n, refresh):
        """Força re-render do quadro (relê do banco) — útil quando em dúvida."""
        if not _n:
            raise PreventUpdate
        return (refresh or 0) + 1

    # alterna modo leitura(fila)/planejamento — só flipa o store (persiste na sessão)
    app.clientside_callback(
        "function(n, atual){ if(!n){ return window.dash_clientside.no_update; }"
        " return (atual === 'fila') ? 'planejamento' : 'fila'; }",
        Output("hh-layout", "data"),
        Input("hh-btn-modo", "n_clicks"),
        State("hh-layout", "data"),
        prevent_initial_call=True,
    )
    # aplica o modo ao DOM (classe no board + label do botão) — roda no clique E no load (restaurado)
    app.clientside_callback(
        """
        function(layout){
            var fila = (layout === 'fila');
            var wrap = document.querySelector('.hh-board-wrap');
            if(wrap){ wrap.classList.toggle('hh-mode-fila', fila); }
            return fila ? 'Modo planejamento' : 'Modo leitura';
        }
        """,
        Output("hh-btn-modo-lbl", "children"),
        Input("hh-layout", "data"),
    )

    @app.callback(
        Output("hh-refresh-status", "children"),
        Output("hh-jobs-ids", "data"),
        Output("hh-jobs-doneat", "data"),
        Output("hh-jobs-poll", "disabled"),
        Output("hh-jobs-body", "children", allow_duplicate=True),
        Output("hh-jobs-toast", "className", allow_duplicate=True),
        Input("hh-btn-refresh", "n_clicks"),
        prevent_initial_call=True,
    )
    def _atualizar_agora(_n):
        """Dispara a coleta que alimenta o quadro: backlog (universo) + HH + entregas. Só PCM+ (nível 2).

        Atende o PCM sem precisar da página do sap-scheduler (nível 3): o backlog é o universo do
        quadro (B13), então uma nota/ordem recém-editada só aparece após recoletar o backlog —
        por isso ele entra aqui junto dos jobs HH (BR-09). Abre o toast de progresso (B28) e liga o
        poll que acompanha os jobs até concluir/falhar."""
        _nop = (no_update,) * 5
        if _nivel_usuario() < _MIN_LEVEL_EDIT:
            return ("Sem permissão para disparar a coleta (requer nível 2+).",) + _nop
        db = get_mongo_connection()        # sem args → objeto Database (padrão do backlog)
        if db is None:
            return ("⚠ Banco indisponível — coleta não disparada.",) + _nop
        try:
            resultados = [inserir_job_manual(db, tipo, _TZ) for tipo in _JOBS_ATUALIZAR]
            res_por_tipo = dict(zip(_JOBS_ATUALIZAR, resultados))
            ids = _ids_lote(db, _JOBS_ATUALIZAR)
            itens = _status_lote(db, ids)
            # honesto: só diz "disparado" o que realmente foi inserido; o que já estava em
            # andamento (ou travado) é sinalizado, não escondido como concluído (bug 2026-07-28).
            nao_novos = [_LABEL_LOTE.get(t, t) for t, r in res_por_tipo.items() if r != "inserido"]
            if "inserido" not in resultados:
                msg = "ℹ️ Já há coleta na fila/execução. Aguarde concluir."
            elif nao_novos:
                msg = ("✅ Coleta disparada — o daemon processa em instantes. "
                       f"⚠ Já estava em andamento (não redisparado): {', '.join(nao_novos)}.")
            else:
                msg = "✅ Coleta disparada (backlog + HH) — o daemon processa em instantes."
            return (msg, ids, None, False, _toast_body("andamento", itens),
                    "hh-jobs-toast show andamento")
        except Exception:
            return ("⚠ Não foi possível disparar a coleta. Veja os logs.",) + _nop

    @app.callback(
        Output("hh-jobs-ids", "data", allow_duplicate=True),
        Output("hh-jobs-body", "children", allow_duplicate=True),
        Output("hh-jobs-toast", "className", allow_duplicate=True),
        Output("hh-jobs-poll", "disabled", allow_duplicate=True),
        Input("hh-jobs-reidratar", "n_intervals"),
        prevent_initial_call=True,
    )
    def _reidratar_toast(_n):
        """Ao montar a página (1 disparo): se já houver coleta em andamento, reabre o toast e
        religa o poll — o toast é efêmero e sumia num F5 no meio do job (o PCM podia achar que
        nada rodava e redisparar). Sem job ativo, não faz nada."""
        db = get_mongo_connection()
        if db is None:
            raise PreventUpdate
        ids = _ids_lote(db, _JOBS_ATUALIZAR)   # só jobs ATIVOS (pendente/executando)
        itens = _status_lote(db, ids)
        if not itens:
            raise PreventUpdate                # nada em andamento → toast fica fechado
        return ids, _toast_body("andamento", itens), "hh-jobs-toast show andamento", False

    @app.callback(
        Output("hh-jobs-body", "children", allow_duplicate=True),
        Output("hh-jobs-toast", "className", allow_duplicate=True),
        Output("hh-jobs-poll", "disabled", allow_duplicate=True),
        Output("hh-jobs-doneat", "data", allow_duplicate=True),
        Input("hh-jobs-poll", "n_intervals"),
        State("hh-jobs-ids", "data"),
        State("hh-jobs-doneat", "data"),
        prevent_initial_call=True,
    )
    def _poll_jobs(_n, ids, doneat):
        """Acompanha os jobs do lote (B28): amarelo enquanto roda; verde ao concluir todos
        (auto-fecha após 10s, contado aqui); vermelho + X se algum falhar (para o poll, não fecha)."""
        if not ids:
            raise PreventUpdate
        db = get_mongo_connection()
        if db is None:
            raise PreventUpdate
        itens = _status_lote(db, ids)
        if not itens:
            raise PreventUpdate
        status = [s for _, s in itens]
        if any(s == "falhou" for s in status):
            return _toast_body("falha", itens), "hh-jobs-toast show falha", True, no_update
        if all(s == "concluido" for s in status):
            # conta ticks do próprio Interval (2s cada) desde o 1º verde — determinístico, sem
            # depender de relógio/parsing. `doneat` guarda o n_intervals do 1º verde.
            if doneat is None:
                return _toast_body("ok", itens), "hh-jobs-toast show ok", False, _n
            if (_n - doneat) * 2 >= _TOAST_VERDE_SEG:
                return no_update, "hh-jobs-toast", True, None      # some + para o poll
            return _toast_body("ok", itens), "hh-jobs-toast show ok", False, no_update
        return _toast_body("andamento", itens), "hh-jobs-toast show andamento", False, no_update

    @app.callback(
        Output("hh-jobs-toast", "className", allow_duplicate=True),
        Output("hh-jobs-poll", "disabled", allow_duplicate=True),
        Input("hh-jobs-close", "n_clicks"),
        prevent_initial_call=True,
    )
    def _fechar_toast(n):
        """X do toast (só aparece no estado falha): fecha e para o poll."""
        if not n:
            raise PreventUpdate
        return "hh-jobs-toast", True
