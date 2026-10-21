# src/utils/failure_events.py

"""
Agregação de apontamentos de `ZPP_Paradas` em **eventos de falha**.

Motivação (BR-AF2-01): um apontamento SAP **não** é uma parada no sentido da
análise A3. A quebra do motor da cisalha da LCL-4,5 em 22/06/2026 chegou ao
SAP como 4 apontamentos (168+118+180+266 = 732 min), em 2 ordens distintas,
entrecortados por refeição (102N) e DDS (105). O A3 correspondente trata o
conjunto como **um** evento. Este módulo reconstrói esse evento.

Agrupamento (BR-AF2-02): a chave é `(equipamento, dia, causa, relato)`. Não há
heurística de contiguidade temporal — o relato do operador é o que identifica a
falha, e apontamentos do mesmo dia com o mesmo relato são a mesma falha, tenham
o intervalo que tiverem entre si.

Duração (BR-AF2-03): `duration_min` é a **fonte única**. `fim_real_hora` não é
lido; o fim é derivado de `inicio + duration_min`. As horas de `inicio_real_hora`
servem **apenas para exibição** (início do evento = a mais cedo do grupo).

A lógica de agrupamento é **pura** (`agrupar_eventos`) e não depende de pandas
nem de Mongo — é testável com documentos crus. Os leitores (`buscar_eventos`,
`buscar_evento`) são cascas finas por cima de `get_mongo_connection`.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Iterable, Optional
import hashlib
import re
import unicodedata

from src.utils.equipment_names import EQUIPAMENTO_NOMES

# Separador da chave do evento. Não ocorre em `centro_de_trabalho` nem em
# `causa_do_desvio`, então a chave é fatiável por split simples.
_SEP = "_"

# Faixas de duração para o filtro da página. Os limites são fechados à direita:
# 25 min cai em "até 25", 60 min cai em "de 25 a 60".
FAIXA_ATE_25 = "ate25"
FAIXA_25_A_60 = "de25a60"
FAIXA_ACIMA_60 = "acima60"

FAIXAS_DURACAO = [
    {"value": FAIXA_ATE_25, "label": "≤ 25 min"},
    {"value": FAIXA_25_A_60, "label": "> 25 e ≤ 60 min"},
    {"value": FAIXA_ACIMA_60, "label": "> 60 min"},
]

_TODAS_FAIXAS = [f["value"] for f in FAIXAS_DURACAO]


def faixa_duracao(minutos: Any) -> Optional[str]:
    """Classifica uma duração em minutos numa das três faixas do filtro.

    Retorna None para valores ausentes ou não numéricos — o chamador decide se
    isso entra ou sai do resultado.
    """
    if minutos is None:
        return None
    try:
        d = float(minutos)
    except (TypeError, ValueError):
        return None
    if d <= 25:
        return FAIXA_ATE_25
    if d <= 60:
        return FAIXA_25_A_60
    return FAIXA_ACIMA_60


def faixas_ativas(faixas: Optional[list[str]]) -> list[str]:
    """Normaliza a seleção do filtro de duração; vazio/None = todas.

    Segue a convenção do filtro de códigos de avaria da mesma página, onde nada
    selecionado significa "sem restrição" em vez de "não mostrar nada".
    """
    if not faixas:
        return list(_TODAS_FAIXAS)
    validas = [f for f in faixas if f in _TODAS_FAIXAS]
    return validas or list(_TODAS_FAIXAS)


def duracao_na_faixa(minutos: Any, faixas: Optional[list[str]]) -> bool:
    """True se a duração pertence a alguma das faixas selecionadas."""
    ativas = faixas_ativas(faixas)
    if len(ativas) == len(_TODAS_FAIXAS):
        return True  # sem restrição — evita descartar duração inválida à toa
    f = faixa_duracao(minutos)
    return f is not None and f in ativas


def anos_disponiveis(hoje: Optional[datetime] = None, janela: int = 3) -> list[int]:
    """Anos oferecidos no filtro, do mais antigo ao mais recente.

    Derivado da data corrente em vez de uma lista fixa no código: a lista
    hardcoded [2024, 2025, 2026] envelhecia sozinha e passava a esconder o ano
    novo em 1º de janeiro. O padrão da página é `anos_disponiveis()[-1]`.
    """
    ano = (hoje or datetime.now()).year
    return list(range(ano - janela + 1, ano + 1))


def ano_padrao(hoje: Optional[datetime] = None) -> int:
    """Ano pré-selecionado no filtro: sempre o mais recente."""
    return anos_disponiveis(hoje)[-1]


GATILHO_MODO_ACIMA = "acima"
GATILHO_MODO_TODAS = "todas"


def exibir_todas_as_paradas(filtros: Optional[dict]) -> bool:
    """Lê o modo do filtro de gatilho. Ausente ou inválido → False (só acima).

    Enum de string, e não booleano, de propósito: `store-af-filters` é
    persistido em `local`, então os filtros já gravados no navegador **não têm**
    esta chave. Com um bool, o ausente viraria `None` → falsy → "mostrar tudo",
    invertendo silenciosamente o padrão para quem já usou a página.
    """
    if not filtros:
        return False
    return filtros.get("gatilho") == GATILHO_MODO_TODAS


def ano_valido(ano: Any, hoje: Optional[datetime] = None) -> int:
    """Ajusta um ano persistido à lista de anos oferecida hoje.

    Necessário porque o filtro é gravado em `local` (permanente) mas a lista de
    anos é móvel: um ano salvo sai da lista na virada do ano. Sem o ajuste, o
    dropdown renderizaria vazio e mesmo assim continuaria filtrando pelo ano
    antigo — o usuário veria um filtro em branco com dados de outro período.
    """
    disponiveis = anos_disponiveis(hoje)
    try:
        a = int(ano)
    except (TypeError, ValueError):
        return disponiveis[-1]
    return a if a in disponiveis else disponiveis[-1]


def _norm_texto(texto: Optional[str]) -> str:
    """Normaliza texto de apontamento para comparação (sem acento/caixa/espaço duplo).

    O texto de confirmação é digitado pelo operador e traz variação de caixa e
    acentuação para o mesmo evento (ex.: "quebra motor cisalaha 5019483").
    Retorna '' quando não há texto — o chamador decide o fallback.
    """
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def _hora_para_delta(hora: Optional[str]) -> Optional[timedelta]:
    """Converte 'HH:MM:SS' (formato de `inicio_real_hora`) em timedelta desde a meia-noite."""
    if not hora:
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", str(hora).strip())
    if not m:
        return None
    h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if h > 23 or mi > 59 or s > 59:
        return None
    return timedelta(hours=h, minutes=mi, seconds=s)


def _base_date(valor: Any) -> Optional[datetime]:
    """Extrai a data-base de `inicio_execucao`, que no Mongo vem como datetime à meia-noite."""
    if isinstance(valor, datetime):
        return datetime(valor.year, valor.month, valor.day)
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    return None


def normalizar_apontamento(doc: dict) -> Optional[dict]:
    """Converte um doc cru de `ZPP_Paradas` num apontamento com datetimes reais.

    `duration_min` é a fonte única da duração (BR-AF2-03): o fim é sempre
    `inicio + duration_min`, e `fim_real_hora` não é lido. Os dois caminhos
    concordam em 100% dos apontamentos de avaria do histórico, mas ter uma única
    fonte evita que uma divergência futura no SAP produza duas verdades.

    `inicio` combina `inicio_execucao` (data à meia-noite) com `inicio_real_hora`
    ("HH:MM:SS") e existe **só para exibição** — o agrupamento não depende dele.

    Retorna None sem data/hora de início ou sem `duration_min`.
    """
    base = _base_date(doc.get("inicio_execucao"))
    d_ini = _hora_para_delta(doc.get("inicio_real_hora"))
    if base is None or d_ini is None:
        return None

    duracao = doc.get("duration_min")
    if duracao is None:
        return None
    try:
        duracao = float(duracao)
    except (TypeError, ValueError):
        return None
    if duracao < 0:
        return None

    inicio = base + d_ini
    return {
        "equipamento": doc.get("centro_de_trabalho"),
        "ordem": doc.get("ordem"),
        "causa": doc.get("causa_do_desvio"),
        "dia": base.date(),
        "inicio": inicio,
        "fim": inicio + timedelta(minutes=duracao),
        "duracao_min": duracao,
        "descricao": doc.get("descricao") or "",
        "texto": doc.get("texto_de_confirmacao") or "",
    }


def _rotulo(apontamentos: list[dict]) -> str:
    """Rótulo do evento: primeiro texto de confirmação não vazio, senão a descrição SAP."""
    for a in apontamentos:
        if a["texto"].strip():
            return a["texto"].strip()
    for a in apontamentos:
        if a["descricao"].strip():
            return a["descricao"].strip()
    return ""


_HASH_LEN = 8


def _hash_relato(relato_norm: str) -> str:
    """Hash curto do relato normalizado, para caber na chave/URL.

    8 hex de sha1 = 4 bilhões de combinações. Uma colisão não daria só uma chave
    repetida: `buscar_evento` devolveria o primeiro match e o índice único em
    `parada_chave` juntaria duas falhas distintas na mesma análise. 6 já bastava
    no histórico atual, mas 8 é de graça.
    """
    return hashlib.sha1(relato_norm.encode("utf-8")).hexdigest()[:_HASH_LEN]


def montar_chave(equipamento: str, mes: date, causa: str, relato_norm: str) -> str:
    """Chave estável do evento **mensal**: `LONGI002_202606_201_a4c2d0ff`.

    O carimbo é o **mês** (`YYYYMM`, 6 dígitos): a parada vale para o mês inteiro
    (BR-AF2-02), então todas as ocorrências da mesma falha no mês compartilham a
    chave. `ZPP_Paradas` não expõe `_id` em nenhum reader do projeto, então a
    identidade do evento é a própria chave de agrupamento. O relato entra como hash
    porque é texto livre do operador — não caberia numa URL.

    O hash **não** é reversível: `buscar_evento` reencontra o grupo reagrupando
    os apontamentos do **mês** e comparando a chave inteira.
    """
    if isinstance(mes, datetime):
        mes = mes.date()
    return f"{equipamento}{_SEP}{mes:%Y%m}{_SEP}{causa}{_SEP}{_hash_relato(relato_norm)}"


def parse_chave(chave: str) -> Optional[tuple[str, date, str, str]]:
    """Fatia a chave em (equipamento, mês, causa, hash_relato), ou None se malformada.

    O mês volta como `date` do 1º dia (ex.: 2026-06-01). Não reconstrói o relato — o
    hash é de mão única. O suficiente para montar a query do mês e reencontrar o
    evento.
    """
    if not chave:
        return None
    partes = str(chave).split(_SEP)
    if len(partes) != 4:
        return None
    equip, carimbo, causa, h = partes
    try:
        mes = datetime.strptime(carimbo, "%Y%m").date()
    except ValueError:
        return None
    if not equip or not causa or not h:
        return None
    return equip, mes, causa, h


def _primeiro_do_mes(d: date) -> date:
    """Primeiro dia do mês de `d` — o carimbo temporal do agrupamento MENSAL."""
    if isinstance(d, datetime):
        d = d.date()
    return date(d.year, d.month, 1)


def agrupar_eventos(docs: Iterable[dict]) -> list[dict]:
    """Agrupa apontamentos crus de `ZPP_Paradas` em eventos de falha **mensais**.

    Chave de agrupamento: `(equipamento, mês, causa, relato normalizado)` — BR-AF2-02.
    A **análise de falha vale para o mês inteiro**: se a mesma falha (mesmo
    equipamento/causa/relato) reincide em vários dias do mês, é **uma** parada só,
    com a duração **somando o mês**. A recorrência vira uma nova parada só no mês
    seguinte. Isso alinha o produto ao processo real (PCM não faz análise por dia) e
    faz o gatilho (BR-AF2-04) enxergar o **acumulado** do mês — 20 min × 15 dias = 300
    min disparam a análise, mesmo que nenhum dia isolado passe do gatilho.

    Sem heurística de contiguidade temporal — o relato identifica a falha. A quebra
    do motor da cisalha (22/06/2026), 4 apontamentos com o mesmo relato separados por
    refeição e DDS, entra num evento só.

    Apontamentos sem relato caem num balde por `(equipamento, mês, causa)`.

    Retorna eventos ordenados por início desc (mais recente primeiro).
    """
    apontamentos = [n for n in (normalizar_apontamento(d) for d in docs) if n]
    apontamentos = [a for a in apontamentos if a["equipamento"] and a["causa"]]

    grupos: dict[tuple, list[dict]] = {}
    for a in apontamentos:
        chave = (a["equipamento"], _primeiro_do_mes(a["dia"]), str(a["causa"]),
                 _norm_texto(a["texto"]))
        grupos.setdefault(chave, []).append(a)

    eventos = [_montar_evento(k, v) for k, v in grupos.items()]
    eventos.sort(key=lambda e: e["inicio"], reverse=True)
    return eventos


def _montar_evento(chave_grupo: tuple, apontamentos: list[dict]) -> dict:
    """Consolida os apontamentos de um grupo (mês) num único evento de falha.

    Além da soma do mês, monta `por_dia` (a composição diária) e `n_dias` — é o que
    o drill usa para mostrar se a parada foi **uma grande** ou a **soma de várias
    pequenas** ao longo do mês.
    """
    equipamento, mes, causa, relato_norm = chave_grupo
    apontamentos = sorted(apontamentos, key=lambda a: a["inicio"])
    duracao = sum(a["duracao_min"] for a in apontamentos)
    ordens = sorted({a["ordem"] for a in apontamentos if a["ordem"] is not None},
                    key=lambda o: str(o))
    # Composição diária (drill "1 grande vs várias pequenas").
    por_dia_map: dict = {}
    for a in apontamentos:
        d = a["dia"]
        slot = por_dia_map.setdefault(d, {"duracao_min": 0, "n_apontamentos": 0})
        slot["duracao_min"] += a["duracao_min"]
        slot["n_apontamentos"] += 1
    por_dia = [{"dia": d, **por_dia_map[d]} for d in sorted(por_dia_map)]
    return {
        "chave": montar_chave(equipamento, mes, causa, relato_norm),
        "equipamento": equipamento,
        "causa": causa,
        "mes": mes,  # date do 1º dia do mês — o carimbo da parada mensal
        "rotulo": _rotulo(apontamentos),
        # Início e fim são só exibição, derivados das horas dos apontamentos do mês.
        "inicio": min(a["inicio"] for a in apontamentos),
        "fim": max(a["fim"] for a in apontamentos),
        # Soma dos apontamentos do mês — NÃO (fim - inicio), que incluiria as pausas
        # operacionais (refeição, DDS) em que a linha não estava em avaria.
        "duracao_min": duracao,
        "n_apontamentos": len(apontamentos),
        "n_dias": len(por_dia_map),
        "por_dia": por_dia,
        "ordens": ordens,
        "apontamentos": apontamentos,
    }


def nome_equipamento(equipamento: str) -> str:
    """Nome de exibição do equipamento (LONGI002 → LCL-4,5), com fallback pro código.

    Para exibir, cair no código é aceitável. Para consultar gatilho, não — ver
    `_nome_para_gatilho`.
    """
    return EQUIPAMENTO_NOMES.get(equipamento, equipamento)


# ---------------------------------------------------------------------------
# Gatilhos de duração (BR-AF2-06)
# ---------------------------------------------------------------------------

def carregar_gatilho(equipamento: str, gatilhos: Optional[dict[str, int]] = None) -> int:
    """Gatilho (minutos) do equipamento, vindo do cadastro da indicators-v2.

    Delega ao cadastro existente (`utils/breakdown_thresholds`). A tradução de
    código para nome é necessária porque a collection é chaveada pelo **nome
    amigável** ("LCL-4,5"), enquanto `ZPP_Paradas` traz o código ("LONGI002").

    `gatilhos` pré-resolvido torna a função pura e evita reler o cadastro por
    evento — ver `filtrar_por_gatilho`.

    Equipamento sem nome amigável conhecido é logado, e não silenciado: cair no
    default por causa de um mapa incompleto some com eventos da tela sem aviso
    (SOLDA001 receberia 200 em vez de 120).
    """
    from src.utils.breakdown_thresholds import DEFAULT_THRESHOLD_MIN, get_threshold

    nome = _nome_para_gatilho(equipamento)
    if nome is None:
        print(f"[failure_events] equipamento {equipamento!r} sem nome amigável — "
              f"usando gatilho default ({DEFAULT_THRESHOLD_MIN} min)")
        return DEFAULT_THRESHOLD_MIN
    try:
        if gatilhos is not None:
            return int(gatilhos.get(nome, DEFAULT_THRESHOLD_MIN))
        return int(get_threshold(nome))
    except Exception as e:
        print(f"[failure_events] falha ao ler gatilho de {equipamento}: {e}")
        return DEFAULT_THRESHOLD_MIN


def _nome_para_gatilho(equipamento: str) -> Optional[str]:
    """Nome amigável para consultar o cadastro, ou None se o mapa não conhece o código.

    Diferente de `nome_equipamento`, que cai para o próprio código: aqui um
    fallback silencioso viraria gatilho errado (SOLDA001 pegaria 200 em vez de
    120, sumindo com eventos da tela), então devolve None e o chamador loga.
    """
    if not equipamento:
        return None
    return EQUIPAMENTO_NOMES.get(equipamento)


def evento_atinge_gatilho(evento: dict, gatilhos: Optional[dict[str, int]] = None) -> bool:
    """True se a duração agregada do evento atinge o gatilho do seu equipamento.

    Comparação `>=` — a única semântica documentada no projeto para gatilho
    (`envio_email/03-spec.md`: "envia se duracao_min ≥ gatilho") e a mesma que a
    indicators-v2 usa para pintar a célula.

    Avaliado sobre a duração do **evento agregado**, não de cada apontamento: uma
    falha de 77 min partida em dois apontamentos de ~38 min continua sendo uma
    falha de 77 min.
    """
    gatilho = carregar_gatilho(evento.get("equipamento") or "", gatilhos)
    try:
        return float(evento.get("duracao_min") or 0) >= gatilho
    except (TypeError, ValueError):
        return False


def _cadastro_de_gatilhos() -> dict[str, int]:
    """Lê o cadastro inteiro de uma vez. {} se o Mongo estiver fora."""
    from src.utils.breakdown_thresholds import get_all_thresholds

    try:
        return get_all_thresholds()
    except Exception as e:
        print(f"[failure_events] falha ao carregar cadastro de gatilhos: {e}")
        return {}


def anotar_gatilhos(eventos: list[dict]) -> list[dict]:
    """Anota `gatilho_min` em cada evento, sem filtrar nada.

    Resolve o cadastro **uma vez**: `get_threshold` por evento consultaria o
    cache centenas de vezes e poderia atravessar a expiração de 60s no meio do
    loop, misturando duas gerações de gatilho no mesmo render.
    """
    gatilhos = _cadastro_de_gatilhos()
    for e in eventos:
        e["gatilho_min"] = carregar_gatilho(e.get("equipamento") or "", gatilhos)
    return eventos


def filtrar_por_gatilho(eventos: list[dict]) -> list[dict]:
    """Mantém só os eventos que atingem o gatilho do seu equipamento."""
    gatilhos = _cadastro_de_gatilhos()
    saida = []
    for e in eventos:
        e["gatilho_min"] = carregar_gatilho(e.get("equipamento") or "", gatilhos)
        if evento_atinge_gatilho(e, gatilhos):
            saida.append(e)
    return saida


def titulo_sugerido(evento: dict) -> str:
    """Título inicial da análise: usa o relato do operador quando houver, senão o equipamento."""
    rotulo = (evento.get("rotulo") or "").strip()
    equip = nome_equipamento(evento.get("equipamento") or "")
    if rotulo:
        return rotulo[:120]
    return f"Análise de falha — {equip}"


def texto_no_raiz(evento: dict) -> str:
    """Texto do nó raiz do diagrama: 'Parada da LCL-4,5 por 12 h 12 min'."""
    from src.utils.failure_tree import formatar_duracao

    equip = nome_equipamento(evento.get("equipamento") or "")
    return f"Parada da {equip} por {formatar_duracao(evento.get('duracao_min') or 0)}"


# ---------------------------------------------------------------------------
# Leitores (Mongo) — cascas finas sobre a lógica pura acima
# ---------------------------------------------------------------------------

_PROJECAO = {
    "_id": 0,
    "centro_de_trabalho": 1,
    "ordem": 1,
    "inicio_execucao": 1,
    "inicio_real_hora": 1,   # só exibição — o fim vem de duration_min
    "causa_do_desvio": 1,
    "duration_min": 1,
    "descricao": 1,
    "texto_de_confirmacao": 1,
}


def _colecao():
    """Handle da collection `ZPP_Paradas`, ou None se o Mongo estiver indisponível."""
    from src.database.connection import get_mongo_connection
    from src.utils.zpp_kpi_calculator import ZPP_PARADAS_COLLECTION

    return get_mongo_connection(ZPP_PARADAS_COLLECTION)


def buscar_eventos(
    start_date: datetime,
    end_date: datetime,
    breakdown_codes: Optional[list[str]] = None,
    equipamentos: Optional[list[str]] = None,
    apenas_acima_do_gatilho: bool = True,
) -> list[dict]:
    """Busca apontamentos de avaria na janela `[start, end)` e devolve eventos agregados.

    Janela semi-aberta, seguindo a convenção dos readers (BR-05). Equipamentos de
    `KPI_FORCE_ZERO_EQUIPMENTS` são descartados, como nos demais indicadores.

    `apenas_acima_do_gatilho` (padrão True) devolve só os eventos que atingem o
    gatilho do equipamento — a fila de candidatos a análise A3. O filtro vive
    aqui, e não no callback, para que todo chamador herde a regra por padrão e
    precise pedir explicitamente para vê-la desligada.

    Retorna [] se o Mongo estiver offline — a página degrada em estado vazio.
    """
    from src.utils.zpp_kpi_calculator import BREAKDOWN_CODES, KPI_FORCE_ZERO_EQUIPMENTS

    col = _colecao()
    if col is None:
        return []

    codes = list(breakdown_codes) if breakdown_codes else list(BREAKDOWN_CODES)
    filtro: dict[str, Any] = {
        "_processed": True,
        "causa_do_desvio": {"$in": codes},
        "inicio_execucao": {"$gte": start_date, "$lt": end_date},
    }
    excluidos = set(KPI_FORCE_ZERO_EQUIPMENTS)
    if equipamentos:
        alvo = [e for e in equipamentos if e not in excluidos]
        if not alvo:
            return []
        filtro["centro_de_trabalho"] = {"$in": alvo}
    elif excluidos:
        filtro["centro_de_trabalho"] = {"$nin": sorted(excluidos)}

    try:
        docs = list(col.find(filtro, _PROJECAO))
    except Exception as e:  # Mongo fora do ar / query inválida
        print(f"[failure_events] falha ao buscar apontamentos: {e}")
        return []

    eventos = agrupar_eventos(docs)
    # `gatilho_min` é anotado nos dois caminhos: a listagem mostra o gatilho numa
    # coluna, para o usuário entender por que a parada está (ou não) ali.
    if apenas_acima_do_gatilho:
        return filtrar_por_gatilho(eventos)
    return anotar_gatilhos(eventos)


def buscar_evento(chave: str) -> Optional[dict]:
    """Recupera um único evento pela chave (`LONGI002_202606_201_a4c2d0ff`).

    O hash do relato não é reversível, então reagrupa os apontamentos do **mês** e
    casa a chave inteira. Como a chave é função total da chave de agrupamento, o
    reagrupamento reproduz o mesmo hash.

    **Nunca aplica o gatilho**: o filtro é uma regra da *listagem*, não da
    identidade. Se filtrasse aqui, um link direto (ou um F5 depois de abrir uma
    parada listada com "Todas") cairia em "parada não encontrada".
    """
    parsed = parse_chave(chave)
    if not parsed:
        return None
    equip, mes, causa, _hash = parsed

    col = _colecao()
    if col is None:
        return None

    inicio_mes = datetime(mes.year, mes.month, 1)
    fim_mes = datetime(mes.year + 1, 1, 1) if mes.month == 12 \
        else datetime(mes.year, mes.month + 1, 1)
    filtro = {
        "_processed": True,
        "centro_de_trabalho": equip,
        "causa_do_desvio": causa,
        # Janela do mês inteiro [1º dia, 1º dia do mês seguinte).
        "inicio_execucao": {"$gte": inicio_mes, "$lt": fim_mes},
    }
    try:
        docs = list(col.find(filtro, _PROJECAO))
    except Exception as e:
        print(f"[failure_events] falha ao buscar evento {chave}: {e}")
        return None

    for ev in agrupar_eventos(docs):
        if ev["chave"] == chave:
            ev["gatilho_min"] = carregar_gatilho(ev.get("equipamento") or "")
            return ev
    return None
