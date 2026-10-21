# -*- coding: utf-8 -*-
"""Figura e formatação do bloco "Mão de obra da semana" (KPIReport-v2 BR-11/12, DS-15).

Compartilhado entre a tela (aba Relatório) e os exportáveis (DOCX/PDF) para o gráfico ser
idêntico nos três. Só apresentação — os dados vêm de `hh_data.semana_mao_de_obra`.
"""
from __future__ import annotations

DOW_PT = ("Seg", "Ter", "Qua", "Qui", "Sex")

# paleta NEUTRA (não semântica) — evita verde/vermelho de julgamento (premissa nº neutro, BR-11/12)
COR_DISP = "#9aa5b1"   # cinza — disponível
COR_PLAN = "#6c8ebf"   # azul médio — planejado
COR_EXEC = "#38517a"   # azul escuro — executado


def fmt_h(v) -> str:
    """Horas para exibição: '—' quando None (nunca 0 — SP-22); inteiro caso contrário."""
    return "—" if v is None else f"{v:.0f}"


def fmt_pct(v) -> str:
    """Percentual para exibição: '—' quando None; inteiro com % caso contrário."""
    return "—" if v is None else f"{v * 100:.0f}%"


def _dm(iso: str) -> str:
    """Data ISO 'AAAA-MM-DD' → 'DD/MM'. Devolve o próprio valor se não parsear."""
    p = (iso or "").split("-")
    return f"{p[2]}/{p[1]}" if len(p) == 3 else iso


def fig_mao_de_obra(dias: list):
    """Barras agrupadas por dia útil (Disponível/Planejado/Executado). Executado None → sem
    barra (gap), nunca barra zero (SP-22/BR-12). Paleta neutra. Retorna `plotly.go.Figure`."""
    import plotly.graph_objects as go
    # eixo X: dia da semana + data (ex: "Seg<br>27/07") — o gestor confere QUAL dia é cada barra
    labels = [f"{DOW_PT[d['dow']]}<br>{_dm(d['data'])}" for d in dias]
    # rótulo de dados em cima de cada barra (horas inteiras) — comparação direta sem a tabela.
    # None (executado sem apontamento) → sem barra e sem rótulo.
    lbl = {"texttemplate": "%{y:.0f}", "textposition": "outside",
           "textfont": {"size": 10}, "cliponaxis": False}
    fig = go.Figure()
    fig.add_bar(name="Disponível", x=labels, y=[d["disponivel_h"] for d in dias],
                marker_color=COR_DISP, **lbl)
    fig.add_bar(name="Planejado", x=labels, y=[d["planejado_h"] for d in dias],
                marker_color=COR_PLAN, **lbl)
    fig.add_bar(name="Executado", x=labels, y=[d["executado_h"] for d in dias],
                marker_color=COR_EXEC, **lbl)  # None vira gap — sem barra
    fig.update_layout(
        barmode="group", height=320,
        margin={"l": 40, "r": 10, "t": 28, "b": 30},
        yaxis_title="horas",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        uniformtext={"minsize": 8, "mode": "hide"},
    )
    return fig


def dia_label(d: dict) -> str:
    """Rótulo do dia com a data: 'Seg 27/07' — usado na coluna Dia da tabela (tela/DOCX/PDF)."""
    return f"{DOW_PT[d['dow']]} {_dm(d['data'])}"


def linhas_tabela(dias: list) -> list[dict]:
    """Linhas formatadas (strings prontas) da tabela de mão de obra para DOCX/PDF.

    Colunas: dia · disponivel · planejado · pct · executado · aderencia. '—' nos vazios."""
    return [{
        "dia": dia_label(d),
        "disponivel": fmt_h(d["disponivel_h"]),
        "planejado": fmt_h(d["planejado_h"]),
        "pct": fmt_pct(d["pct_plan"]),
        "executado": fmt_h(d["executado_h"]),
        "aderencia": fmt_pct(d["aderencia"]),
    } for d in dias]


# cabeçalhos da tabela (PT — SP-23 revisado; i18n do relatório é follow-up)
CABECALHOS = ("Dia", "Disponível (h)", "Planejado (h)", "% plan.", "Executado (h)", "Aderência")


def rotulo_semana(sem: dict) -> str:
    """Subtítulo do bloco: intervalo seg–sex da semana de referência, p/ deixar claro QUAL semana
    está sendo mostrada (a que contém o dia avaliado do relatório). Ex: 'Semana de 27/07 a 31/07'."""
    dias = (sem or {}).get("dias") or []
    if not dias:
        return ""
    return f"Semana de {_dm(dias[0]['data'])} a {_dm(dias[-1]['data'])}"
