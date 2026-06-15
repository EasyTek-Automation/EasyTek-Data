# -*- coding: utf-8 -*-
"""custo_collect.py — coleta READ-ONLY de custo de manutenção do SAP.

Dois coletores (recebem uma sessão SAP GUI já conectada):
  collect_lancamentos(s, ini, fim) -> [dict]   # KSB1 (executado, linha-a-linha)
  collect_resumo(s, periodos)      -> [dict]   # ZBRCO019 (orçado+executado por conta)

Sem &XXL, sem Excel: lê a grade/rótulos no Python. NUNCA grava no SAP.
GT340 = 15 contas (33102104 é fantasma -> fora).
"""
import time, unicodedata
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
_RICH = ["No documento","Centro custo","Data do documento","Data de lancamento","Nome do usuario",
         "No doc.de referencia","Tipo de documento","estornado","Cod.debito/credito",
         "Documento de compras","Item","Texto do pedido","Texto breve de material","Centro","Material"]


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
    """Mês corrente + anterior, até D-1. (início = 1º dia do mês anterior, fim = D-1)."""
    ontem = agora - timedelta(days=1)
    inicio = (ontem.replace(day=1) - timedelta(days=1)).replace(day=1)
    return inicio, ontem


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


def collect_lancamentos(s, ini, fim, classes=None):
    """KSB1 -> lançamentos DS-03 (AMG_CustoLancamentos)."""
    classes = classes or GT340
    s.findById("wnd[0]/tbar[0]/okcd").Text = "/nKSB1"
    s.findById("wnd[0]").sendVKey(0); time.sleep(1.2)
    _handle_acc(s)
    def setv(eid, v):
        try: s.findById("wnd[0]/usr/" + eid).Text = v
        except Exception: pass
    setv("ctxtP_KOKRS", "BR01"); setv("ctxtKSTGR", "BR01CUSTO"); setv("ctxtKOAGR", "")
    setv("ctxtKSTAR-LOW", ""); setv("ctxtKSTAR-HIGH", "")
    setv("ctxtKOSTL-LOW", ""); setv("ctxtKOSTL-HIGH", "")
    setv("ctxtR_BUDAT-LOW", _ddmm(ini)); setv("ctxtR_BUDAT-HIGH", _ddmm(fim))
    _multiselect_kstar(s, classes)
    s.findById("wnd[0]").sendVKey(8); time.sleep(2.0)
    while _has_popup(s):
        s.findById("wnd[1]").sendVKey(0); time.sleep(0.8)
    _build_layout(s)
    raw = _read_grid(s)
    docs = []
    for r in raw:
        conta = (r.get("KSTAR") or "").strip()
        if conta not in classes:
            continue
        budat = (r.get("BUDAT") or "").strip()
        dt = _ddmm_to_date(budat)
        mes_ref = dt.strftime("%Y-%m") if dt else ""   # convenção do banco: YYYY-MM
        docs.append({
            "mes_referencia": mes_ref,
            "data_lancamento": dt,   # datetime (BSON Date) — convenção do banco
            "conta": conta,
            "centro_custo": (r.get("KOSTL") or "").strip(),
            "valor": parse_valor_br(r.get("WRGBTR")),
            "descritor": (r.get("EBTXT") or r.get("MAT_TXT") or "").strip(),
            "tipo_doc": (r.get("BLART") or "").strip(),
            "no_documento": (r.get("BELNR") or "").strip(),
            "pedido_compra": (r.get("EBELN") or "").strip(),
            "fonte": "sap",
        })
    return docs


def _scrape_zbrco019_periodo(s, ano, periodo):
    """ZBRCO019 1 período -> {conta: (executado, orcado)} + geral_executado."""
    def setv(eid, v):
        try: s.findById("wnd[0]/usr/" + eid).Text = v
        except Exception: pass
    s.findById("wnd[0]/tbar[0]/okcd").Text = "/nZBRCO019"
    s.findById("wnd[0]").sendVKey(0); time.sleep(1.2)
    setv("txt$1GJAHLJ", str(ano)); setv("ctxt$1PERIV", str(periodo)); setv("ctxt$1PERIB", str(periodo))
    setv("ctxt$1KOSET", "BR01CUSTO"); setv("ctxt$1KSTAR", "DESP_COCKP")
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
