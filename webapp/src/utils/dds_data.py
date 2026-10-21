# src/utils/dds_data.py
#
# Dados do DDS (Diálogo Diário de Segurança) exibido no telão da Visão Geral
# da Manutenção:
#
#   · há quantos dias a planta está sem acidente (e qual o recorde);
#   · quantos minutos cada um dos 6 passos do guia deve durar.
#
# Duas coleções:
#   `dds_config`    — documento único (_id="default") com os minutos dos passos.
#   `dds_acidentes` — um documento por acidente registrado. A data do último
#                     acidente NÃO é um campo editável: é o maior `data` desta
#                     coleção. Guardar o histórico é o que permite mostrar o
#                     recorde no telão e deixar rastro de quem zerou o contador.

from datetime import date, datetime, time
import logging

from src.database.connection import get_mongo_connection

logger = logging.getLogger(__name__)

# Guia andragógico em 6 passos: 1+2+2+2+2+1 = 10 minutos.
PASSOS_PADRAO = [1, 2, 2, 2, 2, 1]

CONFIG_ID = "default"
COL_CONFIG = "dds_config"
COL_ACIDENTES = "dds_acidentes"


# --------------------------------------------------------------------- helpers
def _para_data(valor):
    """Converte o que veio do Mongo (datetime, date ou 'YYYY-MM-DD') em date."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str) and valor.strip():
        try:
            return datetime.strptime(valor.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _para_datetime(d):
    """Mongo não guarda `date` puro — normaliza para meia-noite do dia."""
    if isinstance(d, datetime):
        d = d.date()
    return datetime.combine(d, time.min)


# ---------------------------------------------------------------- minutos/passos
def get_dds_config():
    """Minutos de cada passo. Sem banco ou sem documento, devolve o padrão."""
    cfg = {"passos_min": list(PASSOS_PADRAO), "atualizado_em": None, "atualizado_por": None}
    try:
        doc = get_mongo_connection(COL_CONFIG).find_one({"_id": CONFIG_ID}) or {}
    except Exception as exc:                       # banco fora: o telão não pode cair
        logger.warning("DDS: config indisponível (%s) — usando padrão", exc)
        return cfg

    passos = doc.get("passos_min")
    if isinstance(passos, list) and len(passos) == 6:
        try:
            cfg["passos_min"] = [max(1, min(60, int(p))) for p in passos]
        except (TypeError, ValueError):
            logger.warning("DDS: passos_min inválido (%r) — usando padrão", passos)
    cfg["atualizado_em"] = doc.get("atualizado_em")
    cfg["atualizado_por"] = doc.get("atualizado_por")
    return cfg


def passos_minutos():
    """Minutos de cada um dos 6 passos, na ordem do guia."""
    return get_dds_config()["passos_min"]


def salvar_passos(passos, usuario=None):
    """Grava os minutos dos 6 passos. Devolve (ok, mensagem)."""
    if not isinstance(passos, (list, tuple)) or len(passos) != 6:
        return False, "São exatamente 6 passos."
    try:
        limpos = [int(p) for p in passos]
    except (TypeError, ValueError):
        return False, "Os minutos precisam ser números inteiros."
    if any(p < 1 or p > 60 for p in limpos):
        return False, "Cada passo vai de 1 a 60 minutos."

    try:
        get_mongo_connection(COL_CONFIG).update_one(
            {"_id": CONFIG_ID},
            {"$set": {"passos_min": limpos,
                      "atualizado_em": datetime.now(),
                      "atualizado_por": usuario}},
            upsert=True,
        )
    except Exception as exc:
        logger.error("DDS: falha ao salvar passos (%s)", exc)
        return False, "Não foi possível salvar — banco indisponível."
    return True, f"Tempos salvos: {' · '.join(str(p) for p in limpos)} min ({sum(limpos)} min no total)."


# -------------------------------------------------------------------- acidentes
def listar_acidentes(limite=50):
    """Acidentes registrados, do mais recente para o mais antigo."""
    try:
        cur = (get_mongo_connection(COL_ACIDENTES)
               .find({})
               .sort("data", -1)
               .limit(int(limite)))
        registros = []
        for d in cur:
            data = _para_data(d.get("data"))
            if data:
                registros.append({"id": str(d.get("_id")), "data": data,
                                  "observacao": d.get("observacao") or "",
                                  "registrado_por": d.get("registrado_por") or "",
                                  "registrado_em": d.get("registrado_em")})
        return registros
    except Exception as exc:
        logger.warning("DDS: histórico indisponível (%s)", exc)
        return []


def registrar_acidente(data, usuario=None, observacao=""):
    """Registra um acidente. Devolve (ok, mensagem).

    Zera o contador de dias do telão — por isso recusa data no futuro e data
    repetida, que só entram por engano de digitação.
    """
    d = _para_data(data)
    if not d:
        return False, "Informe a data do acidente."
    if d > date.today():
        return False, "A data não pode estar no futuro."

    try:
        col = get_mongo_connection(COL_ACIDENTES)
        if col.find_one({"data": _para_datetime(d)}):
            return False, f"Já existe um acidente registrado em {d.strftime('%d/%m/%Y')}."
        col.insert_one({"data": _para_datetime(d),
                        "observacao": (observacao or "").strip(),
                        "registrado_por": usuario,
                        "registrado_em": datetime.now()})
    except Exception as exc:
        logger.error("DDS: falha ao registrar acidente (%s)", exc)
        return False, "Não foi possível registrar — banco indisponível."
    return True, f"Acidente de {d.strftime('%d/%m/%Y')} registrado. O contador do telão foi zerado."


def remover_acidente(registro_id):
    """Apaga um registro (cadastro errado). Devolve (ok, mensagem)."""
    try:
        from bson import ObjectId
        res = get_mongo_connection(COL_ACIDENTES).delete_one({"_id": ObjectId(registro_id)})
    except Exception as exc:
        logger.error("DDS: falha ao remover acidente (%s)", exc)
        return False, "Não foi possível remover o registro."
    if not res.deleted_count:
        return False, "Registro não encontrado."
    return True, "Registro removido. O contador do telão foi recalculado."


def ultimo_acidente():
    """Data do acidente mais recente, ou None se não houver histórico."""
    registros = listar_acidentes(limite=1)
    return registros[0]["data"] if registros else None


def dias_sem_acidente(hoje=None):
    """Dias inteiros desde o último acidente. None quando não há histórico.

    Acidente ontem → 1. Data no futuro (erro de cadastro) devolve 0 em vez de
    número negativo — o telão nunca mostra dias negativos.
    """
    ultimo = ultimo_acidente()
    if not ultimo:
        return None
    return max(0, ((hoje or date.today()) - ultimo).days)


def recorde_dias(hoje=None):
    """Maior período sem acidente já alcançado, em dias.

    Considera também o período em curso: se a planta está em 90 dias e o melhor
    anterior foi 87, o recorde é 90 — está sendo batido agora.

    Devolve (recorde, batendo_agora). Sem histórico: (None, False).
    """
    registros = listar_acidentes(limite=1000)
    if not registros:
        return None, False

    hoje = hoje or date.today()
    datas = sorted(r["data"] for r in registros)
    intervalos = [(datas[i + 1] - datas[i]).days for i in range(len(datas) - 1)]
    corrente = max(0, (hoje - datas[-1]).days)

    anterior = max(intervalos) if intervalos else 0
    if corrente >= anterior:
        return corrente, corrente > anterior
    return anterior, False
