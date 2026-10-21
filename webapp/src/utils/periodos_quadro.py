"""Mão de obra temporária — períodos de presença no quadro semanal (GantManagement BR-25 / DS-18).

Módulo PURO (sem Mongo, sem Dash) para não criar import circular entre `gantt_db` e `hh_data`.

Modelo no documento do funcionário (`gantt_employees`):
  - `temporario`: bool (ausente = False)
  - `periodos_quadro`: [{"de": "YYYY-Www"|None, "ate": "YYYY-Www"|None}] (ausente = [])
    `de=None` = desde sempre; `ate=None` = sem fim.

Regra de leitura (`conta_na_semana`):
  1. inativo → não conta;
  2. há períodos → conta se a semana cai em algum;
  3. sem períodos → conta se NÃO for temporário (todos os funcionários atuais).

Períodos que já valeram nunca são apagados (BR-25 itens 5, 7, 8, 10); só se descarta período
que ainda não começou.
"""
from datetime import date, timedelta


def _parse(semana: str) -> tuple[int, int]:
    y, w = semana.split("-W")
    return int(y), int(w)


def semana_shift(semana: str, delta: int) -> str:
    """Semana ISO deslocada `delta` semanas (mesmo cálculo de `hh_data.semana_shift`)."""
    y, w = _parse(semana)
    d = date.fromisocalendar(y, w, 1) + timedelta(weeks=delta)
    yy, ww, _ = d.isocalendar()
    return f"{yy}-W{ww:02d}"


def semana_cmp(a: str, b: str) -> int:
    """Compara duas semanas 'YYYY-Www': -1 / 0 / 1."""
    pa, pb = _parse(a), _parse(b)
    return (pa > pb) - (pa < pb)


def _dentro(semana: str, p: dict) -> bool:
    de, ate = p.get("de"), p.get("ate")
    if de is not None and semana_cmp(semana, de) < 0:
        return False
    if ate is not None and semana_cmp(semana, ate) > 0:
        return False
    return True


def conta_na_semana(func: dict, semana: str) -> bool:
    """True se o funcionário entra no quadro/disponível da semana (regra de leitura acima)."""
    if not func.get("ativo", True):
        return False
    periodos = func.get("periodos_quadro") or []
    if periodos:
        return any(_dentro(semana, p) for p in periodos)
    return not func.get("temporario", False)


def _key_de(p: dict):
    return (0, 0) if p.get("de") is None else _parse(p["de"])


def normalizar(periodos: list) -> list:
    """Ordena por início e funde períodos sobrepostos ou encostados (W42–W44 + W45–… → W42–…)."""
    ps = sorted((dict(p) for p in (periodos or [])), key=_key_de)
    out: list[dict] = []
    for p in ps:
        if out:
            ult = out[-1]
            if ult["ate"] is None:
                continue                      # último já é aberto: engole o resto
            if p.get("de") is None or semana_cmp(p["de"], semana_shift(ult["ate"], 1)) <= 0:
                if p.get("ate") is None or semana_cmp(p["ate"], ult["ate"]) > 0:
                    ult["ate"] = p.get("ate")
                continue
        out.append({"de": p.get("de"), "ate": p.get("ate")})
    return out


def _fechar_abertos(periodos: list, ate: str) -> list:
    """Fecha períodos abertos em `ate`; descarta os que começariam depois (nunca valeram)."""
    out = []
    for p in periodos or []:
        de = p.get("de")
        if de is not None and semana_cmp(de, ate) > 0:
            continue
        if p.get("ate") is None or semana_cmp(p["ate"], ate) > 0:
            out.append({"de": de, "ate": ate})
        else:
            out.append({"de": de, "ate": p["ate"]})
    return out


def periodos_ao_marcar_temporario(periodos: list, semana_atual: str) -> list:
    """Fixo → temporário: sai do quadro a partir da semana atual; passado preservado (item 7).

    Sem períodos (fixo de sempre) → [{desde sempre, até semana anterior}].
    """
    anterior = semana_shift(semana_atual, -1)
    if not periodos:
        return [{"de": None, "ate": anterior}]
    return normalizar(_fechar_abertos(periodos, anterior))


def periodos_ao_desmarcar(periodos: list, semana_atual: str) -> list:
    """Temporário → fixo: conta da semana atual em diante; passado preservado (item 8 revisado)."""
    if not periodos:
        # temporário que nunca contou: passado segue sem horas; conta desta semana em diante
        return [{"de": semana_atual, "ate": None}]
    return normalizar(list(periodos) + [{"de": semana_atual, "ate": None}])


def periodos_ao_incluir(periodos: list, semana: str) -> list:
    """Inclusão manual pelo quadro: conta da `semana` em diante, até ser retirado (item 4)."""
    return normalizar(list(periodos or []) + [{"de": semana, "ate": None}])


def periodos_ao_retirar(periodos: list, semana: str) -> list:
    """Retirada pelo quadro: deixa de contar a partir da `semana`; anteriores preservadas (item 5)."""
    return normalizar(_fechar_abertos(periodos, semana_shift(semana, -1)))
