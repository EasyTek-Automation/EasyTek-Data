# -*- coding: utf-8 -*-
"""Camada de dados do quadro semanal de Hora-Homem (SDD hh-management, DS-03/DS-08).

Lê os snapshots das collections-fonte de HH (`sap_hh_planejado`/`sap_hh_realizado`,
alimentadas pelos jobs do sap-scheduler), une por (ordem, operação) e agrega por ordem,
cruzando com o esqueleto da ordem do `sap_backlog` (cabeçalho/disciplina/hierarquia). Mantém
a camada de ATRIBUIÇÃO local (`hh_planejamento`) — estado do PCM, por semana, nunca enviado
ao SAP (BR-11). Lê SÓ do Mongo. Degradação graciosa (retorna None/vazio se o Mongo cair).

Pareado com `backlog_data.py` (reusa `carregar_ativos`/`enriquecer_local` para Linha/Conjunto).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytz

try:
    from src.database.connection import get_mongo_connection
    from src.utils import backlog_data as bd
    from src.utils.hh_executores import nomes_executores
    from src.utils import periodos_quadro
except ImportError:  # execução fora do pacote src
    from database.connection import get_mongo_connection
    from utils import backlog_data as bd
    from utils.hh_executores import nomes_executores
    from utils import periodos_quadro

COLL_PLAN = "sap_hh_planejado"
COLL_REAL = "sap_hh_realizado"
COLL_ATRIB = "hh_planejamento"
COLL_MOTIVOS = "hh_motivos"            # categorias de motivo de replanejamento (config — BR-16)
COLL_STATUS = "hh_status_mapa"         # de/para código SAP → rótulo legível (BR-17)
COLL_STATUS_USR = "hh_status_usuario"  # de/para status do USUÁRIO (USTXT) → rótulo legível (B30)
COLL_REPLAN = "hh_replanejamentos"     # auditoria de replanejamento (BR-16)

# de/para default do status do usuário (USTXT — B30). O admin pode sobrepor/ampliar via
# `hh_status_usuario` (codigo_sap → rotulo). Dá recurso ao PCM além do "pendente" binário.
_STATUS_USR_DEFAULT = {
    "ABIE": "Aberta", "ENTR": "Em Tratamento", "ENPA": "Em Pausa",
    "ESAC": "Aceitação de Espera", "CERR": "Encerrada", "CANC": "Cancelada",
}
COLL_CONFIG = "hh_config"              # config de capacidade (disponível/turno + meta %) — SP-13
CAP_ID = "capacidade"                  # _id do doc de config de capacidade em hh_config
META_ID = "meta"

# Categorias default de motivo de replanejamento (BR-16 / SP-08.3). Cadastráveis pelo admin.
MOTIVOS_DEFAULT = [
    "Produção não liberou a máquina",
    "Falta de material / compras",
    "Falta de recurso ou ferramenta",
    "Indisponibilidade do técnico",
    "Entrou algo mais urgente (corretiva)",
    "Retrabalho / serviço não concluído",
    "Outro",
]
# Alterações que EXIGEM justificativa (BR-16 / SP-08.1). Inversão de dia intra-semana NÃO exige.
ALTERACOES_COM_MOTIVO = ("mover_semana", "remover", "trocar_tecnico", "remontar_divisao")
_BRT = pytz.timezone("America/Sao_Paulo")

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


# ---- semana (BR-09: Mon-first, ISO YYYY-Www) -----------------------------------------

def _agora_brt() -> datetime:
    """Agora no fuso BRT (base de semana corrente / carimbos)."""
    return datetime.now(tz=pytz.UTC).astimezone(_BRT)


def semana_atual() -> str:
    """Semana ISO corrente como 'YYYY-Www' (Mon-first). Ex.: '2026-W27'."""
    return iso_semana(_agora_brt())


def iso_semana(dt: datetime) -> str:
    """Converte um datetime para o rótulo ISO 'YYYY-Www'."""
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def semana_shift(semana: str, delta: int) -> str:
    """Semana deslocada `delta` semanas (±). Ex.: shift('2026-W27', -1) → '2026-W26'."""
    inicio = inicio_da_semana(semana) + timedelta(weeks=delta)
    return iso_semana(inicio)


def inicio_da_semana(semana: str) -> datetime:
    """Segunda-feira (00:00) da semana ISO 'YYYY-Www'."""
    y, w = semana.split("-W")
    return datetime.fromisocalendar(int(y), int(w), 1)


def datas_da_semana(semana: str) -> list[datetime]:
    """Os 7 dias (segunda→domingo) da semana ISO, como datetimes à meia-noite."""
    ini = inicio_da_semana(semana)
    return [ini + timedelta(days=i) for i in range(7)]


def semana_eh_futura(semana: str) -> bool:
    """True se a semana inteira ainda não começou (só planejado, sem realizado — BR-09)."""
    agora = _agora_brt()
    return inicio_da_semana(semana) > agora.replace(tzinfo=None)


def semana_atual_ou_futura(semana: str) -> bool:
    """True se a semana é a corrente ou posterior — só nelas se inclui/retira mão de obra
    temporária no quadro (GantManagement SP-17 item 10)."""
    return periodos_quadro.semana_cmp(semana, semana_atual()) >= 0


# ---- snapshots das collections-fonte -------------------------------------------------

def _carregar_snapshot(coll_nome: str, silent: bool = True):
    """Carrega o snapshot atual cru de uma collection-fonte de HH. None se Mongo indisponível."""
    coll = get_mongo_connection(coll_nome, silent=silent)
    if coll is None:
        return None
    meta = coll.find_one({"_id": META_ID})
    if not meta or not meta.get("coleta_id_atual"):
        return {"docs": [], "coleta_id": None, "coletado_em": None}
    cid = meta["coleta_id_atual"]
    docs = list(coll.find({"coleta_id": cid, "_id": {"$ne": META_ID}}))
    return {"docs": docs, "coleta_id": cid, "coletado_em": meta.get("coletado_em")}


def frescor_hh(silent: bool = True):
    """Carimbo de frescor (coletado_em mais antigo entre planejado/realizado). None se vazio.

    Usa o MAIS ANTIGO dos dois para o sinal "dado velho" — o quadro depende dos dois.
    """
    p = _carregar_snapshot(COLL_PLAN, silent)
    r = _carregar_snapshot(COLL_REAL, silent)
    cs = [s["coletado_em"] for s in (p, r) if s and s.get("coletado_em")]
    return min(cs) if cs else None


# ---- união + agregação por ordem (BR-02/03; núcleo SP-04.5 = por ordem) --------------

# cache em processo do resultado pesado (agregação de ~14k operações). Chaveado pelos
# coleta_ids das duas fontes → invalida sozinho quando entra coleta nova. A atribuição
# (hh_planejamento) NÃO entra aqui (é lida fresca e barata em montar_quadro). Perf 2026-06-30.
_ordens_cache: dict = {"key": None, "val": None}


def _coleta_ids(silent: bool = True) -> tuple:
    """Lê só os coleta_id atuais das três fontes (3 finds baratos) — chave do cache.

    Inclui o `sap_backlog` porque o universo da fila agora vem dele (ordens abertas); sem
    esse id no cache, uma coleta nova do backlog não invalidaria o resultado."""
    def _cid(coll):
        c = get_mongo_connection(coll, silent=silent)
        if c is None:
            return None
        m = c.find_one({"_id": META_ID}, {"coleta_id_atual": 1})
        return m.get("coleta_id_atual") if m else None
    return (_cid(COLL_PLAN), _cid(COLL_REAL), _cid(bd.COLL))


def montar_ordens(silent: bool = True) -> dict | None:
    """Monta o universo de ordens da fila a partir do `sap_backlog` (ordens ABERTAS, mesmo
    universo IW39 que o PCM já usa) e cruza com o HH planejado/realizado por operação.

    Inversão de fonte (2026-06-30): antes o universo vinha do IW37 (janela FSAVD ±90d), o que
    escondia as ordens abertas antigas sem operação planejada recente. Agora o backlog é o
    universo; IW37/IW47 são **enriquecimento** — dão o tempo planejado (`Σ ARBEI` por operação)
    e o realizado/aderência **quando a ordem tem**. Operações de ordens fora do backlog
    (preventivas futuras, encerradas) são ignoradas — não são pendência de planejamento.

    Cacheado em processo por (coleta_id_plan, coleta_id_real, coleta_id_backlog). Retorna
    {ordens, coleta_id_plan, coleta_id_real, coletado_em} ou None se o Mongo cair.
    """
    chave = _coleta_ids(silent)
    if chave != (None, None, None) and _ordens_cache["key"] == chave and _ordens_cache["val"] is not None:
        return _ordens_cache["val"]
    snap_p = _carregar_snapshot(COLL_PLAN, silent)
    snap_r = _carregar_snapshot(COLL_REAL, silent)
    snap_bl = bd.carregar_snapshot(silent=silent)
    if snap_bl is None and snap_p is None and snap_r is None:
        return None
    plan = (snap_p or {}).get("docs", [])
    real = (snap_r or {}).get("docs", [])

    # universo = ordens abertas do backlog, já enriquecidas com Linha/Conjunto
    idx_bl: dict[str, dict] = {}
    if snap_bl:
        idx_ativos = bd.carregar_ativos()
        enr = bd.enriquecer_local(snap_bl["ordens"], idx_ativos)
        idx_bl = {str(o.get("ordem")): o for o in enr}

    ordens: dict[str, dict] = {
        aufnr: {
            "ordem": aufnr, "planejado_min": 0, "realizado_min": 0,
            "executores": [], "status_sap": None, "operacoes": 0, "_centros": {}, "_textos": {},
        }
        for aufnr in idx_bl
    }

    # IW37 (tempo planejado) e IW47 (realizado) só acumulam em ordem que está no backlog
    for op in plan:
        o = ordens.get(str(op.get("ordem")))
        if o is None:
            continue
        o["planejado_min"] += int(op.get("planejado_min") or 0)
        o["operacoes"] += 1
        vornr = str(op.get("operacao") or "")
        o["_centros"][vornr] = op.get("centro_planejado")
        if op.get("texto_op"):
            o["_textos"][vornr] = op.get("texto_op")
    for op in real:
        o = ordens.get(str(op.get("ordem")))
        if o is None:
            continue
        o["realizado_min"] += int(op.get("realizado_min") or 0)
        for ex in (op.get("executores") or []):
            if ex not in o["executores"]:
                o["executores"].append(ex)
        if op.get("status_sap"):
            o["status_sap"] = op["status_sap"]

    # aderência por ordem (núcleo SP-04.5); None se sem planejado
    for o in ordens.values():
        plan_min = o["planejado_min"]
        o["aderencia"] = (o["realizado_min"] / plan_min) if plan_min > 0 else None

    _aplicar_cabecalho_backlog(ordens, idx_bl)

    resultado = {
        "ordens": ordens,
        "coleta_id_plan": (snap_p or {}).get("coleta_id"),
        "coleta_id_real": (snap_r or {}).get("coleta_id"),
        "coletado_em": frescor_hh(silent),
    }
    _ordens_cache["key"] = chave
    _ordens_cache["val"] = resultado
    return resultado


def _disc_classifica(centro: str | None) -> str | None:
    """Disciplina pelo prefixo do centro de trabalho (regra do backlog): Z1x→Mecânica,
    Z2x→Elétrica, Z03→Terceiros (serviço de empresa contratada — atribuível, coringa nos dois
    quadros; B15); demais (Z02/MAN/...) → None (não classifica por centro)."""
    c = (centro or "").strip().upper()
    if c.startswith("Z1"):
        return "Mecanica"
    if c.startswith("Z2"):
        return "Eletrica"
    if c == "Z03":
        return "Terceiros"
    if c == "Z01":
        return "Gestao"          # B34: gerente de manutenção (classificada, fora do quadro)
    if c == "Z04":
        return "Ferramentaria"   # B37: ferramentaria/matrizes (classificada, fora do quadro)
    return None


def _texto_repr(textos: dict) -> str:
    """Descrição representativa da ordem a partir dos textos das operações (LTXA1):
    operação 0010 primeiro, senão a primeira operação com texto. '' se nenhuma."""
    if not textos:
        return ""
    if textos.get("0010"):
        return textos["0010"]
    for op in sorted(textos):
        if textos[op]:
            return textos[op]
    return ""


def _disc_por_centros(centros: dict) -> str:
    """Disciplina da ordem a partir dos centros das suas operações (fallback do HH).

    Espelha o backlog (centro da operação 0010 primeiro); se a 0010 não classificar, usa a
    primeira operação com centro Z1x/Z2x. Sem nenhum → NaoClassificado.
    """
    if not centros:
        return "NaoClassificado"
    if "0010" in centros:
        d = _disc_classifica(centros["0010"])
        if d:
            return d
    for op in sorted(centros):
        d = _disc_classifica(centros[op])
        if d:
            return d
    return "NaoClassificado"


def _aplicar_cabecalho_backlog(ordens: dict, idx_bl: dict) -> None:
    """Anexa cabeçalho/disciplina/hierarquia de cada ordem a partir do `idx_bl` (backlog já
    carregado e enriquecido em `montar_ordens`, que agora é a fonte do universo).

    Disciplina: usa a do backlog se classificada (Mec/Elé); se o centro do backlog for `Z03`,
    é **Terceiros** (serviço de empresa contratada — atribuível cross-disciplina, B15); senão
    **deriva do centro das operações do próprio HH** (IW37 `ARBPL` — Z1x/Z2x/Z03), cobrindo o
    caso de a ordem estar no backlog como NaoClassificado mas ter centro de operação
    classificável. Ordem sem centro classificável → NaoClassificado.
    """
    for aufnr, o in ordens.items():
        bl = idx_bl.get(str(aufnr), {})
        # descrição: a do backlog se houver; senão o texto da operação do próprio HH (LTXA1)
        o["descricao"] = (bl.get("descricao") or "").strip() or _texto_repr(o.get("_textos") or {})
        disc_bl = bl.get("disciplina")
        centro_bl = (bl.get("centro_operacao_0010") or "").strip().upper()
        if disc_bl in ("Mecanica", "Eletrica", "Terceiros", "Gestao", "Ferramentaria"):
            o["disciplina"] = disc_bl                        # daemon já classificou (pós-B34/B37)
        elif centro_bl == "Z03":
            o["disciplina"] = "Terceiros"                    # remap read-time p/ dado pré-B34
        elif centro_bl == "Z01":
            o["disciplina"] = "Gestao"                       # remap read-time p/ dado pré-B34
        elif centro_bl == "Z04":
            o["disciplina"] = "Ferramentaria"                # remap read-time p/ dado pré-B37
        else:
            o["disciplina"] = _disc_por_centros(o.get("_centros") or {})
        o["centro_operacao_0010"] = centro_bl or None        # p/ o filtro sem-centro da fila (B37)
        o["categoria"] = bl.get("categoria")
        o["data_criacao"] = bl.get("data_criacao")
        o["data_inicio"] = bl.get("data_inicio")
        o["linha_nome"] = bl.get("_linha_nome")
        o["_linha_id"] = bl.get("_linha_id")
        o["local_instalacao"] = bl.get("local_instalacao", "")
        o["status_usuario"] = bl.get("status_usuario")   # B30: status do usuário (ABIE/ENTR/…)


def ordem_atribuivel(o: dict) -> bool:
    """Só ordem classificada é atribuível (BR-07): Mecânica, Elétrica ou Terceiros. Terceiros é
    coringa — aceita nos dois quadros (B15). NaoClassificado bloqueia."""
    return o.get("disciplina") in ("Mecanica", "Eletrica", "Terceiros")


def opcoes_a_planejar(semana: str, disc: str, busca: str = "", limite: int = 50,
                      silent: bool = True) -> list[dict]:
    """Ordens 'a planejar' de uma disciplina (não atribuídas na semana), filtradas por busca
    (nº da ordem ou descrição). Para o modal de associação por botão direito no slot. O slot de
    um quadro (Mec/Elé) também oferece as ordens **Terceiros** (coringa, B15), que podem pousar
    em qualquer quadro."""
    base = montar_ordens(silent)
    if base is None:
        return []
    ordens = base["ordens"]
    atribs = listar_atribuicoes(semana, silent)
    com_atrib = {str(a.get("ordem")) for a in atribs}
    b = (busca or "").strip().lower()
    out = []
    for aufnr, o in ordens.items():
        if o.get("disciplina") not in (disc, "Terceiros"):
            continue
        # sai da fila só quando TEM atribuição e está 100% alocada; parcial/sem-atrib continua (B18)
        if str(aufnr) in com_atrib and restante_ordem(atribs, aufnr, o.get("planejado_min")) <= 0:
            continue
        desc = o.get("descricao") or ""
        if b and b not in str(aufnr).lower() and b not in desc.lower():
            continue
        out.append({"ordem": str(aufnr), "descricao": desc,
                    "planejado_min": o.get("planejado_min"), "realizado_min": o.get("realizado_min")})
    out.sort(key=lambda x: x["ordem"])
    return out[:limite]


def pode_atribuir(ordem: str, funcionario_id: str, disc_quadro: str | None = None,
                  silent: bool = True, semana: str | None = None) -> bool:
    """True se a ordem pode ser atribuída a este técnico.

    Regra (B33, revisão 2026-07-16): valida contra o **quadro-destino** (`disc_quadro`, Mec/Elé) —
    o técnico tem de pertencer ao quadro onde a ordem foi solta. Isso permite **disciplina cruzada**
    (ordem Elétrica indo para o quadro de Mecânica e vice-versa): não é mais bloqueio, é decisão do
    PCM confirmada no ato do drop (o aviso é montado em `avisos_atribuicao`). Ordem **Terceiros**
    (coringa, B15) cai na mesma regra. Sem `disc_quadro` conhecido, cai na disciplina da própria
    ordem (retrocompat de chamadas sem quadro).

    Bloqueio duro que PERMANECE (BR-07): ordem **não classificada** (sem disciplina Mec nem Elé) não
    é atribuível — `ordem_atribuivel` é False e retorna False aqui.

    Com `semana` informada, recusa técnico que não conta naquela semana — mão de obra temporária
    não incluída no quadro (GantManagement BR-25 / DS-18 §4). Sem `semana`, retrocompat.
    """
    base = montar_ordens(silent)
    if base is None:
        return False
    o = base["ordens"].get(str(ordem))
    if not o or not ordem_atribuivel(o):
        return False
    # quadro-destino manda quando conhecido (permite cruzada Elé↔Mec — confirmada no drop);
    # sem quadro, valida contra a disciplina da própria ordem (retrocompat).
    alvo = disc_quadro if disc_quadro in ("Mecanica", "Eletrica") else o["disciplina"]
    if alvo not in ("Mecanica", "Eletrica"):
        return False
    for f in _carregar_funcionarios(silent):
        if str(f.get("_id")) == str(funcionario_id):
            if semana and not periodos_quadro.conta_na_semana(f, semana):
                return False
            return pertence_disciplina(f, alvo)
    return False


def disciplina_da_ordem(ordem: str, silent: bool = True) -> str | None:
    """Disciplina classificada da ordem (Mecanica/Eletrica/Terceiros/NaoClassificado) ou None.

    Usada no gate do drop (B33) para detectar disciplina cruzada e montar o aviso de confirmação.
    """
    base = montar_ordens(silent)
    o = (base or {}).get("ordens", {}).get(str(ordem)) if base else None
    return o.get("disciplina") if o else None


# ---- atribuição local (estado do PCM — DS-03; nunca vai ao SAP) ----------------------

def _coll_atrib(silent: bool = True):
    """Collection de atribuição (`hh_planejamento`). None se Mongo indisponível."""
    return get_mongo_connection(COLL_ATRIB, silent=silent)


def ensure_indexes_atrib() -> None:
    """Índice único (semana, ordem, funcionario_id, dia) + índices de leitura. Idempotente."""
    c = _coll_atrib(silent=True)
    if c is None:
        return
    c.create_index([("semana", 1), ("ordem", 1), ("funcionario_id", 1), ("dia", 1)],
                   unique=True, name="uniq_atrib")
    c.create_index([("semana", 1)], name="idx_semana")
    c.create_index([("semana", 1), ("funcionario_id", 1)], name="idx_semana_func")
    c.create_index([("ordem", 1)], name="idx_ordem")
    # BR-20/SP-09.6a: detecção das atribuídas AINDA NÃO congeladas pelo daemon `hh_entregas`.
    # Esparso — só indexa docs sem snapshot (`entrega` ausente). Idempotente.
    c.create_index([("entrega", 1)], name="idx_entrega", sparse=True)


def listar_atribuicoes(semana: str, silent: bool = True) -> list[dict]:
    """Atribuições de uma semana (todas as parcelas). [] se vazio/indisponível."""
    c = _coll_atrib(silent=silent)
    if c is None:
        return []
    return list(c.find({"semana": semana}))


def soma_parcelas(semana: str, ordem: str, silent: bool = True) -> int:
    """Soma das parcelas já atribuídas de uma ordem na semana (para validar divisão — SP-04)."""
    tot = 0
    for a in listar_atribuicoes(semana, silent):
        if str(a.get("ordem")) == str(ordem):
            tot += int(a.get("parcela_min") or 0)
    return tot


def restante_ordem(atribuicoes: list[dict], ordem: str, planejado_min,
                   excluir_func_dia: tuple | None = None) -> int:
    """Minutos ainda não atribuídos de uma ordem (regra de ouro retrocompat B18 / SP-04.1).

    Se QUALQUER parcela da ordem é `None` (ordem inteira — legado ou drop-inteiro), o restante é
    **0** (a ordem está 100% alocada, fora da fila). Senão, `planejado − Σ parcela_min`. Puro.
    `excluir_func_dia=(func_id, dia)` ignora o doc daquele slot — usado ao reeditar a própria
    parcela, para não descontá-la de si mesma.
    """
    soma = 0
    for a in atribuicoes:
        if str(a.get("ordem")) != str(ordem):
            continue
        if excluir_func_dia is not None and \
           (str(a.get("funcionario_id")), int(a.get("dia", -1))) == excluir_func_dia:
            continue
        p = a.get("parcela_min")
        if p is None:
            return 0
        soma += int(p)
    return max(0, int(planejado_min or 0) - soma)


def atribuicoes_desde(funcionario_id: str, semana: str, silent: bool = True) -> dict[str, int]:
    """{semana: minutos} das atribuições do técnico da `semana` em diante (BR-25 itens 5/7).

    Base da recusa de retirar/marcar temporário: chave presente = há ordem naquela semana (mesmo
    0 min). Parcela `None` = planejado da ordem (backlog vivo + snapshot `entrega`); se não achar,
    soma 0 mas a semana continua listada. String ISO zero-padded ⇒ `$gte` lexicográfico ==
    cronológico (índice `idx_semana_func`).
    """
    c = _coll_atrib(silent=silent)
    if c is None:
        return {}
    docs = list(c.find({"funcionario_id": str(funcionario_id), "semana": {"$gte": semana}}))
    if not docs:
        return {}
    ordens = {}
    if any(d.get("parcela_min") is None for d in docs):
        base = montar_ordens(silent) or {}
        ordens = overlay_entrega(base.get("ordens") or {}, docs, plan_iw37_por_ordem(silent))
    out: dict[str, int] = {}
    for d in docs:
        p = d.get("parcela_min")
        if p is None:
            p = (ordens.get(str(d.get("ordem"))) or {}).get("planejado_min") or 0
        out[d["semana"]] = out.get(d["semana"], 0) + int(p)
    return dict(sorted(out.items(), key=lambda kv: periodos_quadro._parse(kv[0])))


def _msg_ordens_atribuidas(nome: str, por_semana: dict[str, int], acao: str) -> str:
    """Mensagem de recusa: '<nome> tem 12h atribuídas em 2026-W45, 2026-W46. Mova essas ordens
    antes de <acao>.' (SP-17 itens 4/9)."""
    horas = sum(por_semana.values()) / 60
    h_txt = f"{horas:.1f}".replace(".", ",").replace(",0", "") + "h"
    return (f"{nome} tem {h_txt} atribuídas em {', '.join(por_semana)} no planejamento semanal. "
            f"Mova essas ordens antes de {acao}.")


def _audit_temporario(emp: dict, usuario: dict, acao: str, campo: str, antes, depois) -> None:
    """Grava no log de auditoria do Gantt (`gantt_audit_log`) — SP-17 item 16 / DS-18 §7."""
    try:
        from src.utils import gantt_db
    except ImportError:
        from utils import gantt_db
    gantt_db.append_audit_log({
        "timestamp":      datetime.utcnow(),
        "usuario_id":     (usuario or {}).get("id"),
        "usuario_nome":   (usuario or {}).get("nome"),
        "entidade":       "funcionario",
        "entidade_id":    str(emp.get("_id")),
        "entidade_nome":  emp.get("nome"),
        "acao":           acao,
        "campo_alterado": campo,
        "valor_anterior": str(antes) if antes is not None else None,
        "valor_novo":     str(depois) if depois is not None else None,
    })


def _fmt_periodos(periodos: list) -> str:
    """Periodos legíveis p/ auditoria: '2026-W42→2026-W48; 2026-W52→aberto'."""
    return "; ".join(f"{p.get('de') or 'início'}→{p.get('ate') or 'aberto'}" for p in periodos) or "—"


def marcar_temporario(funcionario_id: str, valor: bool, usuario: dict,
                      silent: bool = True) -> tuple[bool, str]:
    """Liga/desliga 'mão de obra temporária' de um funcionário EXISTENTE (BR-25 itens 7/8).

    Fixo→temporário: recusa se houver ordem atribuída da semana atual em diante; senão sai do
    quadro a partir da semana atual (passado preservado). Temporário→fixo: conta da semana atual
    em diante (passado preservado). Sem mudança de valor = no-op ok.
    """
    try:
        from src.utils import gantt_db
    except ImportError:
        from utils import gantt_db
    emp = gantt_db.get_employee_by_id(funcionario_id)
    if not emp:
        return False, "Funcionário não encontrado."
    atual = bool(emp.get("temporario"))
    valor = bool(valor)
    if atual == valor:
        return True, ""
    sem = semana_atual()
    periodos = emp.get("periodos_quadro") or []
    if valor:
        futuras = atribuicoes_desde(funcionario_id, sem, silent)
        if futuras:
            return False, _msg_ordens_atribuidas(emp.get("nome", "O funcionário"), futuras,
                                                 "marcar como temporário")
        novos = periodos_quadro.periodos_ao_marcar_temporario(periodos, sem)
    else:
        novos = periodos_quadro.periodos_ao_desmarcar(periodos, sem)
    gantt_db.update_employee(funcionario_id, {"temporario": valor, "periodos_quadro": novos})
    # semana em que a mudança passa a valer (SP-17 item 16)
    _audit_temporario(emp, usuario, "edicao", "temporario", atual, f"{valor} — a partir de {sem}")
    return True, ""


def incluir_temporario(funcionario_id: str, semana: str, usuario: dict,
                       silent: bool = True) -> tuple[bool, str]:
    """Inclui temporário no quadro da `semana` em diante, até ser retirado (BR-25 item 4)."""
    try:
        from src.utils import gantt_db
    except ImportError:
        from utils import gantt_db
    emp = gantt_db.get_employee_by_id(funcionario_id)
    if not emp or not emp.get("temporario"):
        return False, "Funcionário não é mão de obra temporária."
    if not emp.get("ativo", True):
        return False, "Funcionário inativo."
    if not semana_atual_ou_futura(semana):
        return False, "Semana encerrada — só é possível incluir na semana atual ou futura."
    if periodos_quadro.conta_na_semana(emp, semana):
        return False, f"{emp.get('nome')} já está no planejamento desta semana."
    antes = emp.get("periodos_quadro") or []
    novos = periodos_quadro.periodos_ao_incluir(antes, semana)
    gantt_db.update_employee(funcionario_id, {"periodos_quadro": novos})
    _audit_temporario(emp, usuario, "inclusao_quadro", "periodos_quadro",
                      _fmt_periodos(antes), _fmt_periodos(novos))
    return True, ""


def retirar_temporario(funcionario_id: str, semana: str, usuario: dict,
                       silent: bool = True) -> tuple[bool, str]:
    """Retira temporário do quadro da `semana` em diante; bloqueia se houver ordem (BR-25 item 5)."""
    try:
        from src.utils import gantt_db
    except ImportError:
        from utils import gantt_db
    emp = gantt_db.get_employee_by_id(funcionario_id)
    if not emp or not emp.get("temporario"):
        return False, "Funcionário não é mão de obra temporária."
    if not semana_atual_ou_futura(semana):
        return False, "Semana encerrada — só é possível retirar na semana atual ou futura."
    if not periodos_quadro.conta_na_semana(emp, semana):
        return False, f"{emp.get('nome')} não está no planejamento desta semana."
    futuras = atribuicoes_desde(funcionario_id, semana, silent)
    if futuras:
        return False, _msg_ordens_atribuidas(emp.get("nome", "O funcionário"), futuras, "retirar")
    antes = emp.get("periodos_quadro") or []
    novos = periodos_quadro.periodos_ao_retirar(antes, semana)
    gantt_db.update_employee(funcionario_id, {"periodos_quadro": novos})
    _audit_temporario(emp, usuario, "retirada_quadro", "periodos_quadro",
                      _fmt_periodos(antes), _fmt_periodos(novos))
    return True, ""


def carga_tecnico_dia(atribuicoes: list[dict], ordens: dict, func_id: str, dia: int) -> int:
    """Soma o planejado (min) das parcelas atribuídas a um técnico num dia (SP-13 — gatilho 70%).
    Parcela `None` = ordem inteira (planejado da ordem). Puro."""
    tot = 0
    for a in atribuicoes:
        if str(a.get("funcionario_id")) != str(func_id) or int(a.get("dia", -1)) != int(dia):
            continue
        o = ordens.get(str(a.get("ordem")))
        if not o:
            continue
        p = a.get("parcela_min")
        tot += int(p) if p is not None else int(o.get("planejado_min") or 0)
    return tot


def opcoes_parcela(restante_min: int) -> list[int]:
    """Opções de horas (min) oferecidas ao dividir uma ordem num slot (SP-04.6).

    Passo de 30 min até o restante, **mas** só os múltiplos que deixam sobra 0 ou ≥30 min, mais o
    restante inteiro. Resto quebrado acima de 30 (ex: 37, 52) → só o restante (o passo de 30
    deixaria um órfão < 30). Ex: 52→[52]; 90→[30,60,90]; 82→[30,82]; 17→[17]; 0→[]."""
    r = int(restante_min or 0)
    if r <= 0:
        return []
    passo = 30
    opcoes = set()
    m = passo
    while m < r:
        sobra = r - m
        if sobra == 0 or sobra >= passo:
            opcoes.add(m)
        m += passo
    opcoes.add(r)   # o restante inteiro é sempre uma opção
    return sorted(opcoes)


def _restante_ordem_semana(semana: str, ordem: str, excluir_func_dia: tuple | None = None,
                           silent: bool = True) -> int | None:
    """Restante de uma ordem lendo do banco (atribuições + planejado agregado). None se a ordem
    não for encontrada (não valida). Usado pela trava do `atribuir`."""
    base = montar_ordens(silent)
    if base is None:
        return None
    o = base["ordens"].get(str(ordem))
    if not o:
        return None
    return restante_ordem(listar_atribuicoes(semana, silent), ordem,
                          o.get("planejado_min"), excluir_func_dia)


def atribuir(semana: str, ordem: str, funcionario_id: str, dia: int,
             parcela_min: int | None, por: str, disciplina_quadro: str | None = None) -> dict:
    """Cria/atualiza uma atribuição (parcela) ordem→técnico→dia na semana. Estado local.

    Upsert pela chave única (semana, ordem, funcionario_id, dia). `parcela_min=None` = ordem
    inteira. `disciplina_quadro` = quadro onde a ordem pousou (Mec/Elé) — só relevante para
    ordens **Terceiros** (coringa, B15), que não têm quadro próprio; determina onde exibir e em
    qual capacidade contar. Gravado apenas quando informado (retrocompat: docs antigos sem o
    campo caem na disciplina da ordem). Retorna {ok, motivo}. A validação de regras é do
    callback (B5); aqui é a persistência.
    """
    c = _coll_atrib(silent=True)
    if c is None:
        return {"ok": False, "motivo": "banco indisponível"}
    # B48: parcela 0 (ou negativa) NÃO é atribuição — não gravar card fantasma de 0h. `None` (ordem
    # inteira) segue válido; só bloqueamos o zero explícito (o drop de ordem já cheia não cai aqui —
    # abre o modal mover/dividir no callback).
    if parcela_min is not None and int(parcela_min) <= 0:
        return {"ok": False, "motivo": "parcela deve ser maior que zero (0 min não é atribuição)"}
    # Trava-no-planejado (SP-04.1): Σ parcelas ≤ planejado da ordem. Só validamos quando é uma
    # parcela explícita; `None` (ordem inteira) segue sem checagem. Exclui o próprio slot da soma
    # (reeditar a mesma parcela não deve descontá-la de si). Ordem sem planejado conhecido não trava.
    if parcela_min is not None:
        rest = _restante_ordem_semana(semana, ordem,
                                      excluir_func_dia=(str(funcionario_id), int(dia)), silent=True)
        if rest is not None and int(parcela_min) > rest:
            return {"ok": False, "motivo": f"excede o planejado (restam {rest} min)"}
    agora = _agora_brt()
    campos = {"parcela_min": parcela_min, "atualizado_em": agora, "por": por}
    if disciplina_quadro is not None:
        campos["disciplina_quadro"] = disciplina_quadro
    # BR-20: persistir a disciplina da ordem no momento da atribuição. Quando a ordem for
    # concluída no SAP ela some do universo de abertas (`sap_backlog`); sem a disciplina gravada
    # aqui, `montar_quadro` não saberia em qual quadro (Mec/Elé) recolocar o snapshot de entrega.
    base = montar_ordens(silent=True)
    od = (base or {}).get("ordens", {}).get(str(ordem)) if base else None
    if od and od.get("disciplina"):
        campos["disciplina"] = od["disciplina"]
    c.update_one(
        {"semana": semana, "ordem": str(ordem), "funcionario_id": str(funcionario_id), "dia": int(dia)},
        {"$set": campos, "$setOnInsert": {"criado_em": agora}},
        upsert=True,
    )
    return {"ok": True, "motivo": "atribuído"}


def get_atribuicao(atrib_id):
    """Doc de uma atribuição (parcela) pelo `_id` — None se não achar. Usado para reabrir o modal
    de divisão a partir do botão ✂ do card (B20)."""
    from bson import ObjectId
    c = _coll_atrib(silent=True)
    if c is None:
        return None
    try:
        oid = atrib_id if isinstance(atrib_id, ObjectId) else ObjectId(str(atrib_id))
    except Exception:
        return None
    return c.find_one({"_id": oid})


def remover_atribuicao(atrib_id, por: str) -> dict:
    """Remove uma atribuição (parcela). A justificativa (replanejamento) é registrada à parte (B6)."""
    from bson import ObjectId
    c = _coll_atrib(silent=True)
    if c is None:
        return {"ok": False, "motivo": "banco indisponível"}
    oid = atrib_id if isinstance(atrib_id, ObjectId) else ObjectId(str(atrib_id))
    c.delete_one({"_id": oid})
    return {"ok": True, "motivo": "removido"}


def repartir_ordem(semana: str, ordem: str, destino_func: str, destino_dia: int,
                   para_min: int, disc: str | None, por: str) -> dict:
    """B48b: re-reparte uma ordem já 100% alocada quando o PCM a solta num slot NOVO.

    `para_min` = quanto vai para o destino. Como o restante é 0 (ordem cheia), o tempo sai das
    ATRIBUIÇÕES DE ORIGEM: reduz as parcelas (maiores primeiro) no total de `para_min`, removendo
    as que chegam a 0. Se `para_min` >= planejado é "mover tudo" (origens somem, destino recebe a
    ordem inteira = `parcela_min=None`). Estado local, sem SAP. Retorna {ok, motivo}."""
    c = _coll_atrib(silent=True)
    if c is None:
        return {"ok": False, "motivo": "banco indisponível"}
    base = montar_ordens(silent=True)
    planejado = int(((base or {}).get("ordens", {}).get(str(ordem)) or {}).get("planejado_min") or 0)
    para = int(para_min or 0)
    if para <= 0 or planejado <= 0:
        return {"ok": False, "motivo": "nada a repartir"}
    atribs = listar_atribuicoes(semana, silent=True)
    origens = [a for a in atribs if str(a.get("ordem")) == str(ordem)
               and not (str(a.get("funcionario_id")) == str(destino_func)
                        and int(a.get("dia", -1)) == int(destino_dia))]

    def _eff(a):
        p = a.get("parcela_min")
        return planejado if p is None else int(p)

    origens.sort(key=_eff, reverse=True)          # tira das maiores primeiro
    resta = para
    for a in origens:
        if resta <= 0:
            break
        eff = _eff(a)
        tira = min(eff, resta)
        novo = eff - tira
        resta -= tira
        if novo <= 0:
            c.delete_one({"_id": a["_id"]})        # origem esvaziou → some (nunca vira card 0h)
        else:
            c.update_one({"_id": a["_id"]},
                         {"$set": {"parcela_min": novo, "atualizado_em": _agora_brt(), "por": por}})
    dest_parcela = None if para >= planejado else para   # levou tudo → ordem inteira no destino
    return atribuir(semana, ordem, destino_func, destino_dia, dest_parcela, por, disciplina_quadro=disc)


# ---- capacidade & disponibilidade por turno (DS-05 / BR-08) --------------------------

# Disponível LÍQUIDO por turno (jornada − almoço) em min/dia — SP-13/SP-05.1 (revisão 2026-07-06).
# A=6h (turno curto, sem 1h de almoço); B/C/ADM=8h (9h − 1h). É o DEFAULT: sobrescrito pela config
# persistida `hh_config` (nível 2+) e pelo override `jornada_min` do técnico (cadastro do Gantt).
DISPONIVEL_DEFAULT = {"A": 360, "B": 480, "C": 480, "ADM": 480}
META_PCT_DEFAULT = 0.70   # meta de planejamento confortável (% do disponível) — gatilho do modal


def carregar_config_capacidade(silent: bool = True) -> dict:
    """Config de capacidade (SP-13): {disponivel_min: {turno: min}, meta_pct: float}. Defaults se
    não houver doc `hh_config`/_id=capacidade (retrocompat: sistema nunca fica sem capacidade)."""
    disp = dict(DISPONIVEL_DEFAULT)
    meta = META_PCT_DEFAULT
    c = get_mongo_connection(COLL_CONFIG, silent=silent)
    if c is not None:
        doc = c.find_one({"_id": CAP_ID})
        if doc:
            for k, v in (doc.get("disponivel_min") or {}).items():
                try:
                    disp[str(k).strip().upper()] = int(v)
                except (TypeError, ValueError):
                    continue
            if doc.get("meta_pct") is not None:
                meta = float(doc["meta_pct"])
    return {"disponivel_min": disp, "meta_pct": meta}


def salvar_config_capacidade(disponivel_min: dict, meta_pct: float, silent: bool = True) -> dict:
    """Persiste a config de capacidade (B19 — enforcement de nível fica no callback). Upsert do
    doc único _id=capacidade em `hh_config`."""
    c = get_mongo_connection(COLL_CONFIG, silent=silent)
    if c is None:
        return {"ok": False, "motivo": "banco indisponível"}
    disp = {}
    for k, v in (disponivel_min or {}).items():
        try:
            disp[str(k).strip().upper()] = int(v)
        except (TypeError, ValueError):
            continue
    c.update_one({"_id": CAP_ID},
                 {"$set": {"disponivel_min": disp, "meta_pct": float(meta_pct),
                           "atualizado_em": _agora_brt()}},
                 upsert=True)
    return {"ok": True}


def jornada_min(emp: dict, disponivel_map: dict | None = None) -> int:
    """Disponível líquido do técnico em min/dia (SP-13/SP-05.1). Precedência: override `jornada_min`
    do cadastro > disponível do turno (config `disponivel_map`, ou DISPONIVEL_DEFAULT)."""
    j = emp.get("jornada_min")
    if j is not None:
        return int(j)
    disp = disponivel_map if disponivel_map is not None else DISPONIVEL_DEFAULT
    return int(disp.get((emp.get("turno_padrao") or "").strip().upper(), 0))


def _overlap(a_ini: datetime, a_fim: datetime, ini: datetime, fim: datetime) -> bool:
    """True se [a_ini, a_fim) sobrepõe [ini, fim) — mesma regra do gantt_validation."""
    return ini < a_fim and a_ini < fim


def indisponivel_no_dia(assignments: list[dict], dia_ini: datetime) -> bool:
    """True se o técnico tem QUALQUER alocação no Gantt sobrepondo o dia [dia, dia+1) (BR-08/F4).

    Cobre 'alocado em outro serviço' E férias/folga (lançadas como alocação no Gantt). A
    feature LÊ essa disponibilidade — não modela ausência nova.
    """
    dia_fim = dia_ini + timedelta(days=1)
    for a in assignments:
        a_ini = a.get("data_hora_entrada")
        a_fim = a.get("data_hora_saida")
        if a_ini is None or a_fim is None:
            continue
        if _overlap(a_ini, a_fim, dia_ini, dia_fim):
            return True
    return False


def comprometimentos(funcionario_id: str, semana: str, dia: int, silent: bool = True) -> list[str]:
    """Títulos das atividades do Gantt em que o técnico está comprometido no dia-alvo (B32/SP-05.6).

    Usado no ato do drop para avisar o PCM ("Fulano está de Férias - 2026 neste dia — confirmar?").
    Reusa a disponibilidade (overlap `gantt_assignments`) e resolve o `titulo` de cada atividade
    que sobrepõe o dia. Lista deduplicada e ordenada; [] se o técnico está livre (ou Mongo caiu).

    Só é chamada no evento de drop (1 técnico / 1 dia) — nunca no `montar_quadro` (hot path).
    """
    try:
        from src.utils import gantt_db
    except ImportError:
        from utils import gantt_db
    try:
        datas = datas_da_semana(semana)
    except Exception:
        return []
    if not (0 <= int(dia) < len(datas)):
        return []
    dia_ini = datas[int(dia)]
    dia_fim = dia_ini + timedelta(days=1)
    try:
        assignments = gantt_db.get_assignments_by_employee(str(funcionario_id)) or []
    except Exception:
        return []
    titulos: list[str] = []
    vistos: set[str] = set()
    for a in assignments:
        a_ini = a.get("data_hora_entrada")
        a_fim = a.get("data_hora_saida")
        if a_ini is None or a_fim is None or not _overlap(a_ini, a_fim, dia_ini, dia_fim):
            continue
        try:
            act = gantt_db.get_activity_by_id(a.get("atividade_id")) or {}
        except Exception:
            act = {}
        titulo = (act.get("titulo") or "").strip() or "Comprometido no Gantt"
        if titulo not in vistos:
            vistos.add(titulo)
            titulos.append(titulo)
    return sorted(titulos, key=str.lower)


def calcular_capacidade(semana: str, funcionarios: list[dict], atribuicoes: list[dict],
                        ordens: dict, assignments_por_func: dict, disc: str | None = None,
                        disponivel_map: dict | None = None) -> dict:
    """Capacidade por (turno, dia) da semana (BR-08). Pura — recebe tudo pronto, sem I/O.

    - Disponível = Σ jornada dos técnicos ATIVOS do turno, descontando quem está indisponível
      no dia (overlap Gantt — `assignments_por_func[func_id]`).
    - Programado = Σ planejado das parcelas atribuídas àquele turno/dia (parcela_min, ou o
      planejado da ordem se a parcela for a ordem inteira).
    - Executado = Σ realizado das ordens das parcelas, rateado pela fração de planejado da
      parcela (reconcilia ao total da ordem; é agregado de display do rodapé, NÃO a aderência
      por ordem — SP-04.5).
    - % Programado = Programado ÷ Disponível; Aderência = Executado ÷ Programado.

    Retorna {turno: {dia(0..6): {disponivel, programado, executado, pct_programado, aderencia}}}.
    Disponível None quando não há técnico com jornada (não força zero).
    """
    func_por_id = {str(f.get("_id")): f for f in funcionarios}
    turnos = sorted({(f.get("turno_padrao") or "").strip().upper()
                     for f in funcionarios if f.get("ativo", True)} - {""})
    datas = datas_da_semana(semana)

    out: dict = {}
    for turno in turnos:
        ativos = [f for f in funcionarios
                  if f.get("ativo", True) and (f.get("turno_padrao") or "").strip().upper() == turno]
        out[turno] = {}
        for dia in range(7):
            dia_ini = datas[dia]
            # Disponível: soma jornada dos ativos presentes (não indisponíveis) no dia
            disp = 0
            tem_jornada = False
            for f in ativos:
                jm = jornada_min(f, disponivel_map)
                if jm <= 0:
                    continue
                tem_jornada = True
                if not indisponivel_no_dia(assignments_por_func.get(str(f.get("_id")), []), dia_ini):
                    disp += jm
            programado = 0
            executado = 0.0
            ordens_dia = set()
            for a in atribuicoes:
                if int(a.get("dia", -1)) != dia:
                    continue
                f = func_por_id.get(str(a.get("funcionario_id")))
                if f is None or (f.get("turno_padrao") or "").strip().upper() != turno:
                    continue
                ordem = ordens.get(str(a.get("ordem")), {})
                # só conta ordens DO quadro (igual aos slots — senão o resumo conta numa
                # disciplina ordem que aparece em slot de outra). O quadro-destino é o
                # `disciplina_quadro` da atribuição (Terceiros coringa, B15) ou, na falta dele,
                # a disciplina da própria ordem (Mec/Elé — retrocompat).
                board = a.get("disciplina_quadro") or ordem.get("disciplina")
                if disc is not None and board != disc:
                    continue
                ordens_dia.add(str(a.get("ordem")))
                plan_ordem = int(ordem.get("planejado_min") or 0)
                parcela = a.get("parcela_min")
                parcela = int(parcela) if parcela is not None else plan_ordem
                programado += parcela
                # rateia o realizado da ordem pela fração planejada da parcela (reconcilia ao total)
                if plan_ordem > 0:
                    executado += (ordem.get("realizado_min") or 0) * (parcela / plan_ordem)
            disponivel = disp if tem_jornada else None
            pct = (programado / disponivel) if disponivel else None
            ader = (executado / programado) if programado > 0 else None
            out[turno][dia] = {
                "disponivel": disponivel,
                "programado": programado,
                "executado": round(executado),
                "pct_programado": pct,
                "aderencia": ader,
                "n_ordens": len(ordens_dia),
            }
    return out


# ---- cabeçalho-indicador por dia (B44) -----------------------------------------------

def planejado_por_dia(atribuicoes: list[dict], ordens: dict) -> dict:
    """Total planejado (min) da FÁBRICA por dia da semana (0..6): soma de todas as parcelas
    atribuídas naquele dia, de qualquer disciplina/turno. Parcela sem `parcela_min` (ordem
    inteira) cai no planejado da ordem; ordem ausente do universo → 0. Pura."""
    out = {d: 0 for d in range(7)}
    for a in atribuicoes:
        dia = int(a.get("dia", -1))
        if dia not in out:
            continue
        parcela = a.get("parcela_min")
        if parcela is None:
            parcela = (ordens.get(str(a.get("ordem")), {}) or {}).get("planejado_min") or 0
        out[dia] += int(parcela or 0)
    return out


# Regra de capacidade de manutenção — a MESMA da aba Histórico Semanal
# (`hh_historico_data`): planejado/disponível contam só dias úteis, e o turno ADM não é mão de
# obra de execução (não pega ordem). Centralizadas aqui para o quadro e o relatório diário
# usarem o mesmo critério (B45 / BR-19 / BR-20).
DIAS_UTEIS = (0, 1, 2, 3, 4)          # seg–sex; sábado/domingo fora do denominador
CAP_TURNOS_EXCLUIR = {"ADM"}          # ADM não recebe ordem → fora da capacidade de execução


def plan_iw37_por_ordem(silent: bool = True) -> dict:
    """{ordem: Σ planejado_min} de **todas** as ordens do snapshot IW37 — inclusive as que já
    saíram do backlog (B54).

    `montar_ordens` só acumula o IW37 de ordens que estão no backlog (abertas); esta leitura é
    deliberadamente mais ampla, porque a ordem encerrada continua no snapshot do IW37 e é a única
    fonte que traz **todas** as operações dela. Usada para recompor o planejado congelado.
    """
    snap = _carregar_snapshot(COLL_PLAN, silent)
    out: dict[str, int] = {}
    for op in (snap or {}).get("docs", []):
        o = str(op.get("ordem") or "")
        if o:
            out[o] = out.get(o, 0) + int(op.get("planejado_min") or 0)
    return out


def planejado_de_entrega(ent: dict, aufnr: str, plan_iw37: dict | None = None) -> int:
    """Planejado de uma ordem já fechada, corrigindo o snapshot congelado (B54). Puro.

    O daemon congela `entrega.planejado_min` a partir do IW47, que só devolve as operações **com
    apontamento**. Como o manutentor não aponta operação a operação, uma ordem de 5 operações de
    30 min era congelada com 30 min em vez de 150. Aqui o valor volta ao total: prevalece o maior
    entre o congelado e a soma das operações no IW37, que traz a ordem inteira.

    Usa `max` de propósito — o compromisso registrado nunca deve encolher na releitura, e nenhuma
    ordem do snapshot do cliente tem IW37 menor que o congelado (medido em 2026-08-25: 0 de 439).
    """
    cong = int(ent.get("planejado_min") or 0)
    return max(cong, int((plan_iw37 or {}).get(str(aufnr), 0) or 0))


def overlay_entrega(ordens: dict, atrib_docs: list[dict], plan_iw37: dict | None = None) -> dict:
    """Cópia de `ordens` (backlog vivo = abertas) sobreposta pelo snapshot `entrega` das ordens
    já FECHADAS encontradas nas atribuições — SÓ para os cálculos de capacidade (B45 / BR-20).

    Ordem concluída sai do backlog e seu `planejado_min` sumiria do indicador (embora o card do
    técnico ainda o mostre pelo mesmo snapshot). Este overlay devolve o valor congelado. NÃO
    altera o dict original: o laço que distribui os cards usa `ordens.get(aufnr) is None` para
    detectar a ordem sumida e chamar `_card_de_entrega` — por isso o dicionário é separado e
    usado só nos cálculos. Mesma regra de `hh_historico_data._ordens_para_capacidade`."""
    out = {str(k): dict(v) for k, v in ordens.items()}
    for d in atrib_docs:
        ent = d.get("entrega")
        if ent and ent.get("planejado_min") is not None:
            o = str(d.get("ordem"))
            out[o] = {**out.get(o, {}),
                      "planejado_min": planejado_de_entrega(ent, o, plan_iw37),
                      "realizado_min": ent.get("realizado_min") or 0}
    return out


def disponivel_por_dia(funcionarios: list[dict], assignments_por_func: dict,
                       disponivel_map: dict | None, semana: str,
                       atribuicoes: list[dict] | None = None) -> dict:
    """Disponível líquido da FÁBRICA por dia (0..6): Σ jornada dos técnicos ATIVOS, descontando
    quem está indisponível no dia (overlap Gantt). Cada técnico conta UMA vez — não duplica quem
    pertence às duas disciplinas (ao contrário de somar as capacidades por disciplina). Pura.

    Dias úteis (`DIAS_UTEIS`): conta a fábrica inteira e exclui o turno ADM
    (`CAP_TURNOS_EXCLUIR`), que não é mão de obra de execução (B45 / BR-19 / BR-20).

    Fim de semana (B53): não há turno cadastrado para sáb/dom, então o dia só ganha denominador
    quando tem serviço marcado — e aí vale a jornada de **quem está lançado naquele dia**, não a
    da fábrica (medir 6h40 de um técnico contra as 132h de todos leria 5% e mentiria; contra as 8h
    dele lê 83%, que é a hora extra real). O turno ADM conta aqui: se foi escalado no fim de
    semana está executando, e excluí-lo devolveria o dia ao `—` que a regra veio corrigir. Sem
    `atribuicoes` (ou sem ninguém lançado/válido no dia) o fim de semana fica 0, como antes.
    """
    datas = datas_da_semana(semana)
    out = {d: 0 for d in range(7)}
    for dia in DIAS_UTEIS:
        dia_ini = datas[dia]
        for f in funcionarios:
            if not f.get("ativo", True):
                continue
            if (f.get("turno_padrao") or "").strip().upper() in CAP_TURNOS_EXCLUIR:
                continue
            jm = jornada_min(f, disponivel_map)
            if jm <= 0:
                continue
            if not indisponivel_no_dia(assignments_por_func.get(str(f.get("_id")), []), dia_ini):
                out[dia] += jm
    if not atribuicoes:
        return out
    func_por_id = {str(f.get("_id")): f for f in funcionarios}
    for dia in (d for d in range(7) if d not in DIAS_UTEIS):
        dia_ini = datas[dia]
        lancados = {str(a.get("funcionario_id")) for a in atribuicoes
                    if int(a.get("dia", -1)) == dia}
        for fid in lancados:                        # set → cada técnico conta uma vez
            f = func_por_id.get(fid)
            if not f or not f.get("ativo", True):
                continue
            jm = jornada_min(f, disponivel_map)
            if jm <= 0:
                continue
            if not indisponivel_no_dia(assignments_por_func.get(fid, []), dia_ini):
                out[dia] += jm
    return out


def resumo_dias_cabecalho(planejado_dia: dict, disponivel_dia: dict, planejado_ant: dict) -> dict:
    """Resumo por dia (0..6) do cabeçalho-indicador (B44): planejado × disponível da fábrica e a
    variação % do PLANEJADO vs o mesmo dia da semana anterior. Pura.

    - `pct_programado` = planejado ÷ disponível (mesma leitura da faixa B21); None se disp = 0.
    - `delta_pct` = variação do planejado vs semana passada; None quando a semana passada teve 0
      planejado no dia (evita dividir por zero → a UI mostra '—'/'novo')."""
    out = {}
    for dia in range(7):
        plan = int(planejado_dia.get(dia, 0))
        disp = int(disponivel_dia.get(dia, 0))
        ant = int(planejado_ant.get(dia, 0))
        out[dia] = {
            "programado": plan,
            "disponivel": disp or None,
            "pct_programado": (plan / disp) if disp else None,
            "programado_ant": ant,
            "delta_pct": ((plan - ant) / ant) if ant > 0 else None,
        }
    return out


# ---- montagem do quadro (DS-06 / BR-07/19) -------------------------------------------

def _carregar_funcionarios(silent: bool = True) -> list[dict]:
    """Funcionários do cadastro único (gantt_employees). [] se indisponível."""
    try:
        from src.utils import gantt_db
    except ImportError:
        from utils import gantt_db
    try:
        return gantt_db.get_all_employees() or []
    except Exception:
        return []


def funcionarios_da_semana(funcionarios: list[dict], semana: str) -> list[dict]:
    """Funcionários que contam no quadro/disponível da `semana` — ponto ÚNICO do filtro de mão
    de obra temporária (GantManagement BR-25 / DS-18 §3). Sem temporários = lista intacta
    (menos inativos, que todo consumidor já descartava)."""
    return [f for f in funcionarios if periodos_quadro.conta_na_semana(f, semana)]


def pertence_disciplina(emp: dict, disc: str) -> bool:
    """True se o técnico pertence à disciplina.

    Campo `disciplinas` AUSENTE (None) → pertence às duas (retrocompat: setups antigos não
    perdem técnicos até serem curados). Campo PRESENTE (lista, inclusive vazia) → membership
    literal — lista vazia = NENHUMA disciplina (ex.: pessoal ADM que não é Mec nem Elé).
    """
    ds = emp.get("disciplinas")
    if ds is None:
        return True
    return disc in ds


def _func_fora_disc(funcionarios: list[dict], disc: str) -> list[dict]:
    """Técnicos ativos que NÃO estão na disciplina (para o picker '+ adicionar técnico')."""
    out = []
    for f in funcionarios:
        if not f.get("ativo", True):
            continue
        if not pertence_disciplina(f, disc):
            out.append({"id": str(f.get("_id")), "nome": f.get("nome", str(f.get("_id")))})
    return sorted(out, key=lambda x: x["nome"].lower())


def set_disciplina_funcionario(funcionario_id: str, disc: str, incluir: bool, silent: bool = True) -> dict:
    """Adiciona/remove uma disciplina do técnico (configura quem aparece em Mec/Elé).

    Materializa o default: se `disciplinas` ainda não existe, parte de ['Mecanica','Eletrica']
    (estado atual visível) e então aplica a mudança — assim 'remover da Elétrica' deixa só Mecânica.
    """
    try:
        from src.utils import gantt_db
    except ImportError:
        from utils import gantt_db
    emp = gantt_db.get_employee_by_id(funcionario_id)
    if not emp:
        return {"ok": False, "motivo": "técnico não encontrado"}
    atual = emp.get("disciplinas")
    if atual is None:
        atual = ["Mecanica", "Eletrica"]      # materializa o default só na 1ª curadoria
    novo = [d for d in atual if d != disc]
    if incluir and disc not in novo:
        novo.append(disc)
    gantt_db.update_employee(funcionario_id, {"disciplinas": novo})
    return {"ok": True, "disciplinas": novo}


def _assignments_por_func(funcionarios: list[dict], silent: bool = True) -> dict:
    """Mapa funcionario_id → alocações do Gantt (para disponibilidade — BR-08/F4)."""
    try:
        from src.utils import gantt_db
    except ImportError:
        from utils import gantt_db
    out = {}
    for f in funcionarios:
        fid = str(f.get("_id"))
        try:
            out[fid] = gantt_db.get_assignments_by_employee(fid) or []
        except Exception:
            out[fid] = []
    return out


def _naive(dt: datetime) -> datetime:
    """Remove tzinfo para subtração segura (mistura aware×naive vinda do Mongo)."""
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


def _idade_dias(o: dict, hoje: datetime) -> int | None:
    """Idade da ordem em dias (BR-19): de data_criacao (ou data_inicio). None se sem data."""
    base = o.get("data_criacao") or o.get("data_inicio")
    if base is None:
        return None
    return max(0, (_naive(hoje) - _naive(base)).days)


def carry_over(ordem: str, semana: str, silent: bool = True) -> int:
    """Quantas semanas ANTERIORES a ordem já foi planejada e não saiu daqui (BR-19, aprox.).

    Conta semanas distintas com atribuição da ordem antes da semana corrente — sinal de arrasto.
    """
    c = _coll_atrib(silent=silent)
    if c is None:
        return 0
    semanas = c.distinct("semana", {"ordem": str(ordem)})
    return sum(1 for s in semanas if s < semana)


def carry_over_map(semana: str, silent: bool = True) -> dict:
    """Carry-over de TODAS as ordens numa única query (evita N+1 — perf). {ordem: nº de semanas
    anteriores com atribuição}. Só as ordens com carry-over > 0 aparecem no dict."""
    c = _coll_atrib(silent=silent)
    if c is None:
        return {}
    from collections import defaultdict
    semanas_por_ordem: dict[str, set] = defaultdict(set)
    for d in c.find({"semana": {"$lt": semana}}, {"ordem": 1, "semana": 1, "_id": 0}):
        semanas_por_ordem[str(d.get("ordem"))].add(d.get("semana"))
    return {o: len(ws) for o, ws in semanas_por_ordem.items() if ws}


# rótulo derivado do status_saida quando o snapshot NÃO tem status do usuário (retrocompat de
# snapshots antigos, resolvidos por status de sistema antes da decisão 2026-07-15). `cancelada` é
# terminal e não reprocessa, então DEPENDE deste fallback; `concluida`/`teco` (legado) reprocessam,
# mas mostram "Encerrada" até lá — nunca "saiu do backlog".
_SAIDA_LABEL_LEGADO = {"cancelada": "Cancelada", "encerrada": "Encerrada",
                       "concluida": "Encerrada", "teco": "Encerrada"}


def _label_status_saida(ent: dict, mapa_usr: dict = None):
    """Rótulo do pill de uma ordem que saiu do backlog: o status do usuário (USTXT) quando houver,
    senão derivado do `status_saida` (retrocompat). None → pill neutro 'saiu do backlog'."""
    stu = ent.get("status_usuario")
    if stu:
        return status_usuario_label(stu, mapa_usr)
    return _SAIDA_LABEL_LEGADO.get(ent.get("status_saida"))


def _card_de_entrega(a: dict, mapa_usr: dict = None, plan_iw37: dict | None = None) -> dict:
    """Card sintético de uma atribuição cuja ordem SAIU do universo de abertas (BR-20/SP-09.6e).

    Quando a ordem sai do `sap_backlog` (fechada/cancelada no SAP), a atribuição continuaria
    apontando para uma ordem inexistente e o card sumiria do quadro (o furo que a BR-20 corrige).
    Este helper devolve um dict tipo-ordem para o card **nunca** sumir:

    - snapshot congelado (`entrega`) presente e não superado → render do resultado final
      (planejado/realizado/aderência) + o **status do usuário** da ordem (decisão 2026-07-15: o
      estado exibido é o status do usuário — Encerrada/Cancelada/Em Pausa…, via `_status_usuario_label`);
    - sem snapshot ainda (daemon `hh_entregas` não rodou) ou snapshot superado (ordem reaberta) →
      placeholder "aguardando fechamento".

    Nunca retorna None. A disciplina vem da atribuição (`disciplina_quadro` p/ Terceiros, ou a
    `disciplina` persistida no ato — BR-20), com o cabeçalho congelado como reforço.
    """
    aufnr = str(a.get("ordem"))
    disc_atrib = a.get("disciplina_quadro") or a.get("disciplina")
    ent = a.get("entrega")
    if not ent or ent.get("superado"):
        return {"ordem": aufnr, "disciplina": disc_atrib,
                "descricao": "(aguardando fechamento no SAP)",
                "_aguardando_fechamento": True}
    cab = ent.get("cabecalho") or {}
    stu = ent.get("status_usuario")
    # estado exibido = status do usuário (Encerrada/Cancelada/Em Pausa…); retrocompat p/ snapshots
    # antigos sem USTXT via status_saida. Só cai em "saiu do backlog" se nem um nem outro derem rótulo.
    label = _label_status_saida(ent, mapa_usr)
    # B54: o planejado congelado veio do IW47 (só operações apontadas) — recompõe pelo IW37
    _plan = planejado_de_entrega(ent, aufnr, plan_iw37)
    _real = int(ent.get("realizado_min") or 0)
    # Linha do card congelado: o daemon guardou o TPLNR (`local_instalacao`) mas nem sempre a
    # `linha_nome`. Quando faltar, re-resolve ao vivo pela árvore oficial (retroativo + self-heal).
    linha_nome = cab.get("linha_nome")
    linha_id = cab.get("_linha_id")
    if not (linha_nome or "").strip():
        _linha = bd.resolver_linha(cab.get("local_instalacao"))
        if _linha:
            linha_nome = _linha.get("descricao")
            linha_id = _linha.get("id")
    return {"ordem": aufnr,
            "disciplina": cab.get("disciplina") or disc_atrib,
            "descricao": cab.get("descricao") or "",
            "categoria": cab.get("categoria"),
            "local_instalacao": cab.get("local_instalacao"),
            "centro_operacao_0010": cab.get("centro_operacao_0010"),
            "linha_nome": linha_nome,
            "_linha_id": linha_id,
            "planejado_min": _plan,
            "realizado_min": _real,
            # aderência recalculada com o planejado corrigido (B54) — o congelado foi dividido por
            # uma operação só e produzia números como 3.700%
            "aderencia": (_real / _plan) if _plan else ent.get("aderencia"),
            "status_sap": ent.get("status_sistema") or ent.get("status_sap_raw"),
            "status_usuario": stu,
            "_status_usuario_label": label,
            "_status_usuario_cor": cor_status_usuario(stu, label),
            "_saiu_backlog": not label,
            "_pendente": False,               # ordem que saiu não é pendência (BR-17)
            "_restante_min": 0,               # nada a distribuir (bolinha "full")
            "_entregue": ent.get("status_saida") in ("encerrada", "concluida")}


def montar_quadro(semana: str, silent: bool = True) -> dict | None:
    """Monta o quadro semanal completo (DS-06). None se Mongo cair.

    Estrutura de retorno:
      {
        semana, eh_futura, coletado_em,
        disciplinas: {"Mecanica"|"Eletrica": {
            tecnicos: [{funcionario_id, nome, turno, dias: {0..6: [ordens]}}],
            capacidade: {turno: {dia: {...}}},
        }},
        a_planejar: {"Mecanica": [ordens], "Eletrica": [ordens]},   # classificadas não atribuídas
        terceiros: [ordens],                                        # Z03 não atribuídas (coringa, B15)
        pendentes_classificacao: [ordens],                          # NaoClassificado (bloqueadas)
      }
    """
    base = montar_ordens(silent)
    if base is None:
        return None
    ordens = base["ordens"]
    atribuicoes = listar_atribuicoes(semana, silent)
    atrib_ant = listar_atribuicoes(semana_shift(semana, -1), silent)   # p/ o Δ% do cabeçalho (B44)
    # ordens abertas + snapshot `entrega` das já fechadas — SÓ para os cálculos de capacidade
    # (B45): sem isto o planejado das semanas passadas evapora conforme as ordens fecham no SAP.
    # Cobre esta semana E a anterior (o Δ% compara contra ela). NÃO usar no laço dos cards.
    plan_iw37 = plan_iw37_por_ordem(silent)
    ordens_cap = overlay_entrega(ordens, atribuicoes + atrib_ant, plan_iw37)
    funcionarios = _carregar_funcionarios(silent)
    # só quem conta nesta semana entra em linhas/capacidade/disponível (BR-25: temporário fora
    # salvo inclusão); `funcionarios` completo segue só para lookup de nome
    funcs_sem = funcionarios_da_semana(funcionarios, semana)
    assignments = _assignments_por_func(funcs_sem, silent)
    hoje = _agora_brt()

    func_por_id = {str(f.get("_id")): f for f in funcionarios}
    cfg_cap = carregar_config_capacidade(silent)
    # restante por ordem (B18): 0 = 100% alocada; >0 = parcial. Ordem SEM atribuição nunca sai da
    # fila (mesmo planejado=0) — só sai quem tem atribuição e restante ≤ 0.
    ordens_com_atrib: set[str] = {str(a.get("ordem")) for a in atribuicoes}
    restante_por_ordem = {str(aufnr): restante_ordem(atribuicoes, aufnr, o.get("planejado_min"))
                          for aufnr, o in ordens.items()}

    # pendência derivada do status (BR-17) — 1 query do de/para, marca todas as ordens
    concluidos = _status_concluidos(silent)
    mapa_usr = _mapa_status_usuario(silent)   # B30: status do usuário → rótulo (1 leitura do de/para)
    for o in ordens.values():
        o["_pendente"] = not (o.get("status_sap") and o["status_sap"] in concluidos)
        o["_status_usuario_label"] = status_usuario_label(o.get("status_usuario"), mapa_usr)
        o["_status_usuario_cor"] = cor_status_usuario(o.get("status_usuario"), o["_status_usuario_label"])

    # esqueleto disciplina → técnico → dia. Técnicos são CONFIGURÁVEIS por disciplina
    # (campo `disciplinas` do funcionário): sem o campo → aparece nas duas (retrocompat).
    disciplinas = {}
    for disc in ("Mecanica", "Eletrica"):
        disc_funcs = [f for f in funcs_sem if pertence_disciplina(f, disc)]
        tecnicos = []
        for f in disc_funcs:
            tecnicos.append({
                "funcionario_id": str(f.get("_id")), "nome": f.get("nome", str(f.get("_id"))),
                "turno": (f.get("turno_padrao") or "").strip().upper(),
                # disponível líquido do técnico/dia (B21: barra de ocupação por célula)
                "disponivel_min": jornada_min(f, cfg_cap["disponivel_min"]),
                "temporario": bool(f.get("temporario")),   # UI: etiqueta + "retirar" (DS-19 §5)
                "dias": {d: [] for d in range(7)},
            })
        # capacidade por disciplina: só os técnicos daquela disciplina E ordens daquela disciplina
        capac = calcular_capacidade(semana, disc_funcs, atribuicoes, ordens_cap, assignments, disc=disc,
                                    disponivel_map=cfg_cap["disponivel_min"])
        disciplinas[disc] = {"tecnicos": {t["funcionario_id"]: t for t in tecnicos},
                             "capacidade": capac, "meta_pct": cfg_cap["meta_pct"],
                             "disponiveis_fora": _func_fora_disc(funcs_sem, disc)}

    # mapa técnico → quadro (disciplina), p/ posicionar ordem fechada pelo quadro DO TÉCNICO quando
    # a ordem perdeu/não tem classificação válida (B29 — ver abaixo).
    func_disc = {fid: dnome for dnome, dd in disciplinas.items() for fid in dd["tecnicos"]}

    # distribui as ordens atribuídas nos slots (técnico/dia) do quadro-destino. Para Terceiros
    # (coringa, B15) o quadro é o gravado na atribuição (`disciplina_quadro`); Mec/Elé usam a
    # disciplina da própria ordem (retrocompat: docs antigos sem o campo).
    for a in atribuicoes:
        if a.get("parcela_min") == 0:      # B48: card fantasma de 0h — não é atribuição, não renderiza
            continue                        # (cura os já gravados; a ordem volta pra fila via restante)
        aufnr = str(a.get("ordem"))
        o = ordens.get(aufnr)
        sumida = o is None
        if sumida:
            # ordem saiu do universo de abertas (concluída/cancelada no SAP). NÃO descarta a
            # atribuição (BR-20/SP-09.6e): render do snapshot congelado ou placeholder — nunca some.
            o = _card_de_entrega(a, mapa_usr, plan_iw37)
        fid = str(a.get("funcionario_id"))
        disc = a.get("disciplina_quadro") or o.get("disciplina")
        # ordem fechada cuja classificação se perdeu (NaoClassificado/sem centro) ainda foi
        # atribuída a um técnico — segue o quadro DO TÉCNICO (foi lá que o PCM a colocou), senão
        # sumiria de novo. Não muda a regra da ordem viva (só o caminho da sumida).
        if sumida and disc not in disciplinas:
            disc = func_disc.get(fid)
        if disc not in disciplinas:
            continue
        dia = int(a.get("dia", 0))
        tec = disciplinas[disc]["tecnicos"].get(fid)
        if tec is None:
            continue
        # ordem viva → restante calculado; ordem sumida (snapshot/placeholder) → _restante_min do card
        tec["dias"][dia].append({**o, "_atrib_id": str(a.get("_id")),
                                 "parcela_min": a.get("parcela_min"),
                                 "_restante_min": restante_por_ordem.get(aufnr, o.get("_restante_min"))})

    # "a planejar" (classificadas não atribuídas nesta semana) + sinais; Terceiros (coringa)
    # numa fila própria; e pendentes de classificação.
    a_planejar = {"Mecanica": [], "Eletrica": []}
    terceiros = []
    pendentes = []
    co_map = carry_over_map(semana, silent)   # carry-over de todas as ordens em 1 query (perf)
    for aufnr, o in ordens.items():
        # sai da fila só quando TEM atribuição e está 100% alocada; parcial (restante > 0) ou sem
        # atribuição continua exibida (B18) — não confundir "planejado=0" com "alocada"
        if str(aufnr) in ordens_com_atrib and restante_por_ordem.get(str(aufnr), 0) <= 0:
            continue
        if bd.esta_encerrada(o):                 # B35: encerrada/cancelada não entra na fila
            continue                             # (se já atribuída, o card fica no slot — laço acima)
        disc = o.get("disciplina")
        if disc in ("Gestao", "Ferramentaria"):  # B34/B37: classificadas, mas fora do quadro
            continue                             # (nem fila, nem "pendente de classificação")
        if disc not in ("Mecanica", "Eletrica", "Terceiros"):
            if bd.sem_centro_classificavel(o):   # B37: None/MAN não é classificável aqui → fora
                continue
            pendentes.append({**o, "_idade_dias": _idade_dias(o, hoje)})
            continue
        card = {**o, "_idade_dias": _idade_dias(o, hoje),
                "_carry_over": co_map.get(str(aufnr), 0),
                "_restante_min": restante_por_ordem.get(str(aufnr))}
        if disc == "Terceiros":
            terceiros.append(card)
        else:
            a_planejar[disc].append(card)
    # ordena: carry-over no topo, depois mais antigas (BR-19)
    for lst in (a_planejar["Mecanica"], a_planejar["Eletrica"], terceiros):
        lst.sort(key=lambda c: (-(c.get("_carry_over") or 0),
                                -(c.get("_idade_dias") or 0)))

    # converte tecnicos dict→lista (ordenada por nome) para a UI
    for disc in disciplinas:
        tecs = list(disciplinas[disc]["tecnicos"].values())
        tecs.sort(key=lambda t: t["nome"].lower())
        disciplinas[disc]["tecnicos"] = tecs

    # cabeçalho-indicador por dia (B44): planejado×disponível da fábrica + Δ% vs semana passada.
    # `ordens_cap` (B45) preserva o planejado das ordens já fechadas; `atrib_ant` veio no topo.
    planejado_dia = planejado_por_dia(atribuicoes, ordens_cap)
    disponivel_dia = disponivel_por_dia(funcs_sem, assignments, cfg_cap["disponivel_min"],
                                     semana, atribuicoes)
    planejado_ant = planejado_por_dia(atrib_ant, ordens_cap)
    resumo_dias = resumo_dias_cabecalho(planejado_dia, disponivel_dia, planejado_ant)

    return {
        "semana": semana,
        "eh_futura": semana_eh_futura(semana),
        "semana_aberta": semana_atual_ou_futura(semana),   # incluir/retirar temporário (SP-17.10)
        "coletado_em": base.get("coletado_em"),
        "disciplinas": disciplinas,
        "a_planejar": a_planejar,
        "terceiros": terceiros,
        "pendentes_classificacao": pendentes,
        "resumo_dias": resumo_dias,
        "meta_pct": cfg_cap["meta_pct"],
    }


# ---- cadastros de apoio + replanejamento (DS-07 / BR-16/17) --------------------------

def status_eh_concluida(status_sap: str | None, silent: bool = True) -> bool:
    """True se o status do SAP mapeia para 'concluída' (de/para hh_status_mapa — BR-17).

    A conclusão é SEMPRE do SAP (o PCM nunca marca à mão). Código sem de/para → não concluída
    (e deve ser sinalizado ao admin para mapear).
    """
    if not status_sap:
        return False
    c = get_mongo_connection(COLL_STATUS, silent=silent)
    if c is None:
        return False
    doc = c.find_one({"codigo_sap": status_sap})
    return bool(doc and doc.get("concluida"))


def pendencia_derivada(ordem: dict, silent: bool = True) -> bool:
    """Pendência é DERIVADA do status (ordem não concluída = pendente — BR-17). Nunca manual."""
    return not status_eh_concluida(ordem.get("status_sap"), silent)


def status_label(codigo: str | None, silent: bool = True) -> str | None:
    """Rótulo legível do status do SAP via de/para (hh_status_mapa). Código cru se sem mapa."""
    if not codigo:
        return None
    c = get_mongo_connection(COLL_STATUS, silent=silent)
    if c is None:
        return codigo
    d = c.find_one({"codigo_sap": codigo})
    return (d.get("rotulo") if d and d.get("rotulo") else codigo)


def _mapa_status_usuario(silent: bool = True) -> dict:
    """De/para do status do usuário (USTXT → rótulo): defaults + overrides de `hh_status_usuario`."""
    mapa = dict(_STATUS_USR_DEFAULT)
    c = get_mongo_connection(COLL_STATUS_USR, silent=silent)
    if c is not None:
        try:
            for d in c.find({}, {"codigo_sap": 1, "rotulo": 1}):
                if d.get("codigo_sap") and d.get("rotulo"):
                    mapa[str(d["codigo_sap"]).strip().upper()] = d["rotulo"]
        except Exception:
            pass
    return mapa


def status_usuario_label(codigo, mapa=None, silent: bool = True):
    """Rótulo do status do usuário (USTXT — B30). Casa o código inteiro; senão o 1º token (o USTXT
    pode vir com mais de um flag). Sem mapa → devolve o código cru. None → None."""
    if not codigo:
        return None
    mapa = mapa if mapa is not None else _mapa_status_usuario(silent)
    cod = str(codigo).strip().upper()
    if cod in mapa:
        return mapa[cod]
    primeiro = cod.split()[0] if cod.split() else cod
    return mapa.get(primeiro, codigo)


# cor do pill do status do usuário (pedido PCM 2026-07-15). Mapeada por CÓDIGO (1º token — pega
# combos tipo `ENPA PRIO`) e, sem código (snapshot legado), pelo RÓTULO.
_COR_STATUS_USR_COD = {"ABIE": "aberta",
                       "ENPA": "andamento", "ESAC": "andamento", "ENTR": "andamento",
                       "CERR": "encerrada", "CANC": "cancelada"}
_COR_STATUS_USR_LABEL = {"Aberta": "aberta", "Em Pausa": "andamento",
                         "Aceitação de Espera": "andamento", "Em Tratamento": "andamento",
                         "Encerrada": "encerrada", "Cancelada": "cancelada"}


def cor_status_usuario(codigo, label=None):
    """Categoria de cor do pill de status do usuário: `aberta` (vermelho), `andamento` (amarelo —
    Em Tratamento/Em Pausa/Aceitação de Espera), `encerrada` (verde), `cancelada` (cinza). Mapeia
    pelo código (1º token, casa `ENPA PRIO` etc.); sem código, pelo rótulo. None → sem cor especial
    (usa o pill padrão)."""
    if codigo:
        tok = str(codigo).strip().upper().split()
        if tok:
            c = _COR_STATUS_USR_COD.get(tok[0])
            if c:
                return c
    return _COR_STATUS_USR_LABEL.get(label)


def _aderencia_recomposta(ent: dict, aufnr: str, silent: bool = True):
    """Aderência da ordem fechada recalculada com o planejado corrigido (B54). None sem planejado."""
    plan = planejado_de_entrega(ent, aufnr, plan_iw37_por_ordem(silent))
    real = int(ent.get("realizado_min") or 0)
    return (real / plan) if plan > 0 else ent.get("aderencia")


def detalhe_ordem(ordem: str, silent: bool = True) -> dict | None:
    """Reúne o MÁXIMO de informação de uma ordem para o modal de detalhe (B9).

    Cabeçalho (sap_backlog) + totais/aderência + operações (planejado×realizado por VORNR) +
    atribuições locais (todas as semanas) + histórico de replanejamento. None se Mongo cair.
    """
    base = montar_ordens(silent)
    if base is None:
        return None
    o = base["ordens"].get(str(ordem))
    if o is None:
        # ordem fora do backlog de abertas (concluída/cancelada — BR-20): o cabeçalho não vem mais
        # do sap_backlog; recupera do snapshot `entrega.cabecalho` congelado na atribuição (B29).
        o = {"ordem": str(ordem), "planejado_min": 0, "realizado_min": 0,
             "aderencia": None, "executores": [], "status_sap": None,
             "disciplina": "NaoClassificado"}
        _ca = _coll_atrib(silent)
        _adoc = _ca.find_one({"ordem": str(ordem), "entrega": {"$ne": None}}) if _ca is not None else None
        _ent = (_adoc or {}).get("entrega") or {}
        _cab = _ent.get("cabecalho") or {}
        if _ent:
            o.update({
                "descricao": _cab.get("descricao") or o.get("descricao"),
                "categoria": _cab.get("categoria"),
                "disciplina": _cab.get("disciplina") or o["disciplina"],
                "local_instalacao": _cab.get("local_instalacao"),
                "centro_operacao_0010": _cab.get("centro_operacao_0010"),
                "status_sap": _ent.get("status_sistema") or _ent.get("status_sap_raw"),
                "status_usuario": _ent.get("status_usuario"),
                # B54: o congelado veio do IW47 (só operações apontadas) — recompõe pelo IW37, que
                # ainda traz a ordem inteira. Sem isto o modal exibia "Planejado 15min" no topo
                # enquanto listava, logo abaixo, as 8 operações que somam 155min.
                "planejado_min": planejado_de_entrega(_ent, str(ordem), plan_iw37_por_ordem(silent)),
                "realizado_min": _ent.get("realizado_min") or 0,
                "aderencia": _aderencia_recomposta(_ent, str(ordem), silent),
                # terminal "feito" = encerrada (CERR); "concluida" é legado do status de sistema
                "_entregue": _ent.get("status_saida") in ("encerrada", "concluida"),
            })

    # operações: une planejado×realizado por VORNR
    cp = get_mongo_connection(COLL_PLAN, silent=silent)
    cr = get_mongo_connection(COLL_REAL, silent=silent)
    ops: dict[str, dict] = {}
    if cp is not None:
        for d in cp.find({"ordem": str(ordem), "_id": {"$ne": META_ID}}):
            e = ops.setdefault(d.get("operacao", ""), {})
            e["plan"] = d.get("planejado_min")
            e["centro"] = d.get("centro_planejado")
            e["texto"] = d.get("texto_op")
    if cr is not None:
        for d in cr.find({"ordem": str(ordem), "_id": {"$ne": META_ID}}):
            op = ops.setdefault(d.get("operacao", ""), {})
            op["real"] = d.get("realizado_min")
            op["executores"] = d.get("executores") or []
            op["status"] = d.get("status_sap")
    # B54: o realizado é RATEADO entre as operações, proporcional ao planejado de cada uma.
    # O manutentor não aponta operação a operação — lança o tempo todo numa só (em geral a 0010),
    # e esse tempo cobre a ordem inteira. Mostrar o número bruto fazia a operação apontada exibir
    # 2.920% e as demais 0%, como se o serviço não tivesse sido feito nelas. Proporcional (e não
    # em partes iguais) porque uma operação de 3h20 ao lado de onze de 5 min voltaria a estourar:
    # a fatia igual daria 243% nas pequenas e 6% na grande. Assim toda operação exibe a aderência
    # da ordem, que é o único número que de fato foi medido.
    plan_total = sum(int((ops[v].get("plan") or 0)) for v in ops)
    real_total = sum(int((ops[v].get("real") or 0)) for v in ops)
    operacoes = []
    for vornr in sorted(ops):
        e = ops[vornr]
        plan = e.get("plan") or 0
        real = (real_total * plan / plan_total) if plan_total > 0 else 0
        operacoes.append({
            "operacao": vornr, "texto": e.get("texto"),
            "planejado_min": plan, "realizado_min": round(real),
            "realizado_rateado": True,
            "aderencia": (real / plan) if plan > 0 else None,
            "centro": e.get("centro"),
            "executores": nomes_executores(e.get("executores"), silent),  # PERNR → nome (SP-06.6)
            "status": e.get("status"),
        })

    # atribuições locais (todas as semanas) + nome do técnico
    nomes = {str(f.get("_id")): f.get("nome") for f in _carregar_funcionarios(silent)}
    atribs = []
    ca = _coll_atrib(silent)
    if ca is not None:
        for a in ca.find({"ordem": str(ordem)}):
            atribs.append({
                "semana": a.get("semana"), "dia": a.get("dia"),
                "funcionario": nomes.get(str(a.get("funcionario_id")), str(a.get("funcionario_id"))),
                "parcela_min": a.get("parcela_min"),
            })

    # histórico de replanejamento
    replanej = []
    crep = get_mongo_connection(COLL_REPLAN, silent=silent)
    if crep is not None:
        for r in crep.find({"ordem": str(ordem)}).sort("em", -1):
            replanej.append({"tipo": r.get("tipo"), "categoria": r.get("categoria"),
                             "texto": r.get("texto"), "por": r.get("por"), "em": r.get("em"),
                             "semana": r.get("semana")})

    return {
        "ordem": str(ordem),
        "header": {
            "descricao": o.get("descricao"), "categoria": o.get("categoria"),
            "disciplina": o.get("disciplina"), "local_instalacao": o.get("local_instalacao"),
            "linha_nome": o.get("linha_nome"), "data_criacao": o.get("data_criacao"),
            "data_inicio": o.get("data_inicio"),
            "status_sap": o.get("status_sap"),
            "status_label": status_label(o.get("status_sap"), silent),
            "status_usuario": o.get("status_usuario"),
            "status_usuario_label": status_usuario_label(o.get("status_usuario"), silent=silent),
            "pendente": not (o.get("_entregue")
                             or (o.get("status_sap") and o.get("status_sap") in _status_concluidos(silent))),
        },
        "totais": {
            "planejado_min": o.get("planejado_min"), "realizado_min": o.get("realizado_min"),
            "aderencia": o.get("aderencia"),
            "executores": nomes_executores(o.get("executores"), silent),  # PERNR → nome (SP-06.6)
            "idade_dias": _idade_dias(o, _agora_brt()),
            "carry_over": carry_over(str(ordem), semana_atual(), silent),
        },
        "operacoes": operacoes,
        "atribuicoes": atribs,
        "replanejamentos": replanej,
    }


def _status_concluidos(silent: bool = True) -> set:
    """Conjunto de códigos do SAP mapeados como 'concluída' (de/para hh_status_mapa). 1 query."""
    c = get_mongo_connection(COLL_STATUS, silent=silent)
    if c is None:
        return set()
    return {d["codigo_sap"] for d in c.find({"concluida": True}, {"codigo_sap": 1})}


def listar_motivos(silent: bool = True) -> list[str]:
    """Categorias de motivo de replanejamento. Semeia o default na 1ª vez (BR-16)."""
    c = get_mongo_connection(COLL_MOTIVOS, silent=silent)
    if c is None:
        return list(MOTIVOS_DEFAULT)
    docs = list(c.find({"_id": {"$ne": META_ID}}).sort("ordem", 1))
    if not docs:
        c.insert_many([{"texto": m, "ordem": i} for i, m in enumerate(MOTIVOS_DEFAULT)])
        return list(MOTIVOS_DEFAULT)
    return [d["texto"] for d in docs]


def registrar_replanejamento(semana: str, ordem: str, tipo: str, de, para,
                             categoria: str | None, texto: str | None, por: str,
                             silent: bool = True) -> dict:
    """Registra a auditoria de um replanejamento (BR-16). Estado local; nunca vai ao SAP.

    `tipo` ∈ ALTERACOES_COM_MOTIVO. Exige categoria; 'Outro' exige texto. Retorna {ok, motivo}.
    """
    if tipo in ALTERACOES_COM_MOTIVO:
        if not categoria:
            return {"ok": False, "motivo": "categoria de motivo obrigatória"}
        if categoria == "Outro" and not (texto or "").strip():
            return {"ok": False, "motivo": "motivo 'Outro' exige texto"}
    c = get_mongo_connection(COLL_REPLAN, silent=silent)
    if c is None:
        return {"ok": False, "motivo": "banco indisponível"}
    c.insert_one({
        "semana": semana, "ordem": str(ordem), "tipo": tipo,
        "de": de, "para": para, "categoria": categoria, "texto": texto,
        "por": por, "em": _agora_brt(),
    })
    return {"ok": True, "motivo": "registrado"}


# ---- mão de obra da semana p/ o relatório diário (KPIReport-v2 BR-11/12/13, DS-14) ----

def semana_mao_de_obra(ref_day, silent: bool = True) -> dict:
    """Disponível × planejado × executado por dia útil (seg–sex) da semana que contém `ref_day`.

    Base do bloco "Mão de obra da semana" do relatório diário (KPIReport-v2). `ref_day` é o **dia
    avaliado do relatório** — a mesma âncora dos blocos de "últimas 24h": o DatePicker do relatório
    (default = ontem). A semana ISO que contém `ref_day` é a semana de referência. Não há recuo
    automático: se o dia default (ontem) não teve produção, o usuário escolhe outro dia no
    DatePicker (mesma UX dos demais blocos) — BR-11.

    - Disponível/planejado por dia reusam `resumo_dias_cabecalho` (a mesma conta do quadro; ADM
      fora, líquido de folga).
    - Executado por dia = Σ `realizado_por_dia` (ISDD) dos docs de `sap_hh_realizado` cujas datas
      caem na semana (BR-12/13). Preenche só até o dia avaliado (`ref_day`) inclusive; dias
      posteriores (hoje/futuro) e dias sem apontamento → `None` (nunca 0 — SP-22).

    Retorna `{"semana": "YYYY-Www", "sem_dados": bool, "dias": [ {data, dow, disponivel_h,
    planejado_h, pct_plan, executado_h, aderencia} ]}` (5 dias úteis). `sem_dados=True` quando o
    Mongo do quadro está indisponível — o relatório renderiza a nota e não quebra (SP-19).
    """
    if isinstance(ref_day, datetime):
        ref_date = ref_day.date()
    else:
        ref_date = ref_day  # já é date
    semana = iso_semana(ref_day if isinstance(ref_day, datetime)
                        else datetime(ref_date.year, ref_date.month, ref_date.day))

    base = montar_ordens(silent)
    if base is None:
        return {"semana": semana, "sem_dados": True, "dias": []}
    ordens = base["ordens"]
    atribuicoes = listar_atribuicoes(semana, silent)
    funcionarios = funcionarios_da_semana(_carregar_funcionarios(silent), semana)   # BR-25
    assignments = _assignments_por_func(funcionarios, silent)
    cfg_cap = carregar_config_capacidade(silent)

    # disponível × planejado por dia — reuso do cálculo do quadro (fábrica, ADM fora, seg–sex).
    # `ordens_cap` (B45) preserva o planejado das ordens já fechadas, cobrindo esta semana e a
    # anterior (usada no Δ%); sem isto o relatório diário subestima o planejado das ordens fechadas.
    atrib_ant = listar_atribuicoes(semana_shift(semana, -1), silent)
    plan_iw37 = plan_iw37_por_ordem(silent)
    ordens_cap = overlay_entrega(ordens, atribuicoes + atrib_ant, plan_iw37)
    planejado_dia = planejado_por_dia(atribuicoes, ordens_cap)
    disponivel_dia = disponivel_por_dia(funcionarios, assignments, cfg_cap["disponivel_min"],
                                     semana, atribuicoes)
    planejado_ant = planejado_por_dia(atrib_ant, ordens_cap)
    resumo = resumo_dias_cabecalho(planejado_dia, disponivel_dia, planejado_ant)

    # executado por dia — Σ realizado_por_dia (ISDD) das operações, mapeado aos dias da semana.
    # O apontamento não carrega turno; o realizado é de ordens de manutenção (ADM não aponta
    # ordem), então somar tudo = fábrica de manutenção (coerente com BR-12).
    datas = datas_da_semana(semana)                       # 7 datetimes seg→dom (meia-noite)
    data_str_por_dia = {d.strftime("%Y-%m-%d"): i for i, d in enumerate(datas)}
    exec_min = {i: 0 for i in range(7)}
    snap = _carregar_snapshot(COLL_REAL, silent)
    for doc in (snap or {}).get("docs", []):
        for data_str, mins in (doc.get("realizado_por_dia") or {}).items():
            dia = data_str_por_dia.get(data_str)
            if dia is not None:
                exec_min[dia] += int(mins or 0)

    dias = _dias_mao_de_obra(resumo, exec_min, datas, ref_date)
    return {"semana": semana, "sem_dados": False, "dias": dias}


def _dias_mao_de_obra(resumo: dict, exec_min: dict, datas: list, ref_date) -> list:
    """Monta as 5 linhas úteis (seg–sex) da visão de mão de obra. Puro/testável (BR-12/SP-22).

    Corte de borda do executado (mesma âncora dos blocos 24h do relatório): o executado de um dia
    só aparece se o dia (a) é **≤ o dia avaliado** (`ref_date` = DatePicker do relatório, default
    ontem) e (b) tem apontamento (`exec_min > 0`). Dias posteriores ao avaliado (hoje/futuro) e
    dias sem apontamento → `executado_h`/`aderencia` = `None` (nunca 0). `pct_plan` = planejado ÷
    disponível (BR-11); `aderencia` = executado ÷ planejado (BR-12)."""
    dias = []
    for i in range(5):
        r = resumo.get(i, {})
        disp_min = r.get("disponivel")
        plan_min = int(r.get("programado") or 0)
        data_i = datas[i].date()
        if data_i <= ref_date and exec_min.get(i, 0) > 0:
            exec_h = round(exec_min[i] / 60, 1)
            ader = (exec_min[i] / plan_min) if plan_min > 0 else None
        else:
            exec_h = None
            ader = None
        dias.append({
            "data": data_i.strftime("%Y-%m-%d"),
            "dow": i,
            "disponivel_h": round(disp_min / 60, 1) if disp_min else None,
            "planejado_h": round(plan_min / 60, 1),
            "pct_plan": r.get("pct_programado"),
            "executado_h": exec_h,
            "aderencia": ader,
        })
    return dias
