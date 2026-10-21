"""Loader de seed: CSVs reais da investigacao -> MongoDB (DS-02).

Le os CSVs reconciliados da investigacao read-only e grava nas duas coleches de
custo (DS-03), no **mesmo contrato** que a futura coleta SAP usara — so muda a
origem do arquivo (DS-01: Mongo e a fronteira). Idempotente: delete-por-janela por
`mes_referencia` antes de reinserir (BR-09), entao rodar 2x nao duplica.

Roda no **host** (os CSVs vivem em `.dev-docs/`, fora do container). Mongo local e
replica set anunciando `database:27017`; do host conecta-se com `directConnection=true`.

Uso:
    cd webapp/src
    python -m custos.seed_custos --mes 2026-02          # um mes
    python -m custos.seed_custos --all                  # todos os meses disponiveis
    python -m custos.seed_custos --all --dry-run        # so parse + reconciliacao, sem gravar

Caminhos/conexao configuraveis por env: CUSTOS_CSV_BASE, CUSTOS_MONGO_URI, CUSTOS_DB.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Permite rodar como script direto (`python seed_custos.py`) e como modulo
# (`python -m custos.seed_custos`): garante webapp/src no sys.path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custos.hierarquia import GRUPO_GERAL, conta_valida, grupo_da_conta  # noqa: E402
from custos.storage import (  # noqa: E402
    COLL_COMPONENTES,
    COLL_LANCAMENTOS,
    COLL_RESUMO,
    ensure_indexes,
)

logger = logging.getLogger("custos.seed")

# Defaults (host). Sobrescrevíveis por variavel de ambiente.
DEFAULT_CSV_BASE = "/home/rgust/projects/AMG/.dev-docs/development/Costs Management/export"
DEFAULT_MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
DEFAULT_DB = "Cluster-EasyTek"

DETALHE_FILENAME = "manutencao_detalhe_2026_completo.csv"
RESUMO_FILENAME = "dados_resumo_conta.csv"


# --------------------------------------------------------------------------- #
# Parsing BR
# --------------------------------------------------------------------------- #
def parse_valor_br(texto: str) -> float:
    """Converte valor em formato BR para float, tratando o sinal do SAP.

    Aceita milhar '.', decimal ',', e sinal **a direita** (formato SAP: '1.006,33-'
    = credito/estorno) ou a esquerda. Vazio/`None` -> 0.0.
    """
    if texto is None:
        return 0.0
    t = texto.strip()
    if not t:
        return 0.0
    negativo = False
    if t.endswith("-"):
        negativo, t = True, t[:-1].strip()
    elif t.startswith("-"):
        negativo, t = True, t[1:].strip()
    t = t.replace(".", "").replace(",", ".")
    valor = float(t)
    return -valor if negativo else valor


def parse_data_br(texto: str) -> datetime | None:
    """Converte data 'dd.mm.aaaa' (BUDAT) para datetime. Vazio/invalida -> None."""
    if not texto:
        return None
    t = texto.strip()
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", t):
        return None
    return datetime.strptime(t, "%d.%m.%Y")


def _abrir_csv(path: Path):
    """Abre CSV `;`-separado com BOM (utf-8-sig) e retorna lista de dicts."""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


# --------------------------------------------------------------------------- #
# Descoberta de pastas / mes
# --------------------------------------------------------------------------- #
def pasta_do_mes(base: Path, mes: str) -> Path:
    """Resolve a pasta `relatorio_manutencao_2026/mes_NN_*` para o mes 'YYYY-MM'.

    Levanta FileNotFoundError se a pasta nao existir.
    """
    nn = mes.split("-")[1]
    raiz = base / "relatorio_manutencao_2026"
    candidatos = sorted(raiz.glob(f"mes_{nn}_*"))
    if not candidatos:
        raise FileNotFoundError(f"pasta do mes {mes} nao encontrada em {raiz}")
    return candidatos[0]


def meses_disponiveis(base: Path) -> list[str]:
    """Lista os meses 'YYYY-MM' com pasta de relatorio (ordenados)."""
    raiz = base / "relatorio_manutencao_2026"
    meses = []
    for p in sorted(raiz.glob("mes_*")):
        m = re.match(r"mes_(\d{2})_", p.name)
        if m:
            meses.append(f"2026-{m.group(1)}")
    return meses


# --------------------------------------------------------------------------- #
# Construcao de documentos
# --------------------------------------------------------------------------- #
def construir_resumo(pasta: Path, mes: str, carregado_em: datetime) -> tuple[list[dict], float, float]:
    """Le `dados_resumo_conta.csv` e retorna (docs_resumo, geral_orcado, geral_exec).

    Pula a linha `GERAL` (vira `total_oficial_geral` em cada doc) e contas fora do
    GT340 (BR-01). `total_oficial_geral` = executado oficial do mes (linha GERAL) —
    base da reconciliacao DS-09.
    """
    linhas = _abrir_csv(pasta / RESUMO_FILENAME)
    geral_orcado = 0.0
    geral_exec = 0.0
    for ln in linhas:
        if (ln.get("conta") or "").strip().upper() == "GERAL":
            geral_orcado = parse_valor_br(ln.get("orcado_mes"))
            geral_exec = parse_valor_br(ln.get("executado"))
            break

    docs: list[dict] = []
    for ln in linhas:
        conta = (ln.get("conta") or "").strip()
        if not conta_valida(conta):
            continue  # descarta GERAL e a fantasma 33102104
        docs.append(
            {
                "mes_referencia": mes,
                "conta": conta,
                "conta_desc": (ln.get("descricao") or "").strip(),
                "subgrupo": grupo_da_conta(conta),
                "grupo": GRUPO_GERAL,
                "orcado": parse_valor_br(ln.get("orcado_mes")),
                "executado": parse_valor_br(ln.get("executado")),
                "total_oficial_geral": geral_exec,
                "fonte": "csv",
                "carregado_em": carregado_em,
            }
        )
    return docs, geral_orcado, geral_exec


# Catalogo de materiais de exemplo p/ os componentes sinteticos do seed (QA local).
# NAO e dado real — o item real de almoxarifado vem da MB25 pelo daemon (BR-15).
_CATALOGO_EXEMPLO = [
    ("16888", "MOTOR CC DMP180 137KW ABB", "PC"),
    ("1004273", "CORREIA 1180", "PC"),
    ("200145", "FILTRO DE AR INDUSTRIAL", "PC"),
    ("300221", "PARAFUSO ALLEN M12", "PC"),
    ("450012", "ROLAMENTO SKF 6205", "PC"),
    ("510098", "OLEO HIDRAULICO ISO 68", "L"),
]


# Requisitantes de exemplo p/ o seed (a coluna 'usuario' vem vazia no CSV da investigação).
# No cliente, o valor real é o USNAM do lançamento (quem lançou/baixou no SAP).
_REQUISITANTES = ["MASSIS", "JSILVA", "RCOSTA", "PALVES", "LFERREIRA"]


def _requisitante_sintetico(ln: dict) -> str:
    """Requisitante SINTÉTICO e determinístico p/ o seed (QA da coluna Requisitante)."""
    base = ((ln.get("no_documento") or "") + (ln.get("centro_custo") or "")).encode()
    return _REQUISITANTES[int(hashlib.md5(base).hexdigest()[:4], 16) % len(_REQUISITANTES)]


def _ordem_sintetica(ln: dict) -> str:
    """Ordem emissora SINTETICA e determinística p/ o seed (QA). O CSV da investigacao nao
    tem ordem (`PRTAU`); geramos uma estavel (hash) no formato de ordem PM (5xxxxxx) para
    exercitar a coluna 'Ordem' e casar com os componentes. Dado real vem do daemon SAP.
    """
    base = "|".join([(ln.get("no_documento") or ""), (ln.get("centro_custo") or ""),
                     (ln.get("data_lancamento") or ""), (ln.get("valor") or "")]).encode()
    n = int(hashlib.md5(base).hexdigest()[:6], 16) % 900000 + 5000000
    return str(n)


def construir_lancamentos(detalhe_path: Path, mes: str, carregado_em: datetime) -> list[dict]:
    """Le o detalhe completo e retorna os lancamentos do mes (contas validas), enriquecidos.

    Filtra por mes da data de lancamento (BUDAT). Descritor por cascata (BR-13): `texto_pedido`
    -> `texto_material` -> (liquidacao) descricao da ordem. Deriva `familia` (BR-13) e, nas
    linhas de liquidacao, SINTETIZA `ordem_emissora` (BR-14) — o CSV nao tem ordem; o dado real
    vem do daemon. Campos novos `fonte='csv'` (selo "dados de exemplo").
    """
    docs: list[dict] = []
    for ln in _abrir_csv(detalhe_path):
        conta = (ln.get("classe_custo") or "").strip()
        if not conta_valida(conta):
            continue
        data = parse_data_br(ln.get("data_lancamento"))
        if data is None or f"{data.year:04d}-{data.month:02d}" != mes:
            continue
        pedido = (ln.get("pedido_compra") or "").strip()
        texto_pedido = (ln.get("texto_pedido") or "").strip()
        texto_mat = (ln.get("texto_material") or "").strip()
        descritor = texto_pedido or texto_mat
        # Familia (BR-13): compra tem pedido; estoque tem texto de material; o resto (sem
        # pedido e sem material — os antigos "em branco") vira liquidacao no seed.
        if pedido:
            familia = "compra"
        elif texto_mat:
            familia = "estoque"
        else:
            familia = "liquidacao"
        ordem = ""
        if familia == "liquidacao":
            ordem = _ordem_sintetica(ln)
            if not descritor:
                descritor = f"ORDEM {ordem} — SERVICO DE MANUTENCAO (exemplo)"
        docs.append(
            {
                "mes_referencia": mes,
                "data_lancamento": data,
                "conta": conta,
                "centro_custo": (ln.get("centro_custo") or "").strip(),
                "valor": parse_valor_br(ln.get("valor")),
                "descritor": descritor,
                "familia": familia,                 # BR-13
                "ordem_emissora": ordem,            # BR-14 (sintetica no seed)
                "doc_ref": (ln.get("no_documento") or "").strip(),
                "material": "",
                "usuario": _requisitante_sintetico(ln),   # requisitante (exemplo no seed)
                "planta": "BR02",
                "tipo_doc": (ln.get("tipo_doc") or "").strip(),
                "no_documento": (ln.get("no_documento") or "").strip(),
                "pedido_compra": pedido,
                "fonte": "csv",
                "carregado_em": carregado_em,
            }
        )
    return docs


def construir_componentes(lanc_docs: list[dict], mes: str, carregado_em: datetime) -> list[dict]:
    """Componentes SINTETICOS por ordem de liquidacao (QA local do mini-modal, BR-15).

    1-3 itens por ordem, do catalogo de exemplo, determinísticos pela ordem. `fonte='csv'`.
    O dado real (item de almoxarifado baixado) vem da MB25 pelo daemon.
    """
    docs: list[dict] = []
    ordens = sorted({d["ordem_emissora"] for d in lanc_docs
                     if d.get("familia") == "liquidacao" and d.get("ordem_emissora")})
    for ordem in ordens:
        n_itens = int(ordem[-1]) % 3 + 1
        for i in range(n_itens):
            mat, desc, un = _CATALOGO_EXEMPLO[(int(ordem[-2:]) + i) % len(_CATALOGO_EXEMPLO)]
            docs.append(
                {
                    "ordem": ordem,
                    "mes_referencia": mes,
                    "material": mat,
                    "material_desc": desc,
                    "quantidade": float((int(ordem[-1]) + i) % 5 + 1),
                    "unidade": un,
                    "fonte": "csv",
                    "carregado_em": carregado_em,
                }
            )
    return docs


# --------------------------------------------------------------------------- #
# Carga de um mes
# --------------------------------------------------------------------------- #
def seed_mes(db, base: Path, mes: str, carregado_em: datetime, dry_run: bool = False) -> dict:
    """Carrega um mes (delete-por-janela + reinsert) e retorna relatorio de reconciliacao."""
    pasta = pasta_do_mes(base, mes)
    detalhe_path = base / DETALHE_FILENAME

    resumo_docs, geral_orcado, geral_exec = construir_resumo(pasta, mes, carregado_em)
    lanc_docs = construir_lancamentos(detalhe_path, mes, carregado_em)
    comp_docs = construir_componentes(lanc_docs, mes, carregado_em)

    soma_orcado = round(sum(d["orcado"] for d in resumo_docs), 2)
    soma_exec = round(sum(d["executado"] for d in resumo_docs), 2)
    soma_lanc = round(sum(d["valor"] for d in lanc_docs), 2)
    reconcilia = abs(soma_exec - round(geral_exec, 2)) < 0.005

    if not dry_run:
        db[COLL_RESUMO].delete_many({"mes_referencia": mes})
        db[COLL_LANCAMENTOS].delete_many({"mes_referencia": mes})
        db[COLL_COMPONENTES].delete_many({"mes_referencia": mes, "fonte": "csv"})
        if resumo_docs:
            db[COLL_RESUMO].insert_many(resumo_docs)
        if lanc_docs:
            db[COLL_LANCAMENTOS].insert_many(lanc_docs)
        if comp_docs:
            db[COLL_COMPONENTES].insert_many(comp_docs)

    return {
        "mes": mes,
        "contas": len(resumo_docs),
        "lancamentos": len(lanc_docs),
        "componentes": len(comp_docs),
        "soma_orcado": soma_orcado,
        "geral_orcado": round(geral_orcado, 2),
        "soma_exec": soma_exec,
        "geral_exec": round(geral_exec, 2),
        "soma_lancamentos": soma_lanc,
        "reconcilia": reconcilia,
    }


def _conectar(uri: str, db_name: str):
    """Abre conexao Mongo standalone (independente do webapp) e garante indices."""
    from pymongo import MongoClient

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    client.admin.command("ping")  # falha cedo se Mongo inacessivel
    ensure_indexes(db)
    return db


def main(argv: list[str] | None = None) -> int:
    """Entry point CLI. Retorna 0 se tudo reconciliou, 1 se algum mes divergiu."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Seed de custos de manutencao (CSV -> Mongo).")
    parser.add_argument("--mes", action="append", help="mes YYYY-MM (repetivel)")
    parser.add_argument("--all", action="store_true", help="carrega todos os meses disponiveis")
    parser.add_argument("--csv-base", default=os.environ.get("CUSTOS_CSV_BASE", DEFAULT_CSV_BASE))
    parser.add_argument("--mongo-uri", default=os.environ.get("CUSTOS_MONGO_URI", DEFAULT_MONGO_URI))
    parser.add_argument("--db", default=os.environ.get("CUSTOS_DB", DEFAULT_DB))
    parser.add_argument("--dry-run", action="store_true", help="nao grava; so parse + reconciliacao")
    args = parser.parse_args(argv)

    base = Path(args.csv_base)
    if not base.exists():
        logger.error("CSV base nao existe: %s", base)
        return 2

    if args.all:
        meses = meses_disponiveis(base)
    elif args.mes:
        meses = sorted(set(args.mes))
    else:
        parser.error("informe --mes YYYY-MM (repetivel) ou --all")
        return 2

    db = None if args.dry_run else _conectar(args.mongo_uri, args.db)
    if args.dry_run:
        logger.info(">>> DRY-RUN (nada sera gravado)")

    carregado_em = datetime.now()
    relatorios = [seed_mes(db, base, m, carregado_em, dry_run=args.dry_run) for m in meses]

    logger.info("")
    logger.info("%-9s %7s %6s %14s %14s %14s %5s", "mes", "contas", "lanc", "exec_soma", "exec_oficial", "lanc_soma", "ok")
    total_exec = 0.0
    for r in relatorios:
        logger.info(
            "%-9s %7d %6d %14.2f %14.2f %14.2f %5s",
            r["mes"], r["contas"], r["lancamentos"], r["soma_exec"], r["geral_exec"],
            r["soma_lancamentos"], "OK" if r["reconcilia"] else "DIVERG",
        )
        total_exec += r["soma_exec"]
    logger.info("%-9s %7s %6s %14.2f", "TOTAL", "", "", round(total_exec, 2))

    divergentes = [r["mes"] for r in relatorios if not r["reconcilia"]]
    if divergentes:
        logger.warning("Meses que NAO reconciliaram: %s", divergentes)
        return 1
    logger.info("Todos os meses reconciliaram na virgula.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
