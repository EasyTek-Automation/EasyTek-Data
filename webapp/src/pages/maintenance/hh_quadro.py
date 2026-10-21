# -*- coding: utf-8 -*-
"""Quadro semanal de planejamento de Hora-Homem — aba dentro de /maintenance/backlog.

Layout (DS-06): barra (seletor de semana + frescor + Atualizar agora) → dois quadros por
disciplina (Mecânica/Elétrica) em blocos técnico×dia (formato da planilha ELÉTRICA) com
rodapé de capacidade por turno → coluna "a planejar" (cards arrastáveis, sinais BR-19) →
"pendentes de classificação". Atribuição por drag-and-drop (asset assets/hh_dragdrop.js,
HTML5 nativo, offline) → grava em hh_planejamento (estado local; nunca vai ao SAP).

Render server-side em `render_board`; persistência e navegação em hh_quadro_callbacks.py.
"""
from dash import html, dcc
import dash_bootstrap_components as dbc

try:
    from src.utils import hh_data
    from src.utils import backlog_data as bd
except ImportError:
    from utils import hh_data
    from utils import backlog_data as bd


# opções do filtro de estado (B31): os rótulos default do status do usuário (hh_data._STATUS_USR_DEFAULT).
# O filtro casa contra `_status_usuario_label`, então combos (ex. ENPA PRIO→"Em Pausa") caem no rótulo.
_ESTADOS_ROTULOS = ("Aberta", "Em Tratamento", "Em Pausa", "Aceitação de Espera",
                    "Encerrada", "Cancelada")

# B52: caixinha coringa. Nem todo código do SAP tem tradução em `hh_status_usuario` — combos como
# `CBTN ENPA` caem no código cru, e há ordem sem estado nenhum. Sem esta opção, marcar "todos" faria
# essas ordens sumirem do quadro (1,8% do backlog do cliente medido em 2026-08-07). Ela recolhe
# qualquer rótulo fora dos 6 conhecidos, e continua valendo quando o SAP inventar um combo novo.
ESTADO_OUTROS = "__outros__"

_ESTADOS_OPCOES = ([{"label": r, "value": r} for r in _ESTADOS_ROTULOS]
                   + [{"label": "Outros / sem estado", "value": ESTADO_OUTROS}])

# Default do controle (B52): tudo marcado. O planejador desmarca o que não quer ver.
ESTADOS_DEFAULT = [o["value"] for o in _ESTADOS_OPCOES]


def _opcoes_linhas():
    """Opções do filtro de Linha (21 Linhas oficiais de `sap_ativos`). [] se Mongo indisponível
    — o dropdown fica vazio mas a UI não quebra."""
    try:
        return bd.opcoes_linhas(bd.carregar_ativos())
    except Exception:
        return []

LABEL_DISC = {"Mecanica": "Mecânica", "Eletrica": "Elétrica", "Terceiros": "Serviço de terceiros"}
DIAS = hh_data.DIAS_SEMANA  # Segunda..Domingo

# Teto de cards renderizados por lista (perf — evita payload de MBs / React montando milhares
# de nós). As listas já vêm ordenadas por relevância (carry-over/idade — BR-19); o excedente
# vira um contador "+N mais". Decisão de performance 2026-06-30.
MAX_CARDS_PLANEJAR = 60
MAX_CARDS_PENDENTES = 25


def _fmt_min(m):
    """Minutos → 'Xh YYm' compacto. None/0 → '—'."""
    if not m:
        return "—"
    h, mm = divmod(int(m), 60)
    return f"{h}h{mm:02d}" if h else f"{mm}min"


def _fmt_pct(p):
    """Fração → '%'. None → '—'."""
    return "—" if p is None else f"{p*100:.0f}%"


def board_content():
    """Conteúdo da aba 'Planejamento semanal' (montado dentro do dbc.Tab do backlog)."""
    return html.Div([
        # barra de controle
        dbc.Row([
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button([html.I(className="bi bi-chevron-left")], id="hh-sem-prev",
                               color="light", size="sm", title="Semana anterior"),
                    dbc.Button("Semana atual", id="hh-sem-label", color="light", size="sm", disabled=True),
                    dbc.Button([html.I(className="bi bi-chevron-right")], id="hh-sem-next",
                               color="light", size="sm", title="Próxima semana"),
                ]),
            ], width="auto"),
            dbc.Col(html.Span("—", id="hh-frescor", className="small text-muted"),
                    width="auto", className="d-flex align-items-center"),
            dbc.Col(
                dbc.Button([html.I(className="bi bi-layout-sidebar-inset me-1"),
                            html.Span("Modo leitura", id="hh-btn-modo-lbl")],
                           id="hh-btn-modo", color="light", size="sm",
                           title="Alternar entre dar mais espaço à fila (leitura) ou aos quadros (planejamento)"),
                width="auto", className="ms-auto",
            ),
            dbc.Col(
                dbc.Button([html.I(className="bi bi-arrow-clockwise me-1"), "Recarregar"],
                           id="hh-btn-recarregar", color="light", size="sm",
                           title="Renderizar o quadro de novo (relê do banco)"),
                width="auto",
            ),
            dbc.Col(
                dbc.Button([html.I(className="bi bi-funnel me-1"), "Filtrar a planejar"],
                           id="hh-btn-filtro", color="link", size="sm",
                           className="text-decoration-none p-0 me-2"),
                width="auto",
            ),
            dbc.Col(
                dbc.Button([html.I(className="bi bi-arrow-repeat me-1"), "Atualizar agora"],
                           id="hh-btn-refresh", color="secondary", outline=True, size="sm"),
                width="auto",
            ),
            # Emitir PDF do planejamento da semana (1 página por técnico) — botão ISOLADO,
            # fora do ButtonGroup de navegação (preservação de UI — BR-07). Read-only.
            dbc.Col(
                dbc.Button([html.I(className="bi bi-file-earmark-pdf me-1"), "Emitir PDF"],
                           id="hh-btn-pdf", color="primary", outline=True, size="sm",
                           title="Emitir o PDF do planejamento da semana (uma página por técnico)"),
                width="auto",
            ),
            # Exportar planilha da semana (análise gerencial/auditoria — B55) — botão ISOLADO ao
            # lado do PDF, fora dos agrupamentos existentes (preservação de UI). Read-only.
            dbc.Col(
                dbc.Button([html.I(className="bi bi-file-earmark-spreadsheet me-1"),
                            "Exportar planilha"],
                           id="hh-btn-xlsx", color="success", outline=True, size="sm",
                           title="Baixar a planilha com todos os dados da semana exibida"),
                width="auto",
            ),
            # Config de capacidade (disponível/turno + meta %) — botão ISOLADO, só nível 2+
            # (visibilidade controlada por callback). Fora dos agrupamentos (preservação de UI).
            dbc.Col(
                dbc.Button([html.I(className="bi bi-sliders me-1"), "Capacidade"],
                           id="hh-btn-capacidade", color="light", size="sm",
                           title="Ajustar horas disponíveis por turno e a meta de planejamento"),
                width="auto", id="hh-col-capacidade", style={"display": "none"},
            ),
            # Mão de obra temporária (GantManagement BR-25) — botão ISOLADO, só nível 2+,
            # desabilitado em semana encerrada (visibilidade/estado por callback).
            dbc.Col(
                dbc.Button([html.I(className="bi bi-person-plus me-1"), "Incluir mão de obra temporária"],
                           id="hh-btn-incluir-temp", color="light", size="sm",
                           title="Incluir mão de obra temporária no planejamento a partir desta semana"),
                width="auto", id="hh-col-incluir-temp", style={"display": "none"},
            ),
        ], className="mb-3 g-2 align-items-center"),
        # modal de filtro das ordens "a planejar"
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Filtrar ordens a planejar")),
            dbc.ModalBody([
                dbc.Label("Buscar (nº da ordem ou descrição)"),
                dbc.Input(id="hh-f-busca", type="text", placeholder="ex.: 5018 ou rolamento",
                          className="mb-3"),
                dbc.Checklist(id="hh-f-flags", className="mb-3", options=[
                    {"label": "Só com tempo planejado (planejado > 0)", "value": "plan_pos"},
                    {"label": "Só parcialmente planejadas (bolinha cinza)", "value": "nao_100"},
                    {"label": "Só com tempo lançado (realizado > 0)", "value": "com_real"},
                    {"label": "Só pendentes (não concluídas)", "value": "pendente"},
                ], value=[]),
                dbc.Label("Linha / ativo"),
                dcc.Dropdown(id="hh-f-linha", multi=True, className="mb-3",
                             options=_opcoes_linhas(), value=[],
                             placeholder="Todas as linhas"),
                dbc.Label("Estado (status do usuário)"),
                # B52: caixinhas sempre à vista, todas marcadas de saída — o planejador DESMARCA o
                # que não quer ver. `persistence local` guarda a escolha no navegador (mesmo
                # mecanismo de `backlog.py` e `hh_historico.py`); só o Estado é lembrado.
                dbc.Checklist(id="hh-f-estado", className="mb-3", options=_ESTADOS_OPCOES,
                              value=ESTADOS_DEFAULT, persistence=True,
                              persistence_type="local", persisted_props=["value"]),
                dbc.Label("Ordenar por"),
                dbc.Select(id="hh-f-ordenar", className="mb-2", value="relevancia", options=[
                    {"label": "Relevância (carry-over + idade)", "value": "relevancia"},
                    {"label": "Mais antiga", "value": "antiga"},
                    {"label": "Maior tempo planejado", "value": "planejado"},
                    {"label": "Menor aderência", "value": "aderencia"},
                    {"label": "Nº da ordem", "value": "ordem"},
                ]),
            ]),
            dbc.ModalFooter([
                dbc.Button("Limpar", id="hh-f-limpar", color="secondary", outline=True, size="sm"),
                dbc.Button("Aplicar", id="hh-f-aplicar", color="primary", size="sm"),
            ]),
        ], id="hh-modal-filtro", is_open=False),
        html.Div(id="hh-refresh-status", className="small text-muted mb-2"),
        # quadro (render server-side)
        dcc.Loading(html.Div(id="hh-board"), type="default"),
        # modal de replanejamento (remover/replanejar com justificativa — BR-16)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Replanejar — justificativa obrigatória")),
            dbc.ModalBody([
                html.Div(id="hh-replan-resumo", className="small text-muted mb-2"),
                dbc.Label("Motivo"),
                dbc.Select(id="hh-motivo", className="mb-2"),
                dbc.Label("Detalhe (obrigatório se 'Outro')"),
                dbc.Textarea(id="hh-motivo-texto", className="mb-1", style={"minHeight": "60px"}),
                html.Div(id="hh-replan-erro", className="small text-danger"),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="hh-replan-cancel", color="secondary", outline=True, size="sm"),
                dbc.Button("Confirmar remoção", id="hh-replan-confirm", color="danger", size="sm"),
            ]),
        ], id="hh-modal-replan", is_open=False),
        # modal de associação por botão direito num slot livre
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Associar ordem ao slot")),
            dbc.ModalBody([
                html.Div(id="hh-assoc-titulo", className="small text-muted mb-2"),
                dbc.Input(id="hh-assoc-busca", type="text", debounce=False,
                          placeholder="Buscar por nº da ordem ou descrição…", className="mb-2"),
                dcc.Loading(dbc.RadioItems(id="hh-assoc-results", options=[], value=None,
                                           className="hh-assoc-list"), type="default"),
                html.Div(id="hh-assoc-erro", className="small text-danger mt-1"),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="hh-assoc-cancel", color="secondary", outline=True, size="sm"),
                dbc.Button("OK — associar", id="hh-assoc-ok", color="primary", size="sm"),
            ]),
        ], id="hh-modal-assoc", is_open=False, scrollable=True),
        dcc.Store(id="hh-slot-context"),   # {tecnico, dia, disc, semana} (set pelo JS no botão direito)
        dcc.Store(id="hh-assoc-ctx"),       # contexto do slot enquanto o modal está aberto
        # modal de detalhe da ordem (B9 — clique simples no card)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Detalhe da ordem")),
            dbc.ModalBody(html.Div(id="hh-detalhe-body")),
        ], id="hh-modal-detalhe", is_open=False, size="lg", scrollable=True,
           className="hh-modal-wide"),   # B42: largura ampliada (min(1500px,95vw)) via CSS
        # modal de parcela (B20 — divisão no drop quando a carga do técnico/dia cruza a meta 70%)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(html.Span(id="hh-parcela-titulo"))),
            dbc.ModalBody([
                html.Div(id="hh-parcela-info", className="small mb-2"),
                html.Div(html.Div(id="hh-parcela-bar-fill", className="hh-parcela-bar-fill ok"),
                         className="hh-parcela-bar"),
                html.Div(id="hh-parcela-pct", className="small text-muted mt-1 mb-2"),
                dbc.Label("Horas neste dia:", className="small fw-bold mb-1"),
                dbc.RadioItems(id="hh-parcela-opcoes", options=[], value=None,
                               className="hh-parcela-opcoes"),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="hh-parcela-cancel", color="secondary",
                           outline=True, size="sm"),
                dbc.Button("Atribuir", id="hh-parcela-ok", color="primary", size="sm"),
            ]),
        ], id="hh-modal-parcela", is_open=False),
        dcc.Store(id="hh-parcela-ctx"),     # {ordem,func,dia,disc,semana,planejado,restante,carga,disp}
        # modal de confirmação de atribuição (B32 técnico comprometido + B33 disciplina cruzada):
        # avisos "moles" agregados; corpo montado no callback _gate_avisos
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("⚠ Confirmar atribuição")),
            dbc.ModalBody(html.Div(id="hh-comprom-body")),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="hh-comprom-cancel", color="secondary",
                           outline=True, size="sm"),
                dbc.Button("Confirmar mesmo assim", id="hh-comprom-ok", color="warning", size="sm"),
            ]),
        ], id="hh-modal-comprometido", is_open=False),
        # B49: bloqueio DURO ao planejar ordem sem tempo (planejado 0 no IW37) — só informa, não deixa
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Não dá para planejar")),
            dbc.ModalBody(html.Div(id="hh-bloqueio-body")),
            dbc.ModalFooter(dbc.Button("Entendi", id="hh-bloqueio-ok", color="secondary", size="sm")),
        ], id="hh-modal-bloqueio", is_open=False),
        dcc.Store(id="hh-comprom-ctx"),      # drop pendente de confirmação (mesmo shape do hh-drop-event)
        dcc.Store(id="hh-drop-confirmed"),   # drop já liberado (livre OU confirmado) → alimenta o _on_drop (B32)
        # modal de config de capacidade (B19 — nível 2+): disponível líquido por turno + meta %
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Capacidade de planejamento")),
            dbc.ModalBody([
                html.Div("Horas disponíveis por dia (jornada − almoço), por turno:",
                         className="small text-muted mb-2"),
                dbc.Row([
                    dbc.Col([dbc.Label("Turno A", className="small mb-0"),
                             dbc.Input(id="hh-cap-A", type="number", min=0, step=0.5, size="sm")], width=3),
                    dbc.Col([dbc.Label("Turno B", className="small mb-0"),
                             dbc.Input(id="hh-cap-B", type="number", min=0, step=0.5, size="sm")], width=3),
                    dbc.Col([dbc.Label("Turno C", className="small mb-0"),
                             dbc.Input(id="hh-cap-C", type="number", min=0, step=0.5, size="sm")], width=3),
                    dbc.Col([dbc.Label("ADM", className="small mb-0"),
                             dbc.Input(id="hh-cap-ADM", type="number", min=0, step=0.5, size="sm")], width=3),
                ], className="g-2 mb-3"),
                dbc.Label("Meta de planejamento (%)", className="small mb-0"),
                dbc.Input(id="hh-cap-meta", type="number", min=0, max=100, step=5, size="sm",
                          style={"maxWidth": "120px"}),
                html.Div("Acima da meta, o sistema abre o modal de divisão ao soltar a ordem. "
                         "É referência de planejamento — não trava.", className="small text-muted mt-1"),
                html.Div(id="hh-cap-msg", className="small mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="hh-cap-cancel", color="secondary", outline=True, size="sm"),
                dbc.Button("Salvar", id="hh-cap-salvar", color="primary", size="sm"),
            ]),
        ], id="hh-modal-capacidade", is_open=False),
        # modal: incluir mão de obra temporária (BR-25 item 4)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Incluir mão de obra temporária", id="hh-incluir-temp-titulo")),
            dbc.ModalBody([
                dcc.Dropdown(id="hh-incluir-temp-sel", options=[], placeholder="Escolha o funcionário",
                             clearable=False),
                html.Div(id="hh-incluir-temp-vazio", className="small text-muted mt-2"),
                html.Div("Vale desta semana em diante, até ser retirado. As semanas anteriores não mudam.",
                         className="small text-muted mt-2"),
                html.Div(id="hh-incluir-temp-msg", className="small mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="hh-incluir-temp-cancel", color="secondary", outline=True, size="sm"),
                dbc.Button("Incluir", id="hh-incluir-temp-ok", color="primary", size="sm"),
            ]),
        ], id="hh-modal-incluir-temp", is_open=False),
        # modal: retirar mão de obra temporária (BR-25 item 5) — confirmação ou bloqueio
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Retirar mão de obra temporária")),
            dbc.ModalBody(html.Div(id="hh-retirar-temp-body", className="small")),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="hh-retirar-temp-cancel", color="secondary", outline=True, size="sm"),
                dbc.Button("Retirar", id="hh-retirar-temp-ok", color="danger", size="sm"),
            ]),
        ], id="hh-modal-retirar-temp", is_open=False),
        dcc.Store(id="hh-retirar-temp-ctx"),       # {func, nome} aguardando confirmação
        # estado + infra
        dcc.Store(id="hh-card-click"),             # {ordem, ts} (set pelo JS no clique do card)
        dcc.Store(id="hh-filtro", data={}),        # filtro do painel 'a planejar'
        dcc.Store(id="hh-layout", data="planejamento", storage_type="session"),  # 'planejamento'|'fila'
        dcc.Store(id="hh-collapsed", data={}, storage_type="session"),  # recolhidos (persiste na sessão)
        dcc.Store(id="hh-semana"),                 # 'YYYY-Www' corrente do quadro
        dcc.Store(id="hh-drop-event"),             # {ordem, funcionario_id, dia, semana, ts} (set pelo JS)
        dcc.Store(id="hh-user-level", data=1),     # nível do usuário (gating de edição — SP-11)
        dcc.Store(id="hh-pending-remove"),         # {atrib_id, ordem, semana} aguardando justificativa
        dcc.Store(id="hh-refresh-board"),          # bump → re-render do quadro
        dcc.Interval(id="hh-interval-load", interval=500, max_intervals=1),
        dcc.Interval(id="hh-cooldown", interval=15000),
        # emissão do PDF do planejamento semanal (SDD relatorio-pdf-semanal)
        dcc.Download(id="hh-download-pdf"),
        dcc.Download(id="hh-download-xlsx"),   # planilha da semana (B55)
        # container SEMPRE presente no DOM p/ feedback (um dbc.Toast is_open=False não
        # renderiza até abrir → Output apontaria p/ componente inexistente = silent fail).
        html.Div(id="hh-pdf-msg",
                 style={"position": "fixed", "top": "70px", "right": "16px",
                        "zIndex": 1080, "minWidth": "320px"}),
        # toast de progresso da coleta (B28) — canto inferior-direito, SEMPRE no DOM (mesma razão
        # do hh-pdf-msg: um dbc.Toast is_open=False não renderiza → Output = silent fail). Cor e
        # visibilidade por className (CSS): amarelo enquanto roda; verde ao concluir (auto-fecha em
        # 10s, contado pelo poll); vermelho + X se algum falhar (não fecha sozinho). O X e o corpo
        # ficam sempre no DOM — o X aparece só no estado `falha` via CSS.
        html.Div([
            html.Button("×", id="hh-jobs-close", className="hh-jobs-x", n_clicks=0, title="Fechar"),
            html.Div(id="hh-jobs-body"),
        ], id="hh-jobs-toast", className="hh-jobs-toast"),
        dcc.Interval(id="hh-jobs-poll", interval=2000, disabled=True),
        # dispara 1x ao montar a página: reidrata o toast se já houver coleta em andamento
        # (o toast é efêmero — sem isso, um F5 no meio do job apagava o aviso e o PCM podia
        # achar que nada estava rodando).
        dcc.Interval(id="hh-jobs-reidratar", interval=800, n_intervals=0, max_intervals=1),
        dcc.Store(id="hh-jobs-ids"),      # _ids dos jobs do lote em acompanhamento
        dcc.Store(id="hh-jobs-doneat"),   # ISO do instante em que ficou verde (p/ auto-fechar 10s)
        # alvo do JS de drag-drop saber a semana corrente
        html.Span(id="hh-semana-dom", style={"display": "none"}),
    ], className="py-2")


# ---- render server-side --------------------------------------------------------------

def _ader_cls(ader):
    """Classe de cor da aderência: verde >=90%, âmbar 60-90%, vermelho <60%."""
    if ader is None:
        return ""
    if ader >= 0.9:
        return "hh-ader-ok"
    if ader >= 0.6:
        return "hh-ader-mid"
    return "hh-ader-low"


def _card_ordem(o, arrastavel, can_edit):
    """Card de uma ordem (na lista 'a planejar' ou num slot). Arrastável se permitido.

    Em slot atribuído (`_atrib_id`), botão de remover (modal de justificativa — BR-16).
    Borda por estado (pendente/ok) e aderência colorida (BR-17).
    """
    ader = o.get("aderencia")
    sub = []
    if o.get("_idade_dias") is not None:
        sub.append(html.Span(f"{o['_idade_dias']}d", className="hh-pill hh-pill-idade",
                             title="Idade da ordem (dias em aberto)"))
    if o.get("_carry_over"):
        sub.append(html.Span(f"⟳ {o['_carry_over']}sem", className="hh-pill hh-pill-carry",
                             title="Planejada em semanas anteriores e não cumprida"))
    # status do usuário (B30 / decisão 2026-07-15): o estado da ordem — aberta OU já saída do backlog
    # — é o STATUS DO USUÁRIO (Em Tratamento / Em Pausa / Encerrada / Cancelada …). Dá mais recurso ao
    # PCM que o "pendente" binário e é o mesmo critério pra ordem viva e pra que saiu. Fallbacks:
    # "aguardando fechamento" (saiu, daemon ainda não congelou) → "saiu do backlog" (congelou mas sem
    # USTXT) → "pendente" (ordem viva sem status mapeado).
    _stu = o.get("_status_usuario_label")
    if _stu:
        _cor = o.get("_status_usuario_cor")   # aberta=vermelho / andamento=amarelo / encerrada=verde / cancelada=cinza
        _cls = "hh-pill hh-pill-statususr" + (f" hh-pill-usr-{_cor}" if _cor else "")
        sub.append(html.Span(_stu, className=_cls,
                             title="Status do usuário da ordem no SAP"))
    elif o.get("_aguardando_fechamento"):
        sub.append(html.Span("aguardando fechamento", className="hh-pill hh-pill-aguardando",
                             title="Ordem saiu do backlog; aguardando o daemon congelar o resultado"))
    elif o.get("_saiu_backlog"):
        sub.append(html.Span("saiu do backlog", className="hh-pill hh-pill-aguardando",
                             title="Ordem saiu do backlog; status do usuário ainda não obtido"))
    elif o.get("_pendente"):
        sub.append(html.Span("pendente", className="hh-pill hh-pill-pend",
                             title="Ordem não concluída no SAP (pendência derivada do status)"))
    # ordem parcialmente planejada, ainda NA FILA: quanto falta distribuir (B20). No card do slot
    # (planejado) a completude é dada pela bolinha (B22), não pela pill — evita redundância.
    _rest = o.get("_restante_min"); _plan = o.get("planejado_min") or 0
    if not o.get("_atrib_id") and _rest is not None and _plan and 0 < _rest < _plan:
        sub.append(html.Span(f"restante {_fmt_min(_rest)}", className="hh-pill hh-pill-restante",
                             title="Parte desta ordem já foi planejada; falta distribuir o restante"))
    atrib_id = o.get("_atrib_id")
    # tarja colorida por classificação: azul Mecânica / laranja Elétrica / roxo Terceiros /
    # vermelho Não classif.
    disc_cls = {"Mecanica": " disc-mec", "Eletrica": " disc-ele",
                "Terceiros": " disc-ter"}.get(o.get("disciplina"), " disc-nc")
    topo = [html.Span(str(o.get("ordem")), className="hh-card-ord me-1"),
            html.Span(o.get("descricao", "") or "", className="hh-card-desc text-truncate flex-grow-1")]
    filhos = []
    if atrib_id and can_edit:
        # ✂ acima do número da ordem (não no canto) — abre o modal de divisão
        filhos.append(html.Button("✂", id={"type": "hh-split", "atrib": str(atrib_id),
                                            "ordem": str(o.get("ordem"))},
                                  className="hh-card-split",
                                  title="Dividir esta ordem em partes (dias/técnicos)"))
    filhos.append(html.Div(topo, className="d-flex align-items-center"))
    linha_nome = o.get("linha_nome")
    if linha_nome:
        filhos.append(html.Div(
            html.Span(linha_nome, className="hh-pill hh-pill-linha text-truncate",
                      title=f"Linha: {linha_nome}"),
            className="hh-card-linha"))
    parcela = o.get("parcela_min")
    if parcela is not None:
        # card num slot dividido: mostra a fração desta parcela (de quanto é a ordem inteira)
        primeiro = html.Span(f"parcela {_fmt_min(parcela)} de {_fmt_min(o.get('planejado_min'))}",
                             className="me-2 hh-parcela-badge")
    else:
        primeiro = html.Span(f"plan {_fmt_min(o.get('planejado_min'))}", className="me-2 text-muted")
    filhos.append(
        html.Div([
            primeiro,
            html.Span(f"real {_fmt_min(o.get('realizado_min'))}", className="me-2 text-muted"),
            html.Span(_fmt_pct(ader), className=_ader_cls(ader)),
        ], className="hh-card-nums"))
    if sub:
        filhos.append(html.Div(sub, className="mt-1"))
    if atrib_id and can_edit:
        filhos.append(html.Button("×", id={"type": "hh-remove", "atrib": str(atrib_id),
                                           "ordem": str(o.get("ordem"))},
                                  className="hh-card-rm",
                                  title="Remover do plano (com justificativa)"))
    if atrib_id:
        # bolinha canto inferior-direito (B22): verde = ordem 100% planejada (nada a distribuir);
        # cinza = ainda sobra tempo dela para planejar em outro dia/técnico
        rest = o.get("_restante_min")
        plena = rest is not None and rest <= 0
        filhos.append(html.Span(
            className="hh-card-dot " + ("full" if plena else "partial"),
            title=("Ordem 100% planejada" if plena
                   else f"Ainda faltam {_fmt_min(rest)} desta ordem para planejar")))
    return html.Div(filhos, className="hh-card" + disc_cls,
                    draggable="true" if (arrastavel and can_edit) else "false",
                    **{"data-hh-ordem": str(o.get("ordem")),
                       "data-hh-disc": o.get("disciplina") or "NaoClassificado",
                       "data-hh-linha": o.get("_linha_id") or ""})


def _barra_ocupacao_dia(carga, disponivel, meta_pct):
    """Barra fina de ocupação do técnico no dia (B21): verde ≤ meta, amarelo meta–100%, vermelho
    > 100%. Retorna None se não há disponível calculável (turno sem jornada)."""
    if not disponivel or disponivel <= 0:
        return None
    pct = carga / disponivel
    meta = meta_pct or 0.70
    zona = "ok" if pct <= meta else ("warn" if pct <= 1.0 else "over")
    w = max(3, min(pct, 1.0) * 100)
    titulo = f"{_fmt_min(carga)} de {_fmt_min(disponivel)} ({pct * 100:.0f}% do dia)"
    return html.Div(html.Span(style={"width": f"{w:.0f}%"}),
                    className=f"hh-slot-cap {zona}", title=titulo)


def _carga_dia(ordens):
    """Soma dos minutos planejados atribuídos a um técnico num dia (parcela ou ordem inteira)."""
    return sum(int(o["parcela_min"]) if o.get("parcela_min") is not None
               else int(o.get("planejado_min") or 0) for o in ordens)


def _cap_cell(ordens, disponivel, meta_pct):
    """Célula da faixa de ocupação (B21): uma barra fina do dia do técnico, alinhada no topo."""
    barra = _barra_ocupacao_dia(_carga_dia(ordens), disponivel, meta_pct)
    return html.Td(barra if barra else html.Span(), className="hh-cap-cell")


def _slot(tec_id, dia, ordens, can_edit, disc, linhas=None, estados=None):
    """Célula (dropzone) técnico×dia com as ordens atribuídas. Vazia mostra hint no arraste.

    `disc` = disciplina do quadro (Mecanica/Eletrica) — usada para repelir drop de ordem de
    outra disciplina (só aceita ordem da mesma disciplina; senão a ordem volta para a fila).
    `linhas` = filtro de Linha ativo (B16): esconde os cards atribuídos que não são da linha
    selecionada (escopo "quadro inteiro"); o slot em si continua sendo dropzone.
    `estados` = filtro de estado (B31/B52), mesmo escopo; `None` = não filtrar.
    """
    attrs = {"data-hh-tecnico": str(tec_id), "data-hh-dia": str(dia), "data-hh-disc": disc}
    titulo = "Botão direito: associar ordem" if can_edit else None
    if linhas:
        ordens = [o for o in ordens if _passa_linha(o, linhas)]
    if estados is not None:                   # B52: None = filtro nunca aplicado → não filtra
        ordens = [o for o in ordens if _passa_status(o, estados)]
    if ordens:
        conteudo = [_card_ordem(o, arrastavel=True, can_edit=can_edit) for o in ordens]
        cls = "hh-slot"
    else:
        conteudo = [html.Span("livre", className="hh-slot-hint")]
        cls = "hh-slot hh-slot-vazio"
    return html.Td(html.Div(conteudo, className=cls, title=titulo, **attrs))


def _rodape_turno(cap, turnos, meta_pct=0.70):
    """Linhas de resumo por turno (no TOPO do quadro): nº de ordens + Programado/Disponível
    com barra de ocupação + % programado, por dia. Barra segue a regra de zona única
    (laranja < meta / azul meta–100% / amarelo > 100%), igual às demais barras de ocupação."""
    meta = meta_pct or 0.70
    linhas = []
    for turno in turnos:
        por_dia = cap.get(turno, {})
        cels = [html.Th(f"Turno {turno}", className="hh-cap-turno")]
        for dia in range(7):
            d = por_dia.get(dia, {})
            pct = d.get("pct_programado")
            zona = "zero" if pct is None else ("ok" if pct <= meta else ("warn" if pct <= 1.0 else "over"))
            largura = f"{min(pct, 1.0) * 100:.0f}%" if pct is not None else "0%"
            n = d.get("n_ordens") or 0
            cels.append(html.Td([
                html.Div(f"{n} {'ordem' if n == 1 else 'ordens'}",
                         className="hh-cap-nord" + (" text-muted" if n == 0 else "")),
                html.Div(f"{_fmt_min(d.get('programado'))} / {_fmt_min(d.get('disponivel'))}",
                         className="hh-cap-vals"),
                html.Div(html.Span(style={"width": largura}), className=f"hh-cap-bar {zona}"),
                # cor do número segue a MESMA zona de ocupação da barra (não a aderência) —
                # número, barra e cor concordam (laranja < meta / azul meta–100% / âmbar > 100%).
                html.Div(_fmt_pct(pct), className=f"hh-cap-vals hh-ocup-txt {zona}"),
            ]))
        linhas.append(html.Tr(cels, className="hh-cap-row"))
    return linhas


_DISC_META = {"Mecanica": ("hh-mec", "bi-gear-fill"), "Eletrica": ("hh-ele", "bi-lightning-charge-fill"),
              "Terceiros": ("hh-ter", "bi-people-fill")}


def _fmt_delta(delta):
    """Variação vs semana passada como '▲ +20%' / '▼ −12%' / '—'. Cor pela marca (quadro
    interno de planejamento do PCM): ▲ mais planejado = melhor = azul; ▼ menos = pior =
    laranja (classes up/down no CSS). '•' (zero) e '—' (sem base na semana passada) neutros."""
    if delta is None:
        return html.Span("—", className="hh-diahdr-delta zero", title="Sem planejado no mesmo dia da semana passada")
    seta = "▲" if delta > 0 else ("▼" if delta < 0 else "•")
    cls = "up" if delta > 0 else ("down" if delta < 0 else "zero")
    return html.Span(f"{seta} {'+' if delta > 0 else ('−' if delta < 0 else '')}{abs(delta)*100:.0f}%",
                     className=f"hh-diahdr-delta {cls}")


def _dia_indicador(nome, r, meta_pct):
    """Cabeçalho de UM dia como indicador (B44): nome + Δ% vs semana passada + barra
    planejado×disponível (cor da zona igual à faixa B21) + 'Xh / Yh'. `r` = entrada de
    `resumo_dias[dia]`; None → só o nome (dias sem dado)."""
    if not r:
        return html.Th(nome)
    plan, disp = r.get("programado") or 0, r.get("disponivel")
    pct = r.get("pct_programado")
    meta = meta_pct or 0.70
    zona = "zero"
    largura = "0%"
    if pct is not None:
        zona = "ok" if pct <= meta else ("warn" if pct <= 1.0 else "over")
        largura = f"{max(3, min(pct, 1.0) * 100):.0f}%"
    titulo = f"Planejado {_fmt_min(plan)} de {_fmt_min(disp)} disponível" + (
        f" ({pct*100:.0f}%)" if pct is not None else "")
    return html.Th([
        html.Div(nome, className="hh-diahdr-nome"),
        _fmt_delta(r.get("delta_pct")),
        html.Div(html.Span(style={"width": largura}), className=f"hh-diahdr-bar {zona}", title=titulo),
        html.Div(f"{_fmt_min(plan)} / {_fmt_min(disp)}", className="hh-diahdr-vals"),
        # % de ocupação (planejado ÷ disponível), colorido pela MESMA zona da barra
        # (laranja < meta / azul meta–100% / âmbar > 100%) — número e barra concordam.
        html.Div(_fmt_pct(pct), className=f"hh-diahdr-pct hh-ocup-txt {zona}"),
    ], className="hh-diahdr")


def _cabecalho_dias_fixo(resumo_dias=None, meta_pct=0.70):
    """Cabeçalho ÚNICO (Técnico + dias da semana) fixo na rolagem, compartilhado pelos dois
    quadros (Mecânica/Elétrica). Fica FORA do wrapper de overflow das tabelas — senão a
    stickiness cola no topo do wrapper (que rola junto) em vez da coluna. Cola no topo da coluna
    rolável via `.hh-headfix-wrap`. Alinha com as tabelas porque todas usam `table-layout: fixed`
    com 8 colunas de mesma largura.

    B44: cada dia vira indicador (barra planejado×disponível da fábrica + Δ% vs semana passada)
    quando `resumo_dias` é fornecido; sem ele, degrada para o cabeçalho de texto simples."""
    if resumo_dias:
        celulas = [html.Th("Técnico", className="hh-diahdr-tec")] + [
            _dia_indicador(d, resumo_dias.get(i), meta_pct) for i, d in enumerate(DIAS)]
    else:
        celulas = [html.Th("Técnico")] + [html.Th(d) for d in DIAS]
    head = html.Thead(html.Tr(celulas))
    return html.Div(dbc.Table(head, className="hh-quadro hh-headfix"),
                    className="hh-headfix-wrap")


def _quadro_disciplina(disc, dados, can_edit, collapsed=False, linhas=None, estados=None,
                       semana_aberta=True):
    """Um quadro de disciplina: cabeçalho (ícone/cor + chevron colapsar) + tabela + rodapé.

    `collapsed=True` → mostra só o cabeçalho (tabela oculta). Estado vem do store hh-collapsed.
    `linhas` = filtro de Linha ativo (B16); `estados` = filtro de estado/status do usuário (B31) —
    ambos repassados aos slots (escondem cards que não batem o filtro).
    `semana_aberta=False` (semana encerrada) desabilita o "retirar" do temporário (SP-17.10).
    """
    tecnicos = dados["tecnicos"]
    cap = dados["capacidade"]
    meta_pct = dados.get("meta_pct", 0.70)
    turnos = sorted({t["turno"] for t in tecnicos} - {""})
    cls_cor, icone = _DISC_META.get(disc, ("", "bi-tools"))
    # cabeçalho clicável (chevron+ícone+texto+contador) — colapso 100% client-side (data-attrs);
    # o Select fica FORA da área clicável.
    area_click = html.Div([
        html.I(className=("bi bi-chevron-right" if collapsed else "bi bi-chevron-down") + " hh-chev"),
        html.Span(html.I(className=f"bi {icone}"), className="hh-disc-icon"),
        html.Span(LABEL_DISC.get(disc, disc)),
        html.Span(f"{len(tecnicos)} técnicos", className="hh-disc-count"),
    ], className="hh-head-click", title="Recolher / expandir",
       **{"data-hh-collapse-key": disc})
    cab = [area_click]
    fora = dados.get("disponiveis_fora") or []
    if can_edit and fora:
        cab.append(dbc.Select(
            id={"type": "hh-tec-add", "disc": disc}, size="sm",
            options=[{"label": "+ Técnico", "value": ""}]
                    + [{"label": f["nome"], "value": f["id"]} for f in fora],
            value="", className="hh-tec-add ms-2",
        ))
    cabecalho = html.Div(cab, className="hh-disc-head")
    # tabela SEMPRE renderizada; o colapso só esconde via display (client-side, sem re-render).
    # SEM thead próprio: o cabeçalho de dias é único e fixo (`_cabecalho_dias_fixo`, no topo da
    # coluna). A 1ª linha (rodapé de turno) governa as larguras via table-layout:fixed.
    corpo = []
    for i, t in enumerate(tecnicos):
        nome_cel = [html.Div(t["nome"], className="hh-tec-nome flex-grow-1"),
                    html.Span(f"Turno {t['turno']}", className="hh-turno-pill")]
        if t.get("temporario"):
            # temporário (BR-25): etiqueta + "retirar" NO LUGAR do × (decisão RV-14); fixo intacto
            nome_cel[-1] = html.Span([nome_cel[-1],
                                      html.Span("Temporária", className="hh-turno-pill hh-temp-pill ms-1")])
            if can_edit:
                nome_cel.insert(1, html.Button(
                    "retirar", id={"type": "hh-temp-ret", "func": t["funcionario_id"]},
                    className="hh-temp-ret", disabled=not semana_aberta,
                    title=("Retirar do planejamento a partir desta semana" if semana_aberta
                           else "semana encerrada")))
        elif can_edit:
            nome_cel.insert(1, html.Button(
                "×", id={"type": "hh-tec-rem", "disc": disc, "func": t["funcionario_id"]},
                className="hh-tec-rem", title=f"Remover de {LABEL_DISC.get(disc, disc)}"))
        row_cls = "hh-tec-row" + (" hh-row-alt" if i % 2 else "")
        # nome ocupa as DUAS linhas (faixa de ocupação + linha dos cards) via rowspan
        name_td = html.Td(html.Div([
                html.Div([nome_cel[0]] + ([nome_cel[1]] if can_edit else []),
                         className="d-flex align-items-start"),
                nome_cel[-1],
             ]), className="hh-tec-cell", rowSpan=2)
        disp = t.get("disponivel_min")
        # 1ª linha do técnico: FAIXA de ocupação (B21) — barras alinhadas no topo, contorno
        # reservado, uma por dia da semana. Carga real (não filtrada por linha).
        corpo.append(html.Tr(
            [name_td] + [_cap_cell(t["dias"][dia], disp, meta_pct) for dia in range(7)],
            className=row_cls + " hh-caprow",
        ))
        # 2ª linha: os slots (cards)
        corpo.append(html.Tr(
            [_slot(t["funcionario_id"], dia, t["dias"][dia], can_edit, disc, linhas, estados)
             for dia in range(7)],
            className=row_cls + " hh-slotrow",
        ))
    tabela = dbc.Table(html.Tbody(_rodape_turno(cap, turnos, meta_pct) + corpo),
                       className="hh-quadro")
    body = html.Div(html.Div(tabela, style={"overflowX": "auto"}),
                    style={"display": "none"} if collapsed else {},
                    **{"data-hh-collapse-body": disc})
    return html.Div([cabecalho, body], className=f"hh-disc-card {cls_cor} mb-3")


def _mais(n_total, n_mostrado):
    """Rodapé 'mostrando X de Y — +Z mais' quando a lista foi limitada (perf)."""
    extra = n_total - n_mostrado
    if extra <= 0:
        return None
    return html.Div(f"mostrando {n_mostrado} de {n_total} — +{extra} mais (use filtros/ordenação)",
                    className="hh-mais")


def _passa_linha(o, linhas):
    """True se a ordem pertence a uma das linhas selecionadas (ou nenhuma selecionada → tudo passa).
    `linhas` = lista de ids de Linha (`_linha_id`, resolvido do TPLNR contra `sap_ativos`)."""
    return (not linhas) or (o.get("_linha_id") in linhas)


def _passa_status(o, estados):
    """True se o estado (status do usuário) da ordem está entre os marcados. `estados` = lista de
    rótulos (Aberta/Em Pausa/Encerrada/…) casados contra `_status_usuario_label`, mais o coringa
    `ESTADO_OUTROS`, que aceita qualquer rótulo fora dos 6 conhecidos — inclusive código cru sem
    tradução (`CBTN ENPA`) e ordem sem estado (B52).

    Semântica desde o B52: lista VAZIA = nada passa (o planejador desmarcou tudo). "Não filtrar" é
    `estados=None` — quem chama trata isso antes (ver `aplicar_filtro_ordens`). Até o B31, vazio
    significava "passa tudo"; a inversão veio junto com as caixinhas marcadas por padrão."""
    if not estados:
        return False
    lab = o.get("_status_usuario_label")
    if lab in estados:
        return True
    return ESTADO_OUTROS in estados and lab not in _ESTADOS_ROTULOS


def aplicar_filtro_ordens(lista, filtro):
    """Filtra e ordena uma lista de ordens 'a planejar' conforme o filtro do painel.

    filtro = {busca, planejado_pos(bool), nao_100(bool), com_realizado(bool), so_pendentes(bool),
    linhas(list), ordenar}. `nao_100` = parcialmente planejada (0 < restante < planejado — bolinha
    cinza). Não muta a entrada. ordenar ∈ relevancia(default) | antiga | planejado | aderencia | ordem.
    """
    filtro = filtro or {}
    out = list(lista)
    busca = (filtro.get("busca") or "").strip().lower()
    if busca:
        out = [o for o in out if busca in str(o.get("ordem", "")).lower()
               or busca in (o.get("descricao") or "").lower()]
    linhas = filtro.get("linhas") or []
    if linhas:
        out = [o for o in out if _passa_linha(o, linhas)]
    estados = filtro.get("estados")           # B52: None = filtro nunca aplicado → não filtra
    if estados is not None:
        out = [o for o in out if _passa_status(o, estados)]
    if filtro.get("planejado_pos"):
        out = [o for o in out if (o.get("planejado_min") or 0) > 0]
    if filtro.get("nao_100"):   # parcialmente planejada (bolinha cinza): 0 < restante < planejado
        out = [o for o in out
               if 0 < (o.get("_restante_min") or 0) < (o.get("planejado_min") or 0)]
    if filtro.get("com_realizado"):
        out = [o for o in out if (o.get("realizado_min") or 0) > 0]
    if filtro.get("so_pendentes"):
        out = [o for o in out if o.get("_pendente")]
    ordenar = filtro.get("ordenar") or "relevancia"
    if ordenar == "antiga":
        out.sort(key=lambda o: -(o.get("_idade_dias") or 0))
    elif ordenar == "planejado":
        out.sort(key=lambda o: -(o.get("planejado_min") or 0))
    elif ordenar == "aderencia":
        out.sort(key=lambda o: (o.get("aderencia") is None, o.get("aderencia") or 0))
    elif ordenar == "ordem":
        out.sort(key=lambda o: str(o.get("ordem")))
    else:  # relevancia: carry-over depois idade (default da BR-19)
        out.sort(key=lambda o: (-(o.get("_carry_over") or 0), -(o.get("_idade_dias") or 0)))
    return out


def _filtra_localizacao(lista, filtro):
    """Só os filtros de LOCALIZAÇÃO (busca por nº/descrição + linha) — para a coluna de
    pendentes de classificação. Ordens não classificadas não são planejáveis, mas devem ser
    LOCALIZÁVEIS: buscar um número de ordem tem de achá-la aqui mesmo sem estar classificada.
    Não aplica flags/ordenação de planejamento (não fazem sentido no pendente) nem reordena."""
    filtro = filtro or {}
    out = list(lista)
    busca = (filtro.get("busca") or "").strip().lower()
    if busca:
        out = [o for o in out if busca in str(o.get("ordem", "")).lower()
               or busca in (o.get("descricao") or "").lower()]
    linhas = filtro.get("linhas") or []
    if linhas:
        out = [o for o in out if _passa_linha(o, linhas)]
    estados = filtro.get("estados")           # B52: None = filtro nunca aplicado → não filtra
    if estados is not None:
        out = [o for o in out if _passa_status(o, estados)]
    return out


def _side_card(grp, titulo, icone, corpo, total, collapsed, cls_cor="", head_style=None):
    """Card lateral com cabeçalho INTEIRO colapsável (client-side) + corpo sempre montado."""
    cab = html.Div([
        html.I(className=("bi bi-chevron-right" if collapsed else "bi bi-chevron-down") + " hh-chev"),
        html.I(className=f"bi {icone} me-1"),
        html.Span(titulo),
        html.Span(str(total), className="hh-disc-count"),
    ], className="hh-side-head hh-head-click", style=head_style or {},
       title="Recolher / expandir", **{"data-hh-collapse-key": grp})
    body = html.Div(corpo, className="hh-side-body",
                    style={"display": "none"} if collapsed else {},
                    **{"data-hh-collapse-body": grp})
    return html.Div([cab, body], className=f"hh-side-card {cls_cor} mb-3")


def _coluna_a_planejar(a_planejar, pendentes, can_edit, collapsed=None, filtro=None, terceiros=None):
    """Painel lateral: cards 'a planejar' por disciplina + Terceiros (coringa, B15) + pendentes.
    Grupos colapsáveis.

    `filtro` (do modal) filtra/ordena as listas antes do teto MAX_CARDS_*.
    """
    collapsed = collapsed or {}
    blocos = []
    for disc in ("Mecanica", "Eletrica"):
        cls_cor, icone = _DISC_META.get(disc, ("", "bi-tools"))
        ordens = aplicar_filtro_ordens(a_planejar.get(disc, []), filtro)
        vis = ordens[:MAX_CARDS_PLANEJAR]
        corpo = [_card_ordem(o, arrastavel=True, can_edit=can_edit) for o in vis] \
            or [html.Div("Nada a planejar.", className="text-muted small")]
        rod = _mais(len(ordens), len(vis))
        if rod:
            corpo.append(rod)
        blocos.append(_side_card(f"ap-{disc}", f"A planejar — {LABEL_DISC[disc]}", icone,
                                 corpo, len(ordens), collapsed.get(f"ap-{disc}"), cls_cor))
    # Terceiros (Z03): fila própria; cada card é arrastável para QUALQUER um dos dois quadros
    if terceiros:
        cls_cor, icone = _DISC_META.get("Terceiros", ("", "bi-people-fill"))
        ordens = aplicar_filtro_ordens(terceiros, filtro)
        vis = ordens[:MAX_CARDS_PLANEJAR]
        corpo = [_card_ordem(o, arrastavel=True, can_edit=can_edit) for o in vis] \
            or [html.Div("Nada a planejar.", className="text-muted small")]
        rod = _mais(len(ordens), len(vis))
        if rod:
            corpo.append(rod)
        corpo.append(html.Div("Arraste para o quadro Mecânica ou Elétrica.",
                              className="text-muted small mt-1"))
        blocos.append(_side_card("ap-Terceiros", f"A planejar — {LABEL_DISC['Terceiros']}", icone,
                                 corpo, len(ordens), collapsed.get("ap-Terceiros"), cls_cor))
    # pendentes: filtros de LOCALIZAÇÃO (busca por número/descrição + linha) para achar uma ordem
    # não classificada pelo número. As flags de completude (planejado>0 / parcialmente planejada)
    # TAMBÉM se aplicam — como pendentes não são planejáveis, ativá-las esconde a coluna (limpa a
    # vista quando o PCM quer ver só o que dá pra planejar). Ordenação de planejamento não se aplica.
    pend = _filtra_localizacao(pendentes, filtro)
    if (filtro or {}).get("planejado_pos"):
        pend = [o for o in pend if (o.get("planejado_min") or 0) > 0]
    if (filtro or {}).get("nao_100"):
        pend = [o for o in pend if 0 < (o.get("_restante_min") or 0) < (o.get("planejado_min") or 0)]
    if pend:
        vis = pend[:MAX_CARDS_PENDENTES]
        corpo = [_card_ordem(o, arrastavel=False, can_edit=can_edit) for o in vis]
        rod = _mais(len(pend), len(vis))
        if rod:
            corpo.append(rod)
        corpo.append(html.Div("Classifique no SAP para liberar a atribuição.",
                              className="text-muted small mt-1"))
        blocos.append(_side_card("pendentes", "Pendente de classificação", "bi-exclamation-triangle",
                                 corpo, len(pend), collapsed.get("pendentes"),
                                 head_style={"borderLeftColor": "var(--bs-danger)"}))
    return blocos


def _kpi_box(rotulo, valor, cls=""):
    """Caixinha de KPI do modal de detalhe."""
    return html.Div([
        html.Div(rotulo, className="text-muted small text-uppercase", style={"letterSpacing": ".4px"}),
        html.Div(valor, className="fw-bold " + cls, style={"fontSize": "1.3rem", "lineHeight": "1.1"}),
    ], className="hh-det-kpi")


def modal_detalhe(det):
    """Corpo do modal de detalhe da ordem (B9) — cabeçalho + KPIs + operações + atribuições +
    histórico de replanejamento. `det` = dict de hh_data.detalhe_ordem."""
    if det is None:
        return dbc.Alert("Ordem não encontrada ou banco indisponível.", color="warning")
    h = det["header"]
    t = det["totais"]
    disc = h.get("disciplina")
    disc_cls = {"Mecanica": "hh-mec", "Eletrica": "hh-ele"}.get(disc, "")
    disc_lbl = LABEL_DISC.get(disc, "Não classificado")

    # cabeçalho
    cab = html.Div([
        html.Div([
            html.Span(det["ordem"], className="hh-card-ord", style={"fontSize": "1.4rem"}),
            html.Span(disc_lbl, className="hh-turno-pill ms-2"),
            html.Span("pendente" if h.get("pendente") else "concluída",
                      className="hh-pill " + ("hh-pill-pend" if h.get("pendente") else ""),
                      style={} if h.get("pendente") else {"background": "var(--bs-success-bg-subtle)",
                                                           "color": "var(--bs-success)"}),
        ], className="d-flex align-items-center gap-1 mb-1"),
        html.Div(h.get("descricao") or "—", className="text-muted"),
    ], className=f"hh-det-head {disc_cls} mb-3")

    # KPIs
    kpis = dbc.Row([
        dbc.Col(_kpi_box("Planejado", _fmt_min(t.get("planejado_min"))), width="auto"),
        dbc.Col(_kpi_box("Realizado", _fmt_min(t.get("realizado_min"))), width="auto"),
        dbc.Col(_kpi_box("Aderência", _fmt_pct(t.get("aderencia")), _ader_cls(t.get("aderencia"))), width="auto"),
        dbc.Col(_kpi_box("Idade", f"{t['idade_dias']}d" if t.get("idade_dias") is not None else "—"), width="auto"),
        dbc.Col(_kpi_box("Carry-over", f"{t.get('carry_over') or 0} sem"), width="auto"),
    ], className="g-3 mb-3")

    # ficha técnica
    def _linha(rot, val):
        # B42: bloco (não inline) — na coluna lateral estreita a ficha fica vertical e legível
        return html.Div([html.Span(rot + ": ", className="text-muted small"),
                         html.Span(val or "—", className="small")], className="hh-det-ficha-linha")
    ficha = html.Div([
        _linha("Categoria", h.get("categoria")),
        _linha("Linha", h.get("linha_nome")),
        _linha("Local", h.get("local_instalacao")),
        _linha("Status", h.get("status_usuario_label")),      # B30: status do usuário (rico)
        _linha("Status SAP", h.get("status_label")),
        _linha("Criação", h["data_criacao"].strftime("%d/%m/%Y") if h.get("data_criacao") else None),
        _linha("Início prog.", h["data_inicio"].strftime("%d/%m/%Y") if h.get("data_inicio") else None),
        _linha("Executores", ", ".join(t.get("executores") or []) or None),
    ], className="mb-3 p-2 rounded", style={"background": "var(--bs-tertiary-bg)"})

    # operações
    ops = det.get("operacoes") or []
    if ops:
        linhas = [html.Tr([
            html.Td(op["operacao"]),
            html.Td(op.get("texto") or "—", className="small"),
            html.Td(_fmt_min(op["planejado_min"]), className="text-end"),
            html.Td(_fmt_min(op["realizado_min"]), className="text-end"),
            html.Td(_fmt_pct(op["aderencia"]), className="text-end " + _ader_cls(op["aderencia"])),
            html.Td(op.get("centro") or "—"), html.Td(", ".join(op.get("executores") or []) or "—"),
            html.Td(op.get("status") or "—"),
        ]) for op in ops]
        tab_ops = dbc.Table([
            html.Thead(html.Tr([html.Th("Op."), html.Th("Descrição"), html.Th("Plan.", className="text-end"),
                                html.Th("Real.", className="text-end"), html.Th("Ader.", className="text-end"),
                                html.Th("Centro"), html.Th("Executor(es)"), html.Th("Status")])),
            html.Tbody(linhas)], size="sm", hover=True, className="mb-0")
        # B54: a coluna "Real." é rateio, não medição por operação — o apontamento é lançado numa
        # operação só e cobre a ordem inteira. Sem esta nota o número parece medido.
        if any(op.get("realizado_rateado") for op in ops):
            tab_ops = html.Div([tab_ops, html.Div(
                "O tempo realizado é lançado no SAP em uma única operação e cobre a ordem inteira. "
                "Aqui ele aparece dividido entre as operações na proporção do tempo planejado de "
                "cada uma — por isso a aderência é a mesma em todas: é a da ordem.",
                className="text-muted small mt-2")])
    else:
        tab_ops = html.Div("Sem operações coletadas.", className="text-muted small")

    # atribuições
    ats = det.get("atribuicoes") or []
    if ats:
        lista_at = html.Ul([html.Li(
            f"semana {a['semana']} · {DIAS[a['dia']] if a.get('dia') is not None and 0<=a['dia']<7 else '?'} · "
            f"{a['funcionario']}" + (f" · {a['parcela_min']} min" if a.get('parcela_min') else " · ordem inteira"),
            className="small") for a in ats], className="mb-0")
    else:
        lista_at = html.Div("Não atribuída em nenhuma semana.", className="text-muted small")

    # replanejamentos
    reps = det.get("replanejamentos") or []
    if reps:
        lista_rep = html.Ul([html.Li([
            html.Span(f"{r['tipo']}", className="fw-semibold"),
            html.Span(f" · {r.get('categoria') or ''}", className="text-muted"),
            html.Span(f" — {r['texto']}" if r.get("texto") else ""),
            html.Span(f" ({r.get('por')}"
                      + (f", {r['em'].strftime('%d/%m %H:%M')}" if r.get("em") else "") + ")",
                      className="text-muted small"),
        ], className="small") for r in reps], className="mb-0")
    else:
        lista_rep = html.Div("Sem replanejamentos registrados.", className="text-muted small")

    def _sec(titulo, corpo):
        return html.Div([html.H6(titulo, className="fw-semibold mt-3 mb-2"), corpo])

    # B42: cabeçalho + KPIs em largura cheia; abaixo 2 colunas — operações (larga) × metadados
    return html.Div([
        cab, kpis,
        dbc.Row([
            dbc.Col(_sec("Operações (planejado × realizado)", tab_ops), lg=8, md=12),
            dbc.Col([
                _sec("Ficha técnica", ficha),
                _sec("Atribuições (planejamento local)", lista_at),
                _sec("Histórico de replanejamento", lista_rep),
            ], lg=4, md=12),
        ], className="g-4"),
    ])


def render_board(quadro, can_edit, collapsed=None, filtro=None, layout="planejamento"):
    """Monta o quadro completo a partir do dict de `hh_data.montar_quadro`. None → aviso."""
    if quadro is None:
        return dbc.Alert("⚠ Banco indisponível — não foi possível carregar o quadro.",
                         color="warning")
    if quadro.get("eh_futura"):
        nota = dbc.Alert("Semana futura — só o planejado aparece (sem realizado ainda).",
                         color="info", className="py-1 small")
    else:
        nota = None
    disciplinas = quadro["disciplinas"]
    collapsed = collapsed or {}
    linhas = (filtro or {}).get("linhas") or []   # B16: filtro por Linha afeta o quadro inteiro
    estados = (filtro or {}).get("estados")   # B31/B52: idem para estado; None = não filtra
    wrap_cls = "hh-board-wrap" + (" hh-mode-fila" if layout == "fila" else "")
    return html.Div([
        nota,
        dbc.Row([
            dbc.Col([
                _cabecalho_dias_fixo(quadro.get("resumo_dias"), quadro.get("meta_pct", 0.70)),
                _quadro_disciplina("Mecanica", disciplinas["Mecanica"], can_edit, collapsed.get("Mecanica"), linhas, estados,
                                   quadro.get("semana_aberta", True)),
                _quadro_disciplina("Eletrica", disciplinas["Eletrica"], can_edit, collapsed.get("Eletrica"), linhas, estados,
                                   quadro.get("semana_aberta", True)),
            ], lg=9, className="hh-col-tables"),
            dbc.Col(_coluna_a_planejar(quadro["a_planejar"], quadro["pendentes_classificacao"],
                                       can_edit, collapsed, filtro, quadro.get("terceiros")),
                    lg=3, className="hh-col-side"),
        ], className="g-3"),
    ], className=wrap_cls)
