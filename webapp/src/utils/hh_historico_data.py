# -*- coding: utf-8 -*-
"""Camada de dados do HISTÓRICO SEMANAL (SDD hh-historico, fase 06 — Bloco A).

Agregações **retroativas** sobre as collections que já persistem por semana, para a aba
"Histórico Semanal" do quadro:

- `hh_planejamento` — atribuições + o snapshot `entrega` congelado no fecho da ordem (BR-20 do
  hh-management: `planejado_min`/`realizado_min`/`aderencia`/`status_saida`/`data_conclusao`).
- `hh_replanejamentos` — auditoria append-only (empurrar/cancelar/trocar/remontar), com `categoria`
  (motivo), `tipo` e `semana`.

Regras implementadas (fase 02 do SDD):
- Semana = ISO `YYYY-Www`, segunda→domingo (BR-03); mês por maioria dos dias (BR-07).
- Carry-over de W = ordem atribuída em semana < W **e** não encerrada/cancelada até o fim de W (BR-01).
- Carry-over crônico = maior sequência **consecutiva** de semanas atribuída, só ordens abertas; pulo
  zera (BR-02).
- Entregue de W = ordem encerrada dentro de W; aderência/HH ponderados por horas, só entregues
  (BR-06/BR-07/BR-08).
- Replanejamento contável = `mover_semana` (empurrar) + `remover` (cancelar); ajuste interno fora (BR-09).

**Não altera** `hh_data.py` (retrocompat). Só leitura; degradação graciosa (Mongo down → vazio). Os
núcleos `_compute_*` são funções puras (testáveis sem Mongo); as `serie_*`/`insight_*` carregam os docs
e delegam.
"""
from __future__ import annotations

try:
    from src.database.connection import get_mongo_connection
    from src.utils import hh_data as hd
except ImportError:  # execução fora do pacote src
    from database.connection import get_mongo_connection
    from utils import hh_data as hd

# status do snapshot `entrega`
ENTREGUE_STATUS = ("encerrada", "concluida")          # concluida = legado (BR-08: só entregues)
TERMINAL_STATUS = ("encerrada", "concluida", "cancelada")  # saíram do plano (param carry-over — BR-01)
# tipos de replanejamento que contam como "plano falhou" (BR-09: empurrar + cancelar)
REPLAN_CONTA_TIPOS = ("mover_semana", "remover")
CRONICO_MIN = 3        # BR-02: 3+ semanas consecutivas = crônico
ETERNAS_TOP = 5        # BR-13: top 5

# quebra por disciplina (BR-16): 3 séries reais + "Outras" (dobra o resto pra fechar com o total)
DISC_BUCKETS = ["Eletrica", "Mecanica", "Terceiros", "Outras"]
_DISC_REAIS = {"Eletrica", "Mecanica", "Terceiros"}


def _disc_bucket(disc: str | None) -> str:
    """Disciplina da ordem → uma das 4 séries (BR-16). Elé/Mec/Ter reais; Gestão, Ferramentaria,
    Não classificado e ausente (`None`) caem em 'Outras' — a soma das 4 fecha com o total da planta."""
    return disc if disc in _DISC_REAIS else "Outras"


# ---- helpers de semana ----------------------------------------------------------------

def semana_para_mes(semana: str) -> str:
    """Mês (YYYY-MM) ao qual a semana ISO pertence = onde cai a **maioria dos 7 dias** (BR-07).

    Ex.: a semana 2026-W27 (29/jun a 5/jul) tem 2 dias em junho e 5 em julho → '2026-07'.
    """
    contagem: dict[str, int] = {}
    for d in hd.datas_da_semana(semana):
        chave = f"{d.year}-{d.month:02d}"
        contagem[chave] = contagem.get(chave, 0) + 1
    return max(contagem, key=contagem.get)


def _semanas_entre(sem_ini: str, sem_fim: str) -> list[str]:
    """Lista de semanas ISO de `sem_ini` a `sem_fim` inclusive (ordem crescente). Vazio se invertido."""
    if hd.inicio_da_semana(sem_ini) > hd.inicio_da_semana(sem_fim):
        return []
    out, w = [], sem_ini
    # limite de segurança: 520 semanas (~10 anos) para nunca laçar infinito por dado corrompido
    for _ in range(520):
        out.append(w)
        if w == sem_fim:
            break
        w = hd.semana_shift(w, 1)
    return out


def _week_lt(a: str, b: str) -> bool:
    """True se a semana `a` começa antes de `b`."""
    return hd.periodos_quadro.semana_cmp(a, b) < 0


def _week_gt(a: str, b: str) -> bool:
    """True se a semana `a` começa depois de `b`."""
    return hd.periodos_quadro.semana_cmp(a, b) > 0


# ---- leitura do snapshot `entrega` ----------------------------------------------------

def _close_week(ent: dict) -> str | None:
    """Semana ISO em que a ordem saiu do backlog (data de conclusão; fallback = congelado_em). None
    se não houver data."""
    dt = ent.get("data_conclusao") or ent.get("congelado_em")
    return hd.iso_semana(dt) if dt else None


def _is_entregue(ent: dict | None) -> bool:
    """Snapshot marca a ordem como ENTREGUE (encerrada/concluída — BR-08). Cancelada NÃO é entregue."""
    return bool(ent) and ent.get("status_saida") in ENTREGUE_STATUS


def _is_terminal(ent: dict | None) -> bool:
    """Snapshot marca a ordem como terminal (saiu do plano: encerrada/concluída/cancelada — BR-01)."""
    return bool(ent) and ent.get("status_saida") in TERMINAL_STATUS


def _index_orders(docs: list[dict]) -> dict:
    """Indexa os docs de `hh_planejamento` por ordem: {ordem: {weeks:set, entrega, disciplina}}.

    `weeks` = semanas em que a ordem foi atribuída. `entrega` = o snapshot congelado (prioriza o
    terminal, se houver). `disciplina` = a última disciplina vista (quadro/ordem).
    """
    orders: dict[str, dict] = {}
    for d in docs:
        o = str(d.get("ordem"))
        rec = orders.setdefault(o, {"weeks": set(), "entrega": None, "disciplina": None})
        sem = d.get("semana")
        if sem:
            rec["weeks"].add(sem)
        ent = d.get("entrega")
        if ent and (rec["entrega"] is None or _is_terminal(ent)):
            rec["entrega"] = ent
        disc = d.get("disciplina_quadro") or d.get("disciplina")
        if disc:
            rec["disciplina"] = disc
    return orders


# ---- núcleos puros (testáveis sem Mongo) ----------------------------------------------

def _compute_fluxo(docs: list[dict], semanas: list[str]) -> list[dict]:
    """Fluxo do plano por semana: atribuídas, entregues, carry-over (contagem de ordens distintas).

    - atribuídas(W): ordens com atribuição na própria W (BR-07).
    - entregues(W): ordens encerradas dentro de W (BR-07; fronteira = fim da semana, BR-01).
    - carry-over(W): ordens atribuídas em semana < W e **não** terminais até o fim de W (BR-01).
    """
    orders = _index_orders(docs)
    out = []
    for W in semanas:
        atrib = entreg = carry = 0
        for rec in orders.values():
            ent = rec["entrega"]
            cw = _close_week(ent) if ent else None
            if W in rec["weeks"]:
                atrib += 1
            if _is_entregue(ent) and cw == W:
                entreg += 1
            if any(_week_lt(w, W) for w in rec["weeks"]):
                terminou_ate_W = _is_terminal(ent) and cw is not None and not _week_gt(cw, W)
                if not terminou_ate_W:
                    carry += 1
        out.append({"semana": W, "atribuidas": atrib, "entregues": entreg, "carry_over": carry})
    return out


def _somas_entregues_semana(orders: dict, W: str) -> tuple[int, int]:
    """(Σ planejado_min, Σ realizado_min) das ordens ENTREGUES em W, por ordem distinta (BR-08)."""
    plan = real = 0
    for rec in orders.values():
        ent = rec["entrega"]
        if _is_entregue(ent) and _close_week(ent) == W:
            plan += int(ent.get("planejado_min") or 0)
            real += int(ent.get("realizado_min") or 0)
    return plan, real


def _compute_hh(docs: list[dict], semanas: list[str]) -> list[dict]:
    """Hora-Homem planejado × realizado por semana (horas), das ordens entregues em W (BR-08)."""
    orders = _index_orders(docs)
    out = []
    for W in semanas:
        plan, real = _somas_entregues_semana(orders, W)
        out.append({"semana": W, "planejado_h": round(plan / 60, 1), "realizado_h": round(real / 60, 1)})
    return out


def _compute_aderencia(docs: list[dict], semanas: list[str]) -> list[dict]:
    """Aderência por semana = (Σ realizado ÷ Σ planejado) × 100, ponderada por horas (BR-06).

    Só ordens entregues em W. `>100%` retornado real. Sem planejado → None.
    """
    orders = _index_orders(docs)
    out = []
    for W in semanas:
        plan, real = _somas_entregues_semana(orders, W)
        pct = round(real / plan * 100, 1) if plan > 0 else None
        out.append({"semana": W, "aderencia_pct": pct})
    return out


def _compute_por_disc(docs: list[dict], semanas: list[str]) -> dict:
    """Métricas por semana **e por disciplina** (BR-16/17/18), numa passada. Base dos 4 gráficos novos.

    Retorna `{semana: {bucket: {atribuidas, entregues, planejado_min, realizado_min, aderencia_pct}}}`
    com `bucket` ∈ DISC_BUCKETS (Elétrica/Mecânica/Terceiros/Outras).

    - `atribuidas`: ordens distintas atribuídas na W, pela disciplina da ordem (BR-16 sobre BR-07).
    - `entregues`: ordens encerradas em W, pela disciplina (BR-16 sobre BR-07).
    - `planejado_min`/`realizado_min`: soma das entregues em W, por disciplina (BR-17; horas = ÷60 na UI).
    - `aderencia_pct`: (Σ realizado ÷ Σ planejado)×100 por disciplina, ponderado por horas (BR-18);
      `None` quando planejado=0 (disciplina sem entrega na semana = buraco, não zero — BR-18).

    A disciplina por ordem é a do índice (`disciplina_quadro or disciplina`, `_index_orders`) — última
    vista; ordem raramente troca de disciplina. Retroativo, sem coleta nova.
    """
    orders = _index_orders(docs)
    base = {W: {b: {"atribuidas": 0, "entregues": 0, "carry_over": 0,
                    "entregues_plano": 0, "entregues_carry": 0, "entregues_fora": 0,
                    "planejado_min": 0, "realizado_min": 0}
                for b in DISC_BUCKETS} for W in semanas}
    alvo = set(semanas)
    for rec in orders.values():
        b = _disc_bucket(rec["disciplina"])
        ent = rec["entrega"]
        cw = _close_week(ent) if ent else None
        for w in rec["weeks"]:
            if w in alvo:
                base[w][b]["atribuidas"] += 1
        if _is_entregue(ent) and cw in alvo:
            cell = base[cw][b]
            cell["entregues"] += 1
            cell["planejado_min"] += int(ent.get("planejado_min") or 0)
            cell["realizado_min"] += int(ent.get("realizado_min") or 0)
            # origem da entrega (BR-07/BR-22): planejada na própria semana × arrasto × nunca planejada
            if cw in rec["weeks"]:
                cell["entregues_plano"] += 1
            elif rec["weeks"]:
                cell["entregues_carry"] += 1
            else:
                cell["entregues_fora"] += 1
        # carry-over por disciplina, por semana (mesma regra da BR-01, recortada por disciplina)
        if any(_week_lt(w0, semanas[-1]) for w0 in rec["weeks"]):
            for W in semanas:
                if any(_week_lt(w0, W) for w0 in rec["weeks"]):
                    terminou_ate_W = _is_terminal(ent) and cw is not None and not _week_gt(cw, W)
                    if not terminou_ate_W:
                        base[W][b]["carry_over"] += 1
    for W in semanas:
        for b in DISC_BUCKETS:
            cell = base[W][b]
            p = cell["planejado_min"]
            cell["aderencia_pct"] = round(cell["realizado_min"] / p * 100, 1) if p > 0 else None
    return base


def _compute_replanejamentos(replan_docs: list[dict], semanas: list[str]) -> list[dict]:
    """Replanejamentos por semana e por motivo (empurrar + cancelar — BR-09)."""
    por_semana: dict[str, dict] = {W: {} for W in semanas}
    alvo = set(semanas)
    for r in replan_docs:
        if r.get("tipo") not in REPLAN_CONTA_TIPOS:
            continue
        sem = r.get("semana")
        if sem not in alvo:
            continue
        cat = r.get("categoria") or "Sem motivo"
        por_semana[sem][cat] = por_semana[sem].get(cat, 0) + 1
    return [{"semana": W, "motivos": por_semana[W]} for W in semanas]


def _janela_semanas(ref_week: str, janela: int) -> list[str]:
    """As `janela` semanas terminando em `ref_week` (inclusive), da mais recente à mais antiga."""
    out, w = [], ref_week
    for _ in range(max(1, int(janela))):
        out.append(w)
        w = hd.semana_shift(w, -1)
    return out


def _compute_eternas(docs: list[dict], ref_week: str, janela: int, top: int = ETERNAS_TOP,
                     info_map: dict | None = None) -> list[dict]:
    """Carry-over crônico (BR-02): ordens ABERTAS com maior sequência CONSECUTIVA de semanas
    atribuídas terminando em `ref_week`; pulo zera. Só streak ≥ 3; top N por streak.

    `info_map` = {ordem: {descricao, linha}} (opcional, de `montar_ordens`); quando dado, cada item
    leva `descricao` e `linha` (senão `None`). Nenhum dos dois está em `hh_planejamento` — vêm do
    backlog vivo (`linha_nome`/`descricao` da ordem)."""
    orders = _index_orders(docs)
    im = info_map or {}
    elig = []
    for o, rec in orders.items():
        if _is_terminal(rec["entrega"]):     # fechou/cancelou → não é "eterna" ativa
            continue
        streak, w = 0, ref_week
        for _ in range(max(1, int(janela))):
            if w in rec["weeks"]:
                streak += 1
                w = hd.semana_shift(w, -1)
            else:
                break
        if streak >= CRONICO_MIN:
            info = im.get(o) or {}
            elig.append({"ordem": o, "semanas_consec": streak, "disciplina": rec["disciplina"],
                         "descricao": info.get("descricao"), "linha": info.get("linha")})
    elig.sort(key=lambda x: -x["semanas_consec"])
    return elig[:top]


def _mapa_ordem_info(silent: bool = True) -> dict:
    """{ordem: {descricao, linha}} do universo de ordens abertas (`montar_ordens`, cacheado).
    Fonte de descrição + linha das 'eternas' (carry-over crônico) — nada disso vive em
    `hh_planejamento`. Campos ausentes viram '' (retrocompat)."""
    base = hd.montar_ordens(silent=silent) or {}
    return {str(k): {"descricao": (v.get("descricao") or ""), "linha": (v.get("linha_nome") or "")}
            for k, v in (base.get("ordens") or {}).items()}


def _compute_top_motivos(replan_docs: list[dict], ref_week: str, janela: int) -> list[dict]:
    """Ranking de motivos de replanejamento (empurrar + cancelar) na janela terminando em ref_week."""
    alvo = set(_janela_semanas(ref_week, janela))
    tot: dict[str, int] = {}
    for r in replan_docs:
        if r.get("tipo") not in REPLAN_CONTA_TIPOS:
            continue
        if r.get("semana") not in alvo:
            continue
        cat = r.get("categoria") or "Sem motivo"
        tot[cat] = tot.get(cat, 0) + 1
    return sorted(({"motivo": k, "total": v} for k, v in tot.items()), key=lambda x: -x["total"])


# ---- carregadores + API pública -------------------------------------------------------

_PROJ_ATRIB = {
    "ordem": 1, "semana": 1, "disciplina": 1, "disciplina_quadro": 1,
    "entrega.status_saida": 1, "entrega.planejado_min": 1, "entrega.realizado_min": 1,
    "entrega.aderencia": 1, "entrega.data_conclusao": 1, "entrega.congelado_em": 1, "_id": 0,
}
_PROJ_REPLAN = {"ordem": 1, "semana": 1, "tipo": 1, "categoria": 1, "_id": 0}
# projeção do DETALHE (modal drill-down do Top motivos, BR-13): inclui texto/por/em
_PROJ_REPLAN_DET = {"ordem": 1, "semana": 1, "tipo": 1, "categoria": 1,
                    "texto": 1, "por": 1, "em": 1, "_id": 0}


def _load_atrib_docs(silent: bool = True) -> list[dict]:
    """Todos os docs de `hh_planejamento` projetados para o histórico. 1 query. [] se Mongo down.

    B54: o `entrega.planejado_min` congelado vem do IW47, que só devolve as operações COM
    apontamento — uma ordem de 5 operações de 30 min ficava com 30. A recomposição é feita aqui,
    na porta de entrada, para que TODAS as contas do histórico (HH entregue, aderência semanal,
    aderência por disciplina) já recebam o total das operações. Corrigir só nos pontos de uso
    deixaria a próxima conta nova exposta ao mesmo furo. A aderência congelada é recalculada
    junto — senão o número exibido discordaria dos totais.
    """
    c = get_mongo_connection(hd.COLL_ATRIB, silent=silent)
    if c is None:
        return []
    docs = list(c.find({}, _PROJ_ATRIB))
    iw37 = hd.plan_iw37_por_ordem(silent)
    for d in docs:
        ent = d.get("entrega")
        if not ent or ent.get("planejado_min") is None:
            continue
        plan = hd.planejado_de_entrega(ent, str(d.get("ordem")), iw37)
        if plan != ent.get("planejado_min"):
            ent["planejado_min"] = plan
            real = int(ent.get("realizado_min") or 0)
            ent["aderencia"] = (real / plan) if plan > 0 else ent.get("aderencia")
    return docs


def _load_replan_docs(silent: bool = True) -> list[dict]:
    """Todos os docs de `hh_replanejamentos` projetados. 1 query. [] se Mongo down."""
    c = get_mongo_connection(hd.COLL_REPLAN, silent=silent)
    if c is None:
        return []
    return list(c.find({}, _PROJ_REPLAN))


def serie_fluxo(sem_ini: str, sem_fim: str, silent: bool = True) -> list[dict]:
    """Série do fluxo do plano (atribuídas/entregues/carry-over) por semana no intervalo."""
    return _compute_fluxo(_load_atrib_docs(silent), _semanas_entre(sem_ini, sem_fim))


def serie_hh(sem_ini: str, sem_fim: str, silent: bool = True) -> list[dict]:
    """Série de HH planejado × realizado (horas) por semana no intervalo."""
    return _compute_hh(_load_atrib_docs(silent), _semanas_entre(sem_ini, sem_fim))


def serie_aderencia(sem_ini: str, sem_fim: str, silent: bool = True) -> list[dict]:
    """Série de aderência (%) ponderada por horas, por semana no intervalo."""
    return _compute_aderencia(_load_atrib_docs(silent), _semanas_entre(sem_ini, sem_fim))


def serie_replanejamentos(sem_ini: str, sem_fim: str, silent: bool = True) -> list[dict]:
    """Série de replanejamentos (empurrar + cancelar) por semana e motivo no intervalo."""
    return _compute_replanejamentos(_load_replan_docs(silent), _semanas_entre(sem_ini, sem_fim))


def serie_por_disciplina(sem_ini: str, sem_fim: str, silent: bool = True) -> dict:
    """Métricas por disciplina (BR-16/17/18) por semana no intervalo: {semana:{bucket:{...}}}."""
    return _compute_por_disc(_load_atrib_docs(silent), _semanas_entre(sem_ini, sem_fim))


def detalhe_semana(semana: str, silent: bool = True) -> dict:
    """Corte transversal de UMA semana p/ o modal de detalhe (clique no Fluxo): totais da semana
    (fluxo + HH + aderência) + a quebra por disciplina. Uma passada sobre `hh_planejamento`."""
    docs = _load_atrib_docs(silent)
    fluxo = _compute_fluxo(docs, [semana])[0]
    hh_s = _compute_hh(docs, [semana])[0]
    ader = _compute_aderencia(docs, [semana])[0]["aderencia_pct"]
    por_disc = _compute_por_disc(docs, [semana])[semana]
    return {"semana": semana, "fluxo": fluxo, "hh": hh_s, "aderencia_pct": ader, "por_disc": por_disc}


CAP_TURNOS_EXCLUIR = {"ADM"}   # turnos fora da capacidade de manutenção (BR-20) — ADM não pega ordem
DIAS_UTEIS = (0, 1, 2, 3, 4)   # BR-19: disponível/planejado contam só seg–sex (dia 0..4); fds fora


def _ordens_para_capacidade(silent: bool = True) -> dict:
    """{ordem: {planejado_min, realizado_min, ...}} p/ a capacidade (BR-19). Backlog vivo (abertas)
    sobreposto pelo snapshot `entrega` das fechadas — assim ordem fechada não perde o planejado no
    histórico (o backlog vivo só tem as abertas).

    B54: delega para `hd.overlay_entrega`, em vez de repetir a regra aqui. A cópia local ficava
    fora de sincronia a cada correção do quadro (era o caso do planejado congelado do IW47, que
    trazia só as operações apontadas) — o histórico e o quadro erravam igual e por isso a
    conferência entre as duas telas não flagrava nada."""
    base = hd.montar_ordens(silent=silent) or {}
    return hd.overlay_entrega(base.get("ordens") or {}, _load_atrib_docs(silent),
                              hd.plan_iw37_por_ordem(silent))


def serie_capacidade(sem_ini: str, sem_fim: str, silent: bool = True) -> list[dict]:
    """Disponível (líquido de folga) × planejado por semana, total e por turno (BR-19/BR-20).

    Retroativo (decisão 2026-07-25): reusa `hd.calcular_capacidade` por semana com roster/config **ao
    vivo** e folgas **datadas** (`gantt_assignments`) — passado é aproximado se o roster mudou depois.
    Exceção: mão de obra temporária é filtrada pelos períodos datados de cada semana (BR-25).
    Retorna [{semana, disponivel_h, planejado_h, por_turno:{turno:{disponivel_h, planejado_h}}}].
    """
    weeks = _semanas_entre(sem_ini, sem_fim)
    if not weeks:
        return []
    funcs = hd._carregar_funcionarios(silent)
    assign = hd._assignments_por_func(funcs, silent)
    dmap = (hd.carregar_config_capacidade(silent) or {}).get("disponivel_min")
    ordens = _ordens_para_capacidade(silent)
    out = []
    for W in weeks:
        atrib = hd.listar_atribuicoes(W, silent)
        # mão de obra temporária conta só nas semanas em que estava incluída (BR-25 item 10)
        funcs_w = hd.funcionarios_da_semana(funcs, W)
        cap = hd.calcular_capacidade(W, funcs_w, atrib, ordens, assign, disc=None, disponivel_map=dmap)
        por_turno, tot_disp, tot_plan = {}, 0, 0
        for turno, dias in cap.items():
            if turno in CAP_TURNOS_EXCLUIR:   # ADM não é capacidade de manutenção (BR-20)
                continue
            # só dias úteis (seg–sex) — não conta jornada de fim de semana (BR-19)
            disp = sum((dias.get(d, {}).get("disponivel") or 0) for d in DIAS_UTEIS)
            plan = sum((dias.get(d, {}).get("programado") or 0) for d in DIAS_UTEIS)
            por_turno[turno] = {"disponivel_h": round(disp / 60, 1), "planejado_h": round(plan / 60, 1)}
            tot_disp += disp
            tot_plan += plan
        out.append({"semana": W, "disponivel_h": round(tot_disp / 60, 1),
                    "planejado_h": round(tot_plan / 60, 1), "por_turno": por_turno})
    return out


def insight_eternas(janela_sem: int, ref_week: str | None = None, top: int = ETERNAS_TOP,
                    silent: bool = True) -> list[dict]:
    """Top-N ordens em carry-over crônico (BR-02) terminando em `ref_week` (default = semana atual)."""
    ref = ref_week or hd.semana_atual()
    return _compute_eternas(_load_atrib_docs(silent), ref, janela_sem, top, _mapa_ordem_info(silent))


def insight_top_motivos(janela_sem: int, ref_week: str | None = None, silent: bool = True) -> list[dict]:
    """Ranking de motivos de replanejamento na janela terminando em `ref_week` (default = atual)."""
    ref = ref_week or hd.semana_atual()
    return _compute_top_motivos(_load_replan_docs(silent), ref, janela_sem)


def insight_replan_detalhe(janela_sem: int, ref_week: str | None = None,
                           motivo: str | None = None, silent: bool = True) -> list[dict]:
    """Registros crus de replanejamento (empurrar+cancelar) que compõem o Top motivos (BR-13), na
    janela terminando em `ref_week`. Para o modal de drill-down: cada linha é um evento com ordem,
    descrição (do backlog vivo), tipo, motivo, observação livre (`texto`), quem e quando. `motivo`
    filtra a uma categoria (None = todas). Ordenado por motivo e data (mais recente primeiro)."""
    ref = ref_week or hd.semana_atual()
    alvo = set(_janela_semanas(ref, janela_sem))
    c = get_mongo_connection(hd.COLL_REPLAN, silent=silent)
    docs = list(c.find({}, _PROJ_REPLAN_DET)) if c is not None else []
    desc = _mapa_ordem_info(silent)
    out = []
    for r in docs:
        if r.get("tipo") not in REPLAN_CONTA_TIPOS:
            continue
        if r.get("semana") not in alvo:
            continue
        cat = r.get("categoria") or "Sem motivo"
        if motivo and cat != motivo:
            continue
        o = str(r.get("ordem"))
        out.append({"semana": r.get("semana"), "ordem": o,
                    "descricao": (desc.get(o) or {}).get("descricao", ""),
                    "tipo": r.get("tipo"), "categoria": cat,
                    "texto": r.get("texto") or "", "por": r.get("por") or "", "em": r.get("em")})
    out.sort(key=lambda x: (x["categoria"], str(x["em"] or "")), reverse=False)
    return out


# ---- período disponível + persistência de config (Bloco D) ----------------------------

def primeira_semana(silent: bool = True) -> str | None:
    """Semana ISO mais antiga com atribuição em `hh_planejamento` (base do filtro de período —
    BR-11). None se não houver dado / Mongo down."""
    c = get_mongo_connection(hd.COLL_ATRIB, silent=silent)
    if c is None:
        return None
    ws = [w for w in c.distinct("semana") if w]
    return min(ws, key=hd.inicio_da_semana) if ws else None


CFG_HISTORICO_ID = "historico"        # doc de config da aba em hh_config
INSIGHTS_JANELA_DEFAULT = 12          # BR-13 (editável 1–52, salva)


def carregar_insights_janela(silent: bool = True) -> int:
    """Janela (semanas) dos insights salva em `hh_config` (BR-13). Default 12 se ausente."""
    c = get_mongo_connection(hd.COLL_CONFIG, silent=silent)
    if c is None:
        return INSIGHTS_JANELA_DEFAULT
    d = c.find_one({"_id": CFG_HISTORICO_ID}) or {}
    v = d.get("insights_janela")
    try:
        return max(1, min(52, int(v))) if v else INSIGHTS_JANELA_DEFAULT
    except (TypeError, ValueError):
        return INSIGHTS_JANELA_DEFAULT


def salvar_insights_janela(n, silent: bool = True) -> int:
    """Persiste a janela dos insights (clampada 1–52) em `hh_config`. Retorna o valor salvo."""
    n = max(1, min(52, int(n or INSIGHTS_JANELA_DEFAULT)))
    c = get_mongo_connection(hd.COLL_CONFIG, silent=silent)
    if c is not None:
        c.update_one({"_id": CFG_HISTORICO_ID}, {"$set": {"insights_janela": n}}, upsert=True)
    return n


# ======================================================================================
# CAPTURA FASE 2 (forward-only) — SDD hh-historico, Bloco E
#
# `hh_historico_semanal` (SCD2 por ordem, BR-12): estado do backlog no tempo — só existe daqui
# pra frente. `hh_historico_fora` (snapshot semanal, BR-10): trabalho fora do plano por semana.
# Rodadas pelo job semanal no webapp (apscheduler). Idempotente por semana.
# ======================================================================================

COLL_HIST = "hh_historico_semanal"     # SCD2 do estado do backlog (por ordem)
COLL_FORA = "hh_historico_fora"        # snapshot semanal de trabalho fora do plano

# situações semânticas (rótulo → cor), na ordem de exibição do gráfico empilhado (BR-12)
STATUS_ORDEM = ["Aberta", "Em Tratamento", "Em Pausa", "Aceitação de Espera", "Encerrada", "Cancelada"]


def ensure_indexes_historico(silent: bool = True) -> None:
    """Índices da captura Fase 2 (SP-06.2). Idempotente."""
    c = get_mongo_connection(COLL_HIST, silent=silent)
    if c is not None:
        c.create_index([("ordem", 1)], name="idx_ordem")
        c.create_index([("valido_ate", 1)], name="idx_vigente")
        c.create_index([("valido_de", 1), ("valido_ate", 1)], name="idx_intervalo")
    cf = get_mongo_connection(COLL_FORA, silent=silent)
    if cf is not None:
        cf.create_index([("semana", 1)], name="idx_semana", unique=True)
    cr = get_mongo_connection(hd.COLL_REPLAN, silent=silent)
    if cr is not None:
        cr.create_index([("semana", 1)], name="idx_semana")   # BR-09/SP-06.2


def _estado_atual_backlog(silent: bool = True) -> dict:
    """{ordem: {status_usuario, disciplina}} do estado atual das ordens abertas (via montar_ordens)."""
    base = hd.montar_ordens(silent=silent)
    if not base:
        return {}
    return {str(a): {"status_usuario": o.get("status_usuario"), "disciplina": o.get("disciplina")}
            for a, o in base["ordens"].items()}


# ---- núcleos puros (testáveis) --------------------------------------------------------

def _diff_backlog(atual: dict, vigentes: dict, semana: str):
    """Pure (append-on-change): dado o estado atual e os registros vigentes, decide o que gravar.

    Retorna (inserts, close_ids): `inserts` = novos episódios de status; `close_ids` = _ids de
    vigentes a encerrar (`valido_ate=semana`). Só muda o que mudou de status ou saiu do backlog.
    """
    inserts, close_ids = [], []
    for ordem, est in atual.items():
        st = est.get("status_usuario") or "ABIE"
        cur = vigentes.get(ordem)
        if cur is None:
            inserts.append({"ordem": ordem, "status_usuario": st, "disciplina": est.get("disciplina"),
                            "valido_de": semana, "valido_ate": None})
        elif (cur.get("status_usuario") or "ABIE") != st:
            close_ids.append(cur["_id"])
            inserts.append({"ordem": ordem, "status_usuario": st, "disciplina": est.get("disciplina"),
                            "valido_de": semana, "valido_ate": None})
    for ordem, cur in vigentes.items():
        if ordem not in atual:          # sumiu do backlog → encerra o vigente
            close_ids.append(cur["_id"])
    return inserts, close_ids


def _cobre(vd, va, semana: str) -> bool:
    """O intervalo [valido_de, valido_ate) cobre `semana`? (valido_de ≤ semana < valido_ate)."""
    if not vd or _week_gt(vd, semana):
        return False
    if va is not None and not _week_gt(va, semana):   # va ≤ semana → não cobre
        return False
    return True


def _contar_status(docs: list[dict], semana: str, label_fn=None) -> dict:
    """{rótulo_status: nº ordens} a partir dos registros SCD2 cujo intervalo cobre `semana`.
    `label_fn` (código→rótulo) é injetável para teste; default = de/para do SAP (`hd`)."""
    label_fn = label_fn or (lambda c: hd.status_usuario_label(c) or "Aberta")
    counts: dict[str, int] = {}
    for d in docs:
        if not _cobre(d.get("valido_de"), d.get("valido_ate"), semana):
            continue
        lbl = label_fn(d.get("status_usuario")) or "Aberta"
        counts[lbl] = counts.get(lbl, 0) + 1
    return counts


# ---- captura (escrita) ----------------------------------------------------------------

def capturar_backlog(semana: str | None = None, silent: bool = True) -> dict:
    """Grava a foto append-on-change do estado do backlog (SCD2, BR-12). Idempotente por semana."""
    c = get_mongo_connection(COLL_HIST, silent=silent)
    if c is None:
        return {"ok": False, "motivo": "banco indisponível"}
    semana = semana or hd.semana_atual()
    atual = _estado_atual_backlog(silent)
    vigentes = {d["ordem"]: d for d in c.find({"valido_ate": None})}
    inserts, close_ids = _diff_backlog(atual, vigentes, semana)
    agora = hd._agora_brt()
    for cid in close_ids:
        c.update_one({"_id": cid}, {"$set": {"valido_ate": semana}})
    for doc in inserts:
        doc["coletado_em"] = agora
        c.insert_one(doc)
    return {"ok": True, "semana": semana, "novos": len(inserts), "encerrados": len(close_ids)}


def capturar_fora_do_plano(semana: str | None = None, silent: bool = True) -> dict:
    """Snapshot semanal de trabalho fora do plano (BR-10): ordens com realizado > 0 que NÃO estão
    atribuídas no quadro da semana. Upsert por semana (idempotente). Forward-only proxy."""
    c = get_mongo_connection(COLL_FORA, silent=silent)
    if c is None:
        return {"ok": False, "motivo": "banco indisponível"}
    semana = semana or hd.semana_atual()
    base = hd.montar_ordens(silent=silent)
    atribuidas = {str(a.get("ordem")) for a in hd.listar_atribuicoes(semana, silent)}
    ordens_fora, horas_min = 0, 0
    if base:
        for aufnr, o in base["ordens"].items():
            real = int(o.get("realizado_min") or 0)
            if real > 0 and str(aufnr) not in atribuidas:
                ordens_fora += 1
                horas_min += real
    c.update_one({"semana": semana},
                 {"$set": {"semana": semana, "ordens": ordens_fora,
                           "horas": round(horas_min / 60, 1), "coletado_em": hd._agora_brt()}},
                 upsert=True)
    return {"ok": True, "semana": semana, "ordens": ordens_fora, "horas": round(horas_min / 60, 1)}


def capturar_semanal(semana: str | None = None, silent: bool = True) -> dict:
    """Captura Fase 2 da semana: estado do backlog (SCD2) + trabalho fora do plano. 1×/semana."""
    ensure_indexes_historico(silent)
    return {"backlog": capturar_backlog(semana, silent),
            "fora_do_plano": capturar_fora_do_plano(semana, silent)}


# ---- leitura (séries) -----------------------------------------------------------------

def serie_backlog_status(sem_ini: str, sem_fim: str, silent: bool = True) -> list[dict]:
    """Estado do backlog por semana: [{semana, status:{rótulo:n}}]. Vazio nas semanas sem captura."""
    c = get_mongo_connection(COLL_HIST, silent=silent)
    docs = (list(c.find({}, {"status_usuario": 1, "valido_de": 1, "valido_ate": 1, "_id": 0}))
            if c is not None else [])
    return [{"semana": W, "status": _contar_status(docs, W)} for W in _semanas_entre(sem_ini, sem_fim)]


def serie_fora_do_plano(sem_ini: str, sem_fim: str, silent: bool = True) -> list[dict]:
    """Trabalho fora do plano por semana: [{semana, ordens, horas}] a partir da captura Fase 2."""
    c = get_mongo_connection(COLL_FORA, silent=silent)
    por_sem = {}
    if c is not None:
        for d in c.find({}, {"semana": 1, "ordens": 1, "horas": 1, "_id": 0}):
            por_sem[d["semana"]] = d
    out = []
    for W in _semanas_entre(sem_ini, sem_fim):
        d = por_sem.get(W)
        out.append({"semana": W, "ordens": (d or {}).get("ordens"), "horas": (d or {}).get("horas")})
    return out
