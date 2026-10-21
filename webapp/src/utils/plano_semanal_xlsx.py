# -*- coding: utf-8 -*-
"""Planilha do Planejamento Semanal (hh-management B55) — análise gerencial e auditoria.

Irmã do `plano_semanal_pdf`: o PDF serve para imprimir e entregar ao técnico; a planilha traz
**todos os dados da semana exibida** para análise. Fonte única: `hh_data.montar_quadro(semana)`
(o mesmo que desenha a tela — overlay B45, planejado recomposto B54, cards congelados de ordens
já fechadas), então a planilha bate com o quadro por construção. READ-ONLY.

Abas:
- **Atribuições** — 1 linha por card do quadro (técnico × dia × ordem). Realizado **rateado** pela
  fração planejada da parcela (mesmo critério do rodapé e do PDF), então a coluna é somável.
- **Ordens** — 1 linha por ordem atribuída na semana; realizado/aderência no nível da ordem.
- **A planejar** — fila não atribuída (Mec/Elé/Terceiros) + pendentes de classificação.
- **Resumo por dia** — o cabeçalho-indicador da tela (planejado × disponível, ocupação, Δ%).
- **Capacidade por turno** — o rodapé da tela (disciplina × turno × dia).
- **Replanejamentos** — trilha de auditoria registrada na semana (`hh_replanejamentos`).
- **Sobre** — semana, quem/quando exportou, frescor da coleta e notas de leitura.

Duas camadas, como o PDF: `montar_planilha(...)` é PURA (testável sem Mongo);
`montar_planilha_da_semana(...)` carrega de `hh_data`; `gerar_xlsx(...)` devolve bytes.
Horas sempre em **horas decimais** (número somável), percentuais como fração com formato %.
"""
from __future__ import annotations

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

try:
    from src.utils import hh_data
    from src.utils import hh_executores
    from src.database.connection import get_mongo_connection
except ImportError:  # execução fora do pacote src (testes)
    from utils import hh_data
    from utils import hh_executores
    from database.connection import get_mongo_connection

LABEL_DISC = {"Mecanica": "Mecânica", "Eletrica": "Elétrica", "Terceiros": "Terceiros",
              "Gestao": "Gestão", "Ferramentaria": "Ferramentaria"}
LABEL_TIPO_REPLAN = {"remover": "Remoção do plano", "mover_semana": "Movida de semana",
                     "trocar_tecnico": "Troca de técnico", "remontar_divisao": "Divisão refeita"}
_NAVY = "08137C"

# formatos de coluna (openpyxl number_format)
_F_H = "0.00"          # horas decimais
_F_PCT = "0%"
_F_DATA = "dd/mm/yyyy"
_F_DATAHORA = "dd/mm/yyyy hh:mm"


# ---- helpers puros --------------------------------------------------------------------

def _h(minutos) -> float | None:
    """Minutos → horas decimais (2 casas). None se não houver valor."""
    if minutos is None:
        return None
    return round(float(minutos) / 60.0, 2)


def _plan_parcela(o: dict) -> int:
    """Planejado do card: a parcela; se a parcela é a ordem inteira (None), o planejado da ordem."""
    p = o.get("parcela_min")
    return int(p) if p is not None else int(o.get("planejado_min") or 0)


def _real_rateado(o: dict) -> float:
    """Realizado da ordem rateado pela fração planejada da parcela (critério do rodapé/PDF).

    O SAP dá o realizado por ORDEM; repetir o realizado cheio em cada card faria a soma da coluna
    contar a mesma hora várias vezes quando a ordem é dividida entre técnicos/dias."""
    plan = int(o.get("planejado_min") or 0)
    if plan <= 0:
        return 0.0
    return (o.get("realizado_min") or 0) * (_plan_parcela(o) / plan)


def _situacao(o: dict) -> str:
    """Situação da ordem no SAP do ponto de vista do quadro."""
    if o.get("_aguardando_fechamento"):
        return "Saiu do backlog (aguardando fechamento)"
    if "_entregue" in o:                      # card montado do snapshot de entrega
        return "Fechada no SAP"
    return "Aberta"


def _status(o: dict) -> str:
    return (o.get("_status_usuario_label") or o.get("status_usuario") or "").strip()


def _naive(dt):
    """openpyxl não aceita datetime com fuso — remove o tzinfo (horário de Brasília já aplicado)."""
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _txt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        return "; ".join(f"{k}: {x}" for k, x in v.items())
    if isinstance(v, (list, tuple, set)):
        return "; ".join(str(x) for x in v)
    return str(v)


# ---- camada de modelo (pura) ----------------------------------------------------------

def montar_planilha(quadro: dict, atrib_por_id: dict, replanejamentos: list[dict],
                    carry_map: dict, exportado_por: str, exportado_em: datetime,
                    nomes_executores: dict | None = None) -> dict:
    """Monta as abas (lista de colunas + linhas) a partir do quadro já carregado. Pura.

    `atrib_por_id`: {str(_id): doc de hh_planejamento} — dá quem/quando atribuiu.
    `nomes_executores`: {código SAP: nome} (`hh_executores`); código sem nome sai como código.
    Retorna {"nome_arquivo", "abas": [{"titulo", "colunas": [(nome, formato, largura)], "linhas"}]}.
    """
    semana = quadro["semana"]
    nomes_executores = nomes_executores or {}
    datas = hh_data.datas_da_semana(semana)

    # ---- Atribuições + agregação por ordem
    col_atrib = [("Semana", None, 10), ("Data", _F_DATA, 11), ("Dia", None, 9),
                 ("Quadro", None, 10), ("Técnico", None, 26), ("Turno", None, 7),
                 ("Ordem", None, 11), ("Descrição", None, 40), ("Linha", None, 22),
                 ("Local de instalação", None, 24), ("Categoria", None, 18),
                 ("Status", None, 16), ("Situação no SAP", None, 18),
                 ("Ordem inteira?", None, 9), ("Planejado na parcela (h)", _F_H, 12),
                 ("Planejado da ordem (h)", _F_H, 12), ("Realizado rateado (h)", _F_H, 12),
                 ("Atribuído por", None, 16), ("Atribuído em", _F_DATAHORA, 16),
                 ("Última alteração", _F_DATAHORA, 16)]
    linhas_atrib = []
    por_ordem: dict[str, dict] = {}
    for disc, dd in (quadro.get("disciplinas") or {}).items():
        for tec in dd.get("tecnicos") or []:
            for dia in range(7):
                for o in (tec.get("dias") or {}).get(dia, []):
                    a = atrib_por_id.get(str(o.get("_atrib_id")), {})
                    plan_p = _plan_parcela(o)
                    linhas_atrib.append([
                        semana, datas[dia].date(), hh_data.DIAS_SEMANA[dia],
                        LABEL_DISC.get(disc, disc), tec.get("nome"), tec.get("turno") or "",
                        str(o.get("ordem")), (o.get("descricao") or "").strip(),
                        o.get("linha_nome") or "", o.get("local_instalacao") or "",
                        o.get("categoria") or "", _status(o), _situacao(o),
                        "Sim" if o.get("parcela_min") is None else "Não",
                        _h(plan_p), _h(o.get("planejado_min") or 0), _h(_real_rateado(o)),
                        a.get("por") or "", _naive(a.get("criado_em")),
                        _naive(a.get("atualizado_em")),
                    ])
                    agg = por_ordem.setdefault(str(o.get("ordem")), {
                        "o": o, "parcelas": 0, "tecnicos": [], "quadros": [], "dias": []})
                    agg["parcelas"] += plan_p
                    for chave, valor in (("tecnicos", tec.get("nome")),
                                         ("quadros", LABEL_DISC.get(disc, disc)),
                                         ("dias", hh_data.DIAS_SEMANA[dia])):
                        if valor and valor not in agg[chave]:
                            agg[chave].append(valor)
    linhas_atrib.sort(key=lambda r: (r[1], r[3], r[4], r[6]))

    # ---- Ordens
    col_ordens = [("Ordem", None, 11), ("Descrição", None, 40), ("Disciplina", None, 11),
                  ("Quadro(s)", None, 14), ("Categoria", None, 18), ("Linha", None, 22),
                  ("Local de instalação", None, 24), ("Status", None, 16),
                  ("Status do sistema SAP", None, 22), ("Situação no SAP", None, 18),
                  ("Planejado da ordem (h)", _F_H, 12), ("Planejado na semana (h)", _F_H, 12),
                  ("Realizado total da ordem (h)", _F_H, 12), ("Aderência", _F_PCT, 10),
                  ("Técnicos", None, 30), ("Dias", None, 22), ("Executores no SAP", None, 24),
                  ("Nº de operações", None, 9), ("Semanas anteriores planejada", None, 11)]
    linhas_ordens = []
    for aufnr, agg in sorted(por_ordem.items()):
        o = agg["o"]
        linhas_ordens.append([
            aufnr, (o.get("descricao") or "").strip(),
            LABEL_DISC.get(o.get("disciplina"), o.get("disciplina") or ""),
            ", ".join(agg["quadros"]), o.get("categoria") or "", o.get("linha_nome") or "",
            o.get("local_instalacao") or "", _status(o), o.get("status_sap") or "", _situacao(o),
            _h(o.get("planejado_min") or 0), _h(agg["parcelas"]), _h(o.get("realizado_min") or 0),
            o.get("aderencia"), ", ".join(agg["tecnicos"]), ", ".join(agg["dias"]),
            ", ".join(dict.fromkeys(str(nomes_executores.get(str(c), c))
                                    for c in (o.get("executores") or []))),
            o.get("operacoes"), carry_map.get(aufnr, 0),
        ])

    # ---- A planejar
    col_fila = [("Fila", None, 22), ("Ordem", None, 11), ("Descrição", None, 40),
                ("Categoria", None, 18), ("Linha", None, 22), ("Local de instalação", None, 24),
                ("Status", None, 16), ("Planejado da ordem (h)", _F_H, 12),
                ("Falta planejar (h)", _F_H, 12), ("Realizado total da ordem (h)", _F_H, 12),
                ("Idade (dias)", None, 9), ("Semanas anteriores planejada", None, 11),
                ("Criada em", _F_DATA, 11)]
    linhas_fila = []
    filas = [("Mecânica", (quadro.get("a_planejar") or {}).get("Mecanica") or []),
             ("Elétrica", (quadro.get("a_planejar") or {}).get("Eletrica") or []),
             ("Terceiros", quadro.get("terceiros") or []),
             ("Pendente de classificação", quadro.get("pendentes_classificacao") or [])]
    for nome_fila, lst in filas:
        for o in lst:
            restante = o.get("_restante_min")
            if restante is None:
                restante = o.get("planejado_min") or 0
            linhas_fila.append([
                nome_fila, str(o.get("ordem")), (o.get("descricao") or "").strip(),
                o.get("categoria") or "", o.get("linha_nome") or "",
                o.get("local_instalacao") or "", _status(o), _h(o.get("planejado_min") or 0),
                _h(max(int(restante), 0)), _h(o.get("realizado_min") or 0),
                o.get("_idade_dias"), carry_map.get(str(o.get("ordem")), 0),
                _naive(o.get("data_criacao")),
            ])

    # ---- Resumo por dia (cabeçalho-indicador)
    col_dia = [("Data", _F_DATA, 11), ("Dia", None, 9), ("Planejado (h)", _F_H, 11),
               ("Disponível (h)", _F_H, 11), ("Ocupação", _F_PCT, 10),
               ("Planejado semana anterior (h)", _F_H, 13), ("Variação vs semana anterior", _F_PCT, 13)]
    linhas_dia = []
    for dia in range(7):
        r = (quadro.get("resumo_dias") or {}).get(dia) or {}
        linhas_dia.append([datas[dia].date(), hh_data.DIAS_SEMANA[dia], _h(r.get("programado") or 0),
                           _h(r.get("disponivel")), r.get("pct_programado"),
                           _h(r.get("programado_ant") or 0), r.get("delta_pct")])

    # ---- Capacidade por turno (rodapé)
    col_cap = [("Quadro", None, 10), ("Turno", None, 7), ("Data", _F_DATA, 11), ("Dia", None, 9),
               ("Disponível (h)", _F_H, 11), ("Planejado (h)", _F_H, 11),
               ("Realizado rateado (h)", _F_H, 12), ("Ocupação", _F_PCT, 10),
               ("Aderência", _F_PCT, 10), ("Nº de ordens", None, 9)]
    linhas_cap = []
    for disc, dd in (quadro.get("disciplinas") or {}).items():
        for turno, por_dia in sorted((dd.get("capacidade") or {}).items()):
            for dia in range(7):
                c = por_dia.get(dia) or {}
                linhas_cap.append([LABEL_DISC.get(disc, disc), turno, datas[dia].date(),
                                   hh_data.DIAS_SEMANA[dia], _h(c.get("disponivel")),
                                   _h(c.get("programado") or 0), _h(c.get("executado") or 0),
                                   c.get("pct_programado"), c.get("aderencia"),
                                   c.get("n_ordens") or 0])

    # ---- Replanejamentos
    col_rep = [("Quando", _F_DATAHORA, 16), ("Por", None, 16), ("Ordem", None, 11),
               ("Tipo", None, 18), ("Motivo", None, 24), ("Detalhe do motivo", None, 40)]
    linhas_rep = []
    for r in sorted(replanejamentos, key=lambda x: _naive(x.get("em")) or datetime.min):
        linhas_rep.append([_naive(r.get("em")), r.get("por") or "", str(r.get("ordem") or ""),
                           LABEL_TIPO_REPLAN.get(r.get("tipo"), r.get("tipo") or ""),
                           r.get("categoria") or "", (r.get("texto") or "").strip()])

    # ---- Sobre
    meta = quadro.get("meta_pct")
    linhas_sobre = [
        ["Semana", semana],
        ["Período", f"{datas[0]:%d/%m/%Y} a {datas[6]:%d/%m/%Y}"],
        ["Exportado por", exportado_por or ""],
        ["Exportado em", _naive(exportado_em)],
        ["Última coleta do SAP", _naive(quadro.get("coletado_em"))
         if isinstance(quadro.get("coletado_em"), datetime) else _txt(quadro.get("coletado_em"))],
        ["Meta de planejamento", meta],
        ["", ""],
        ["Como ler", ""],
        ["Horas", "Todas as horas estão em horas decimais (1,50 = 1h30)."],
        ["Realizado", "O SAP informa o realizado por ORDEM, acumulado desde a abertura (não só "
                      "desta semana) — o mesmo número da tela. Na aba Atribuições ele aparece "
                      "rateado pela parcela planejada de cada card, para a coluna poder ser "
                      "somada sem contar a mesma hora duas vezes; ordem sem tempo planejado não "
                      "tem como ratear e fica com 0 ali. O realizado total e a aderência estão "
                      "na aba Ordens."],
        ["Ordem inteira", "\"Ordem inteira? = Sim\" significa que o card não tem parcela própria: "
                          "vale o planejado total da ordem."],
        ["Fidelidade", "A planilha é montada pela mesma rotina que desenha o quadro: os números "
                       "batem com a tela no momento da exportação."],
        ["Replanejamentos", "Traz o que o sistema registra hoje: remoções do plano com motivo. "
                            "Trocas de dia ou de técnico dentro da semana não são registradas."],
    ]

    return {
        "nome_arquivo": f"plano-semanal_{semana}.xlsx",
        "abas": [
            {"titulo": "Atribuições", "colunas": col_atrib, "linhas": linhas_atrib},
            {"titulo": "Ordens", "colunas": col_ordens, "linhas": linhas_ordens},
            {"titulo": "A planejar", "colunas": col_fila, "linhas": linhas_fila},
            {"titulo": "Resumo por dia", "colunas": col_dia, "linhas": linhas_dia},
            {"titulo": "Capacidade por turno", "colunas": col_cap, "linhas": linhas_cap},
            {"titulo": "Replanejamentos", "colunas": col_rep, "linhas": linhas_rep},
            {"titulo": "Sobre", "colunas": [("Item", None, 24), ("Valor", None, 100)],
             "linhas": linhas_sobre, "_sobre": True},
        ],
    }


def montar_planilha_da_semana(semana: str, exportado_por: str = "",
                              silent: bool = True) -> dict | None:
    """Carrega o quadro + atribuições + replanejamentos da semana e monta a planilha.
    None se o banco estiver indisponível."""
    quadro = hh_data.montar_quadro(semana, silent=silent)
    if quadro is None:
        return None
    atrib_por_id = {str(a.get("_id")): a for a in hh_data.listar_atribuicoes(semana, silent)}
    replan = []
    c = get_mongo_connection(hh_data.COLL_REPLAN, silent=silent)
    if c is not None:
        replan = list(c.find({"semana": semana}, {"_id": 0}))
    return montar_planilha(quadro, atrib_por_id, replan, hh_data.carry_over_map(semana, silent),
                           exportado_por, hh_data._agora_brt(),
                           hh_executores.mapa_executores(silent))


# ---- render -----------------------------------------------------------------------------

def gerar_xlsx(modelo: dict) -> bytes:
    """Renderiza o modelo em .xlsx: cabeçalho em negrito, congelado, com autofiltro."""
    wb = Workbook()
    wb.remove(wb.active)
    cab_font = Font(bold=True, color="FFFFFF")
    cab_fill = PatternFill("solid", fgColor=_NAVY)
    for aba in modelo["abas"]:
        ws = wb.create_sheet(aba["titulo"][:31])
        colunas = aba["colunas"]
        if aba.get("_sobre"):
            for r in aba["linhas"]:
                ws.append(r)
            for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
                row[0].font = Font(bold=True)
                row[1].alignment = Alignment(wrap_text=True, vertical="top")
                if isinstance(row[1].value, datetime):
                    row[1].number_format = _F_DATAHORA
                elif isinstance(row[1].value, float):
                    row[1].number_format = _F_PCT
        else:
            ws.append([c[0] for c in colunas])
            for cel in ws[1]:
                cel.font = cab_font
                cel.fill = cab_fill
                cel.alignment = Alignment(wrap_text=True, vertical="center")
            for r in aba["linhas"]:
                ws.append(r)
            for j, (_, fmt, _larg) in enumerate(colunas, start=1):
                if fmt:
                    for (cel,) in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=j, max_col=j):
                        cel.number_format = fmt
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = f"A1:{get_column_letter(len(colunas))}{max(ws.max_row, 1)}"
            ws.row_dimensions[1].height = 32
        for j, (_, _fmt, larg) in enumerate(colunas, start=1):
            ws.column_dimensions[get_column_letter(j)].width = larg
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
