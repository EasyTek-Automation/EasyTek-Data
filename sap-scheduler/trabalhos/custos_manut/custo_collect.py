# -*- coding: utf-8 -*-
"""custo_collect.py — coleta READ-ONLY de custo de manutenção do SAP.

Dois coletores (recebem uma sessão SAP GUI já conectada):
  collect_lancamentos(s, ini, fim) -> [dict]   # KSB1 (executado, linha-a-linha)
  collect_resumo(s, periodos)      -> [dict]   # ZBRCO019 (orçado+executado por conta)

Sem &XXL, sem Excel: lê a grade/rótulos no Python. NUNCA grava no SAP.
GT340 = 15 contas (33102104 é fantasma -> fora).
"""
import calendar, time, unicodedata
from datetime import datetime, timedelta

GT340 = ["33102101", "33102260", "33102264", "33102211", "33102130",   # G0341 Máquinas
         "33102265", "33102382",                                       # G0342 Utilidades
         "33102102", "33102105", "33102100",                           # G0343 Edifícios
         "33102106", "33102261", "33102263", "33102103", "33102400"]   # G0344 Outras
SUBGRUPO = {**{c: "G0341" for c in ("33102101","33102260","33102264","33102211","33102130")},
            **{c: "G0342" for c in ("33102265","33102382")},
            **{c: "G0343" for c in ("33102102","33102105","33102100")},
            **{c: "G0344" for c in ("33102106","33102261","33102263","33102103","33102400")}}
GRID = "wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell"

# colunas ricas a adicionar no layout da KSB1 (texto do pool -> normalizado)
# Só usadas no FALLBACK em runtime (_build_layout) — o caminho normal usa a variante /EASYTEK.
_RICH = ["No documento","Centro custo","Data do documento","Data de lancamento","Nome do usuario",
         "No doc.de referencia","Tipo de documento","estornado","Cod.debito/credito",
         "Documento de compras","Item","Texto do pedido","Texto breve de material","Centro","Material",
         # de/para de nome (KSB1): OBJ_TXT = nome do centro de custo; CEL_KTXT = nome da conta.
         # Alimentam as coleções AMG_CustoCentros/AMG_CustoContas (nome auto, sem dict manual).
         "Denominação de objeto","Descr.classe custo",
         # BR-13/BR-14: objeto parceiro = ordem emissora (liquidação) + descrição da ordem.
         "Ordem do parceiro","Denominação do objeto parceiro"]
_VARIANTE = "/EASYTEK"   # variante global salva (17 col) — traz PRTAU/POB_TXT sem runtime


def _norm(x):
    x = unicodedata.normalize("NFKD", x or "")
    x = "".join(c for c in x if not unicodedata.combining(c))
    return "".join(c for c in x.lower() if c.isalnum())


def parse_valor_br(x):
    """'1.234,56' -> 1234.56 ; sinal à direita '1.006,33-' = negativo (crédito)."""
    x = (x or "").strip().replace(".", "").replace(",", ".")
    neg = x.endswith("-")
    if neg:
        x = x[:-1]
    try:
        v = float(x)
    except ValueError:
        return 0.0
    return -v if neg else v


def janela_dois_meses(agora):
    """Mês corrente + anterior INTEIROS (início = 1º dia do mês anterior, fim = último dia
    do mês corrente).

    O fim era **D-1** até 25/09/2026. Esse corte escondia do detalhe (KSB1, filtrado por
    BUDAT) a **liquidação de ordens (KO88)**, que o SAP lança com data no ÚLTIMO dia do
    mês — enquanto o resumo (ZBRCO019, lido por **período**) já a enxergava. Resultado: no
    mês corrente a barra da tela mostrava o oficial e a tabela de detalhes só uma fração
    (set/2026: R$ 525.588,79 invisíveis na conta 33102101, 120 linhas datadas 30/09).
    Com os dois lados lendo o mês inteiro, barra e detalhe batem sempre.

    Contrapartida aceita pelo cliente em 25/09/2026: o executado do mês corrente passa a
    incluir provisão/liquidação com data futura — era o motivo original do D-1 (manter o
    acumulado do mês livre do accrual de fechamento).

    A âncora passou de `ontem` para `agora`: com fim no último dia do mês, ancorar em ontem
    deixaria o mês novo **fora** da janela no dia 1º.
    """
    inicio = (agora.replace(day=1) - timedelta(days=1)).replace(day=1)
    fim = agora.replace(day=calendar.monthrange(agora.year, agora.month)[1])
    return inicio, fim


def _ddmm(d):
    return d.strftime("%d.%m.%Y")


def _ddmm_to_date(x):
    try:
        return datetime.strptime(x.strip(), "%d.%m.%Y")
    except Exception:
        return None


def _has_popup(s, i=1):
    try:
        s.findById(f"wnd[{i}]"); return True
    except Exception:
        return False


def _handle_acc(s):
    """Popup 'Definir ACC' (área contábil) -> BR01 + OK."""
    if _has_popup(s) and "ACC" in (s.findById("wnd[1]").Text or ""):
        try:
            s.findById("wnd[1]/usr/sub:SAPLSPO4:0300/ctxtSVALD-VALUE[0,21]").Text = "BR01"
            s.findById("wnd[1]/tbar[0]/btn[0]").press(); time.sleep(0.6)
        except Exception:
            pass


def _multiselect_kstar(s, classes):
    """Preenche as classes via 'Upload do clipboard' do popup de seleção múltipla."""
    import win32clipboard
    s.findById("wnd[0]/usr/btn%_KSTAR_%_APP_%-VALU_PUSH").press(); time.sleep(0.8)
    win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText("\r\n".join(classes)); win32clipboard.CloseClipboard()
    s.findById("wnd[1]/tbar[0]/btn[24]").press(); time.sleep(0.6)   # Upload do clipboard
    s.findById("wnd[1]/tbar[0]/btn[8]").press(); time.sleep(0.6)    # Transferir (F8)


def _build_layout(s):
    """Adiciona as colunas ricas em RUNTIME (sem salvar nada)."""
    s.findById("wnd[0]/mbar/menu[3]/menu[0]/menu[0]").Select(); time.sleep(1.0)
    base = "wnd[1]/usr/tabsG_TS_ALV/tabpALV_M_R1/ssubSUB_DYN0510:SAPLSKBH:0620/"
    disp = s.findById(base + "cntlCONTAINER2_LAYO/shellcont/shell")
    pool = s.findById(base + "cntlCONTAINER1_LAYO/shellcont/shell")
    if pool.RowCount < disp.RowCount:
        disp, pool = pool, disp
    want = {_norm(w) for w in _RICH}
    rows = [r for r in range(pool.RowCount) if _norm(pool.GetCellValue(r, "SELTEXT")) in want]
    pool.selectedRows = ",".join(map(str, rows)); time.sleep(0.3)
    s.findById(base + "btnAPP_WL_SING").press(); time.sleep(0.4)
    s.findById("wnd[1]/tbar[0]/btn[0]").press(); time.sleep(0.8)


def _read_grid(s):
    """Lê o GuiGridView inteiro (paginando) -> [dict tecnico->valor]."""
    g = s.findById(GRID)
    rc = g.RowCount
    cols = [c for c in g.ColumnOrder]
    vis = g.VisibleRowCount if hasattr(g, "VisibleRowCount") else 16
    out = []
    top = 0
    while top < rc:
        try:
            g.firstVisibleRow = top
        except Exception:
            pass
        time.sleep(0.08)
        for r in range(top, min(top + vis, rc)):
            try:
                k = g.GetCellValue(r, "KSTAR")
            except Exception:
                continue
            if not k or not k.strip().startswith("3"):
                continue
            out.append({c: g.GetCellValue(r, c) for c in cols})
        top += vis
    return out


def _tem_colunas_parceiro(s):
    """True se a grade já expõe as colunas do objeto parceiro (PRTAU + POB_TXT).

    É como sabemos que a variante /EASYTEK foi aplicada. Se vier False (variante editada
    ou apagada no SAP), o coletor monta o layout em runtime como fallback (aviso 2 do estudo
    `estudo-enriquecimento-custo-2101` §8) — nunca coleta silenciosamente sem a ordem/descrição.
    """
    try:
        cols = [c for c in s.findById(GRID).ColumnOrder]
        return "PRTAU" in cols and "POB_TXT" in cols
    except Exception:
        return False


def _familia(r):
    """Família do lançamento (BR-13): 'liquidacao' | 'compra' | 'estoque'.

    Chave = presença da ordem emissora (PRTAU), NÃO o tipo de documento — assim a liquidação
    real (SA com ordem) é separada da reclassificação SA manual (sem ordem, cai em 'estoque').
    """
    if (r.get("PRTAU") or "").strip():
        return "liquidacao"
    if (r.get("EBELN") or "").strip():
        return "compra"
    return "estoque"


def _descritor(r):
    """Descritor por cascata (BR-13): texto do pedido -> texto do material -> descrição da
    ordem. Primeiro não-vazio vence; se as três faltarem, vazio (não inventa)."""
    return ((r.get("EBTXT") or "").strip()
            or (r.get("MAT_TXT") or "").strip()
            or (r.get("POB_TXT") or "").strip())


def _map_lancamento(r):
    """Mapeia uma linha crua da grade KSB1 -> doc AMG_CustoLancamentos (BR-13/14/16).

    Puro (sem SAP) para ser testável com dicts fake. Retorna None se a linha não é de classe
    de custo (KSTAR não começa com '3'). Campos novos do incremento de enriquecimento:
    `descritor` (cascata), `familia`, `ordem_emissora`, `doc_ref`, `material`, `usuario`,
    `planta`. Campos existentes preservados (retrocompat, BR-16). `conta_nome` passa a ler
    `CEL_KTXT` (título "Descr.classe custo" na /EASYTEK), com `CEL_LTXT` de fallback.
    """
    conta = (r.get("KSTAR") or "").strip()
    if not conta.startswith("3"):
        return None
    dt = _ddmm_to_date((r.get("BUDAT") or "").strip())
    return {
        "mes_referencia": dt.strftime("%Y-%m") if dt else "",   # convenção do banco: YYYY-MM
        "data_lancamento": dt,   # datetime (BSON Date) — convenção do banco
        "conta": conta,
        "conta_nome": (r.get("CEL_KTXT") or r.get("CEL_LTXT") or "").strip(),   # nome da conta (KSB1)
        "centro_custo": (r.get("KOSTL") or "").strip(),
        "centro_nome": (r.get("OBJ_TXT") or "").strip(),     # nome do centro (KSB1)
        "valor": parse_valor_br(r.get("WRGBTR")),
        "descritor": _descritor(r),                          # BR-13 cascata
        "familia": _familia(r),                              # BR-13
        "ordem_emissora": (r.get("PRTAU") or "").strip(),    # BR-14 (chave de rastreio)
        "doc_ref": (r.get("REFBN") or "").strip(),           # doc de material/FI
        "material": (r.get("MATNR") or "").strip(),
        "usuario": (r.get("USNAM") or "").strip(),           # requisitante/lançador
        "planta": (r.get("WERKS") or "").strip(),
        "tipo_doc": (r.get("BLART") or "").strip(),
        "no_documento": (r.get("BELNR") or "").strip(),
        "pedido_compra": (r.get("EBELN") or "").strip(),
        "fonte": "sap",
    }


def collect_lancamentos(s, ini, fim, classes=None):
    """KSB1 -> lançamentos DS-03 (AMG_CustoLancamentos), enriquecidos (BR-13/14)."""
    classes = classes or GT340
    s.findById("wnd[0]/tbar[0]/okcd").Text = "/nKSB1"
    s.findById("wnd[0]").sendVKey(0); time.sleep(1.2)
    _handle_acc(s)
    def setv(eid, v):
        try: s.findById("wnd[0]/usr/" + eid).Text = v
        except Exception: pass
    # KOKRS=BR01 é a ÁREA CONTÁBIL; o grupo de centro de custo é BR02CUSTO (planta do Max —
    # reproduz a planilha oficial GT340; com BR01CUSTO o REAL dava ~metade). Ver SDD BR-11/DS-10.
    setv("ctxtP_KOKRS", "BR01"); setv("ctxtKSTGR", "BR02CUSTO"); setv("ctxtKOAGR", "")
    setv("ctxtKSTAR-LOW", ""); setv("ctxtKSTAR-HIGH", "")
    setv("ctxtKOSTL-LOW", ""); setv("ctxtKOSTL-HIGH", "")
    setv("ctxtR_BUDAT-LOW", _ddmm(ini)); setv("ctxtR_BUDAT-HIGH", _ddmm(fim))
    setv("ctxtP_DISVAR", _VARIANTE)   # BR-13/14: variante /EASYTEK traz cascata + parceiro (17 col)
    _multiselect_kstar(s, classes)
    s.findById("wnd[0]").sendVKey(8); time.sleep(2.0)
    while _has_popup(s):
        s.findById("wnd[1]").sendVKey(0); time.sleep(0.8)
    # fallback: se a /EASYTEK não trouxe o objeto parceiro (variante editada/apagada), monta
    # as colunas ricas em runtime — nunca coleta sem ordem/descrição (estudo §8, aviso 2).
    if not _tem_colunas_parceiro(s):
        _build_layout(s)
    raw = _read_grid(s)
    docs = []
    for r in raw:
        d = _map_lancamento(r)
        if not d or d["conta"] not in classes:
            continue
        docs.append(d)
    return docs


def depara_de_docs(docs):
    """De/para código→nome extraído dos lançamentos (OBJ_TXT/CEL_LTXT da KSB1).

    Retorna `(centros, contas)` — dois dicts `{código: nome}`. O 1º nome não-vazio por
    código vence. Alimenta o upsert das coleções AMG_CustoCentros/AMG_CustoContas, então
    um rename no SAP é refletido na próxima coleta (sem dict manual no código).
    """
    centros, contas = {}, {}
    for d in docs:
        c = (d.get("centro_custo") or "").strip()
        cn = (d.get("centro_nome") or "").strip()
        if c and cn:
            centros.setdefault(c, cn)
        a = (d.get("conta") or "").strip()
        an = (d.get("conta_nome") or "").strip()
        if a and an:
            contas.setdefault(a, an)
    return centros, contas


# ============================ MB25 — componentes da ordem (BR-15) ============================

_MB25_GRIDS = ["wnd[0]/usr/cntlGRID1/shellcont/shell",
               "wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell"]


def _cell(row, *names):
    """Primeiro campo **não-vazio** entre os aliases (a grade MB25 varia o sufixo `_I`, e às
    vezes a coluna existe mas vem vazia — nesse caso tenta o próximo alias)."""
    for n in names:
        if n in row:
            v = (row.get(n) or "").strip()
            if v:
                return v
    return ""


def _add_maktx_mb25(s):
    """Adiciona 'Texto breve de material' (MAKTX) ao layout da MB25 em RUNTIME → preenche o
    `material_desc` dos componentes (BR-15). Read-only (não salva variante). Degrada suave
    (código sem nome) se o diálogo não abrir.

    A MB25 no layout padrão NÃO expõe a descrição do material (só `MATNR_I`/`BDMNG_I`/`ACCOU`
    etc.) — igual à KSB1, precisa injetar a coluna. IDs confirmados ao vivo no cliente:
    menu Configurações ▸ Layout ▸ Modificar = `menu[3]/menu[2]/menu[0]`; diálogo ALV padrão
    (SAPLSKBH); campo do pool com SELTEXT "Texto breve de material"; botão `btnAPP_WL_SING`.
    """
    try:
        s.findById("wnd[0]/mbar/menu[3]/menu[2]/menu[0]").Select(); time.sleep(1.0)
    except Exception:
        return
    base = "wnd[1]/usr/tabsG_TS_ALV/tabpALV_M_R1/ssubSUB_DYN0510:SAPLSKBH:0620/"
    try:
        disp = s.findById(base + "cntlCONTAINER2_LAYO/shellcont/shell")
        pool = s.findById(base + "cntlCONTAINER1_LAYO/shellcont/shell")
    except Exception:
        try: s.findById("wnd[1]/tbar[0]/btn[12]").press()   # cancela se o diálogo veio diferente
        except Exception: pass
        return
    if pool.RowCount < disp.RowCount:
        disp, pool = pool, disp
    alvo = _norm("Texto breve de material")
    rows = [r for r in range(pool.RowCount) if _norm(pool.GetCellValue(r, "SELTEXT")) == alvo]
    if not rows:
        try: s.findById("wnd[1]/tbar[0]/btn[12]").press()
        except Exception: pass
        return
    try:
        pool.selectedRows = ",".join(map(str, rows)); time.sleep(0.3)
        s.findById(base + "btnAPP_WL_SING").press(); time.sleep(0.4)
        s.findById("wnd[1]/tbar[0]/btn[0]").press(); time.sleep(0.8)
    except Exception:
        pass


def _norm_ordem(x):
    """`ACCOU` (MB25) vem com zeros à esquerda; `ordem_emissora`/`PRTAU` (KSB1) não.
    Normaliza para a junção casar (ex.: '000005019483' -> '5019483')."""
    return (x or "").strip().lstrip("0")


def _map_componente(row, mes_ref=""):
    """Linha da grade MB25 -> doc AMG_CustoOrdemComponentes (BR-15). Puro/testável.

    Só entra o **baixado**: `DIFFMG == 0` (saldo a retirar zerado) — reserva que não virou
    baixa fica de fora (reservar ≠ consumir). Retorna None se faltar material/ordem ou o
    saldo a retirar não for zero. **Quantidade, não R$** (a MB25 não traz valor por item).
    """
    material = _cell(row, "MATNR_I", "MATNR")
    if not material:
        return None
    if abs(parse_valor_br(_cell(row, "DIFFMG"))) > 1e-9:   # saldo a retirar != 0 -> não baixado
        return None
    ordem = _norm_ordem(_cell(row, "ACCOU"))
    if not ordem:
        return None
    return {
        "ordem": ordem,
        "mes_referencia": mes_ref,
        "material": material,
        "material_desc": _cell(row, "MAKTX", "MAKTX_I", "MATXT", "MATXT_I"),
        "quantidade": parse_valor_br(_cell(row, "BDMNG_I", "BDMNG")),
        "unidade": _cell(row, "MEINS_I", "MEINS"),
        "fonte": "sap",
    }


def collect_componentes(s, ordens, mes_ref=""):
    """MB25 -> componentes (itens de material baixados) das ordens, em LOTE (BR-15).

    Read-only. `ordens` = ordens emissoras (`PRTAU`) das linhas de liquidação da janela.
    Multisseleção via 'Upload do clipboard' (igual à coleta de classes). Junção por `ACCOU`.
    Retorna [dict] por ordem×material com `DIFFMG=0`. Lista vazia se `ordens` vazio.
    """
    ordens = [o for o in dict.fromkeys((o or "").strip() for o in (ordens or [])) if o]
    if not ordens:
        return []
    import win32clipboard
    s.findById("wnd[0]/tbar[0]/okcd").Text = "/nMB25"
    s.findById("wnd[0]").sendVKey(0); time.sleep(1.3)
    def setv(short, v):
        try: s.findById("wnd[0]/usr/" + short).Text = v
        except Exception: pass
    setv("ctxtMATNR-LOW", ""); setv("ctxtWERKS-LOW", ""); setv("ctxtWERKS-HIGH", "")
    setv("ctxtAUFNR-LOW", ""); setv("ctxtAUFNR-HIGH", "")
    for chk in ("chkP_OPEN", "chkP_ISSUES", "chkP_CANCEL", "chkP_RECEIP", "chkP_CLOSED"):
        try: s.findById("wnd[0]/usr/" + chk).selected = True
        except Exception: pass
    s.findById("wnd[0]/usr/btn%_AUFNR_%_APP_%-VALU_PUSH").press(); time.sleep(1.0)
    win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText("\r\n".join(ordens)); win32clipboard.CloseClipboard()
    s.findById("wnd[1]/tbar[0]/btn[24]").press(); time.sleep(0.8)   # Upload do clipboard
    s.findById("wnd[1]/tbar[0]/btn[8]").press(); time.sleep(0.8)    # Transferir (F8)
    s.findById("wnd[0]").sendVKey(8); time.sleep(3.0)
    while _has_popup(s):
        s.findById("wnd[1]").sendVKey(0); time.sleep(1.0)
    _add_maktx_mb25(s)   # injeta a coluna de descrição do material (senão material_desc vem vazio)
    g = None
    for gid in _MB25_GRIDS:
        try: g = s.findById(gid); break
        except Exception: continue
    if g is None or not hasattr(g, "ColumnOrder"):
        return []   # lista clássica (sem ALV) — sem componentes legíveis
    cols = [c for c in g.ColumnOrder]
    rc = g.RowCount
    vis = g.VisibleRowCount if hasattr(g, "VisibleRowCount") else 20
    out, top = [], 0
    while top < rc:
        try: g.firstVisibleRow = top
        except Exception: pass
        time.sleep(0.06)
        for r in range(top, min(top + vis, rc)):
            d = _map_componente({c: g.GetCellValue(r, c) for c in cols}, mes_ref)
            if d:
                out.append(d)
        top += vis
    return out


def _scrape_zbrco019_periodo(s, ano, periodo):
    """ZBRCO019 1 período -> {conta: (executado, orcado)} + geral_executado."""
    def setv(eid, v):
        try: s.findById("wnd[0]/usr/" + eid).Text = v
        except Exception: pass
    s.findById("wnd[0]/tbar[0]/okcd").Text = "/nZBRCO019"
    s.findById("wnd[0]").sendVKey(0); time.sleep(1.2)
    setv("txt$1GJAHLJ", str(ano)); setv("ctxt$1PERIV", str(periodo)); setv("ctxt$1PERIB", str(periodo))
    # $1KOSET = grupo de centro de custo BR02CUSTO (planta do Max — reproduz a planilha oficial). Ver SDD BR-11/DS-10.
    setv("ctxt$1KOSET", "BR02CUSTO"); setv("ctxt$1KSTAR", "DESP_COCKP")
    s.findById("wnd[0]").sendVKey(8); time.sleep(2.3)
    if _has_popup(s):
        s.findById("wnd[1]").sendVKey(0); time.sleep(1.2)
    store = {}; geral = [None]
    def grab():
        rows = {}
        def rec(n):
            try: kids = n.Children; cnt = kids.Count
            except Exception: return
            for i in range(cnt):
                try: c = kids(i)
                except Exception: continue
                try:
                    if c.Type == "GuiLabel":
                        cid = c.Id; tx = c.Text
                        if tx.strip():
                            co = cid[cid.rindex("[")+1:cid.rindex("]")]; col, r = co.split(",")
                            rows.setdefault(int(r), {})[int(col)] = tx
                except Exception: pass
                rec(c)
        rec(s.findById("wnd[0]/usr")); return rows
    def absorb():
        for r, cols in grab().items():
            d = None
            for cc in sorted(cols):
                if cc <= 8 and any(ch.isalpha() for ch in cols[cc]):
                    d = cols[cc].strip(); break
            if not d:
                continue
            if "GT340" in d and d.strip().startswith("**") and geral[0] is None:
                geral[0] = parse_valor_br(cols.get(42, ""))
            cur = store.get(d, ["", ""])
            if cols.get(42, "").strip() and not cur[0]:
                cur[0] = cols[42].strip()   # Real / executado
            if cols.get(58, "").strip() and not cur[1]:
                cur[1] = cols[58].strip()   # Plan / orçado
            store[d] = cur
    absorb()
    try:
        # para de rolar assim que achar o total GT340 (seção agregada está acima;
        # evita a seção por-centro com rótulos truncados + acelera ~4x)
        mx = s.findById("wnd[0]/usr").verticalScrollbar.Maximum; pos = 0
        while pos < mx and geral[0] is None:
            pos = min(pos + 18, mx)
            s.findById("wnd[0]/usr").verticalScrollbar.Position = pos; time.sleep(0.25); absorb()
    except Exception:
        pass
    import re
    cand = {}
    for d in store:
        m = re.match(r"^(33102\d{3})\s+(.*)$", d)
        if not m:
            continue
        cod = m.group(1)
        if cod not in GT340:
            continue
        real, plan = store[d]
        cand.setdefault(cod, []).append((m.group(2).strip(), parse_valor_br(real), parse_valor_br(plan)))
    # por conta, fica com a variante de maior magnitude (a agregada, não a truncada)
    out = {cod: max(lst, key=lambda t: abs(t[1]) + abs(t[2])) for cod, lst in cand.items()}
    return out, geral[0]


def collect_resumo(s, periodos):
    """ZBRCO019 -> resumo DS-03 (AMG_CustoResumo) por conta × mês."""
    docs = []
    for ano, per in periodos:
        contas, geral = _scrape_zbrco019_periodo(s, ano, per)
        mes_ref = f"{ano}-{per:02d}"   # convenção do banco: YYYY-MM
        for cod, (desc, ex, orc) in contas.items():
            docs.append({
                "conta": cod,
                "conta_desc": desc,
                "subgrupo": SUBGRUPO.get(cod, ""),
                "grupo": "GT340",
                "mes_referencia": mes_ref,
                "orcado": orc,
                "executado": ex,
                "total_oficial_geral": geral,
                "fonte": "sap",
            })
    return docs


if __name__ == "__main__":   # teste standalone (40MASSIS, read-only)
    import sys, json, time as _t
    sys.path.insert(0, ".")
    import zpp_gridcap
    eng = zpp_gridcap.get_engine()
    s = eng.Children(0).Children(0)
    ini, fim = janela_dois_meses(datetime(2026, 6, 12))
    print(f"[teste] janela {_ddmm(ini)}..{_ddmm(fim)}")
    t0 = _t.time()
    lanc = collect_lancamentos(s, ini, fim)
    print(f"[lancamentos] {len(lanc)} docs em {_t.time()-t0:.1f}s")
    if lanc:
        print("  amostra:", json.dumps(lanc[0], default=str, ensure_ascii=False))
        print("  soma valor:", round(sum(d["valor"] for d in lanc), 2))
        print("  meses:", sorted({d["mes_referencia"] for d in lanc}))
        print("  contas:", sorted({d["conta"] for d in lanc}))
    s.findById("wnd[0]/tbar[0]/okcd").Text = "/n"; s.findById("wnd[0]").sendVKey(0)
