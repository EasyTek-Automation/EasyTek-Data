"""
zpp_gridcap.py — captura READ-ONLY da estrutura de grade ALV do SAP.
Uso (PC do cliente, SAP logado GM3/040, Python 32-bit):

  python zpp_gridcap.py --list-sessions
  # navegue no SAP até ZPPPRD, aplique layout/filtros, F8 (grade na tela), então:
  python zpp_gridcap.py --gridcap --out zppprd-cols.txt
  # repita pra ZPP_NT0001:
  python zpp_gridcap.py --gridcap --out nt0001-cols.txt
  # se a tela não tiver grade ALV (lista clássica), use:
  python zpp_gridcap.py --dump > tela.txt

NUNCA grava no SAP. Sem caminho de escrita. Não adicione um.
"""
import sys, os, struct, time, argparse


def excel_pids():
    """Conjunto de PIDs de EXCEL.EXE em execução (via tasklist)."""
    import subprocess
    pids = set()
    try:
        out = subprocess.run('tasklist /FI "IMAGENAME eq EXCEL.EXE" /FO CSV /NH',
                             shell=True, capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = [p.strip().strip('"') for p in line.split('","')]
            if len(parts) >= 2 and parts[0].upper().startswith("EXCEL"):
                pids.add(parts[1])
    except Exception:
        pass
    return pids


def kill_new_excel(before, wait=20):
    """Espera SURGIR um PID de Excel novo (não confia em delay fixo) e mata só ESSE.
    Se nada surgir em `wait`s, não mata nada. Retorna o que matou."""
    import time as _t
    deadline = _t.time() + wait
    while _t.time() < deadline:
        novos = excel_pids() - before
        if novos:
            for pid in novos:
                os.system(f"taskkill /PID {pid} /F >nul 2>&1")
            return novos
        _t.sleep(0.4)
    return set()


def _close_popups(s):
    """Fecha popups SAP perdidos (wnd[2]/wnd[1]) com Cancel — read-only, p/ começar limpo."""
    for w in ("wnd[2]", "wnd[1]"):
        try:
            s.findById(w).sendVKey(12)   # F12 = cancelar
            time.sleep(0.3)
        except Exception:
            pass


def get_engine():
    import win32com.client
    try:
        return win32com.client.GetObject("SAPGUI").GetScriptingEngine  # property, SEM ()
    except Exception as e:
        print(f"[FALHA-A] {e}")
    try:
        w = win32com.client.Dispatch("SapROTWr.SapROTWrapper")
        g = w.GetROTEntry("SAPGUI")
        try:
            return g.GetScriptingEngine
        except Exception:
            return g.GetScriptingEngine()
    except Exception as e:
        print(f"[FALHA-B] {e}")
    # AJ-02-01 (RV-02): levanta RuntimeError em vez de sys.exit(1).
    # daemon classifica como fase="conexao_sap" sem morrer.
    raise RuntimeError(
        "get_engine: nao conectou ao SAP scripting engine "
        "(verifique: scripting habilitado, SAP logado, Python 32-bit)"
    )


def banner(t):
    print("\n" + "=" * 70 + f"\n {t}\n" + "=" * 70)


def coll(c):
    """Itera GuiCollection (ColumnOrder / GetColumnTitles) de forma tolerante."""
    out = []
    try:
        n = c.Count
    except Exception:
        return out
    for i in range(n):
        v = None
        for acc in ("ElementAt", "Item"):
            try:
                v = getattr(c, acc)(i); break
            except Exception:
                pass
        if v is None:
            try:
                v = c(i)
            except Exception:
                v = None
        out.append(v)
    return out


def col_title(grid, cid):
    try:
        ts = coll(grid.GetColumnTitles(cid))
    except Exception:
        return ""
    best = ""
    for t in ts:
        if t and len(str(t)) > len(best):
            best = str(t)
    return best


def find_grid(el, depth=0, maxd=45):
    # Aceita GuiGridView OU qualquer shell que exponha ColumnOrder. O ALV
    # (SAPGUI.GridViewCtrl.1) às vezes vem com Type 'GuiShell', aninhado em
    # splitter/HTML container (ex.: layout /prod.indic do ZPPPRD).
    try:
        t = getattr(el, "Type", "")
        if t == "GuiGridView":
            return el
        if t in ("GuiShell", "GuiCtrlGridView"):
            _ = el.ColumnOrder.Count       # só grids têm ColumnOrder; senão estoura
            return el
    except Exception:
        pass
    if depth >= maxd:
        return None
    try:
        kids = el.Children; n = kids.Count
    except Exception:
        return None
    for i in range(n):
        try:
            r = find_grid(kids(i), depth + 1, maxd)
            if r:
                return r
        except Exception:
            pass
    return None


def statusbar(s):
    try:
        sb = s.findById("wnd[0]/sbar")
        return f"[{sb.MessageType}] {sb.Text}"
    except Exception:
        return ""


def walk(el, depth=0, maxd=40):
    pad = "  " * depth

    def g(a, d=""):
        try:
            return getattr(el, a)
        except Exception:
            return d
    print(f"{pad}{g('Type','?'):24} | {g('Id','?')}")
    nm, tx = g("Name", ""), g("Text", "")
    if nm or tx:
        print(f"{pad}{'':24}   name={nm!r} text={tx!r}")
    if g("Type", "") == "GuiGridView":
        return
    if depth >= maxd:
        return
    try:
        kids = el.Children; n = kids.Count
    except Exception:
        return
    for i in range(n):
        try:
            walk(kids(i), depth + 1, maxd)
        except Exception as e:
            print(f"{pad}  [filho {i} ilegível: {e}]")


def do_dump(s):
    banner(f"DUMP tela atual — tx={s.Info.Transaction}")
    print(f"título: {s.findById('wnd[0]').Text!r}")
    print(f"statusbar: {statusbar(s)}")
    walk(s.findById("wnd[0]/usr"))
    try:
        s.findById("wnd[1]")
        print("\n--- popup wnd[1] ---")
        walk(s.findById("wnd[1]/usr"))
    except Exception:
        pass


def gridcap(s, args):
    lines = []

    def emit(t=""):
        print(t); lines.append(t)

    # navegação autônoma opcional (read-only): entra na tx, seta layout/filtros
    # (--set "id=valor", repetível) e dá F8. Nada de escrita — só relatório.
    if args.tx:
        s.findById("wnd[0]/tbar[0]/okcd").Text = f"/n{args.tx}"
        s.findById("wnd[0]").sendVKey(0)
        time.sleep(0.6)
        for kv in (args.set or []):
            k, _, v = kv.partition("=")
            try:
                if v == "@select":                 # radio/checkbox (ex: 'Exibir Dados')
                    s.findById(k).select()
                    print(f"   select {k}")
                else:
                    s.findById(k).Text = v
                    print(f"   set {k} = {v!r}")
            except Exception as e:
                print(f"   [aviso] set {k}: {e}")
        if not args.no_f8:
            s.findById("wnd[0]").sendVKey(8)  # F8 executar (read-only num relatório)
            time.sleep(0.8)

    banner(f"GRIDCAP — tx={s.Info.Transaction} | título={s.findById('wnd[0]').Text!r}")
    emit(f"tx        : {s.Info.Transaction}")
    emit(f"título    : {s.findById('wnd[0]').Text!r}")
    emit(f"statusbar : {statusbar(s)}")

    grid = find_grid(s.findById("wnd[0]/usr"))
    if grid is None:
        emit("\n[gridcap] NENHUM GuiGridView — pode ser lista clássica. Dump completo:")
        _flush(args, lines)
        do_dump(s)
        return

    try:
        rows = grid.RowCount
    except Exception as e:
        rows = None; emit(f"RowCount falhou: {e}")
    cols = [c for c in coll(grid.ColumnOrder) if c is not None]
    emit(f"\ngrid_id   : {getattr(grid,'Id','?')}")
    emit(f"RowCount  : {rows}")
    emit(f"Colunas   : {len(cols)}\n")
    emit("COLUNAS (técnico | título de exibição):")
    for c in cols:
        emit(f"   {str(c):28} | {col_title(grid, c)}")

    emit("\nAMOSTRA (linhas 0..2 + última):")
    show = list(range(min(rows or 0, 3)))
    if rows and rows > 3:
        show.append(rows - 1)
    for r in show:
        if rows and rows > 3 and r == rows - 1:
            try:
                grid.firstVisibleRow = rows - 1   # ALV virtualiza: materializa o fim
            except Exception:
                pass
        vals = {}
        for c in cols:
            try:
                vals[c] = grid.GetCellValue(r, c)
            except Exception:
                vals[c] = "?"
        tag = " (ÚLTIMA)" if rows and r == rows - 1 and rows > 3 else ""
        emit(f"   row[{r}]{tag} {vals}")
    _flush(args, lines)


def navigate(s, args):
    """Navegação read-only reutilizável: okcode /n<tx>, aplica --set (layout/filtros/
    radio @select), e F8 (salvo --no-f8). Não escreve no banco — só relatório."""
    if not args.tx:
        return
    s.findById("wnd[0]/tbar[0]/okcd").Text = f"/n{args.tx}"
    s.findById("wnd[0]").sendVKey(0)
    time.sleep(0.6)
    for kv in (args.set or []):
        k, _, v = kv.partition("=")
        try:
            if v == "@select":
                s.findById(k).select()
                print(f"   select {k}")
            else:
                s.findById(k).Text = v
                print(f"   set {k} = {v!r}")
        except Exception as e:
            print(f"   [aviso] set {k}: {e}")
    if not args.no_f8:
        s.findById("wnd[0]").sendVKey(8)
        time.sleep(0.9)


def export_grid(s, args):
    """VIA C — dispara o export ALV→planilha (mesmo da tela 'Exibir Dados') via menu de
    contexto do GuiGridView. READ-ONLY no SAP; grava arquivo em disco. Faz dump de cada
    popup pra descobrir IDs/opções. Não há caminho de escrita no banco."""
    banner("EXPORT VIA C — ALV → planilha")
    excel_before = excel_pids() if getattr(args, "kill_excel", False) else set()
    _close_popups(s)
    navigate(s, args)
    grid = find_grid(s.findById("wnd[0]/usr"))
    if grid is None:
        print("[export] sem GuiGridView na tela — render falhou. Dump:")
        do_dump(s)
        # AJ-02-02 (RV-02): levanta em vez de return silencioso.
        raise RuntimeError("export: grid nao encontrado na tela (navegacao falhou)")
    print(f"   grid_id={getattr(grid,'Id','?')} RowCount={getattr(grid,'RowCount','?')}")
    try:
        grid.setCurrentCell(-1, "")
    except Exception as e:
        print(f"   [aviso] setCurrentCell: {e}")
    try:
        grid.contextMenu()
    except Exception as e:
        print(f"   [ERRO] contextMenu(): {e}")
        # AJ-02-02
        raise RuntimeError(f"export contextMenu falhou: {e}") from e
    code = args.ctx_code or "&XXL"      # &XXL=Planilha(moderno); &PC=arq.local; &XLS;&XML
    try:
        grid.selectContextMenuItem(code)
        print(f"   selectContextMenuItem({code}) OK")
    except Exception as e:
        print(f"   selectContextMenuItem({code}) FALHOU: {e}")
        print("   → tente outro --ctx-code (&PC/&XLS/&XML) ou dump do menu.")
        # AJ-02-02
        raise RuntimeError(f"export selectContextMenuItem({code}) falhou: {e}") from e
    time.sleep(1.0)
    # se não for o popup de formato do &XXL (ex.: &PC), só despeja pra descobrir
    has_xxl_combo = False
    try:
        s.findById("wnd[1]/usr/cmbG_LISTBOX")
        has_xxl_combo = True
    except Exception:
        pass
    if not has_xxl_combo:
        print(f"\n[export] popup diferente do &XXL (ctx-code={code}). Dump pra descobrir:")
        try:
            print(f"   wnd[1] = {s.findById('wnd[1]').Text!r}")
            walk(s.findById("wnd[1]/usr"))
        except Exception as e:
            print(f"   sem wnd[1]: {e}")
        # AJ-02-02
        raise RuntimeError(f"export popup nao reconhecido (ctx-code={code})")
    # POPUP 1 — escolha de formato (diálogo SAP "Formatos:")
    try:
        w = s.findById("wnd[1]")
        print(f"\n[fmt popup] {w.Text!r}")
        cmb = s.findById("wnd[1]/usr/cmbG_LISTBOX")
        ents = []
        try:
            es = cmb.Entries
            for i in range(es.Count):
                e = es.ElementAt(i) if hasattr(es, "ElementAt") else es(i)
                ents.append((e.Key, str(e.Value).strip()))
        except Exception as e:
            print(f"   [combo entries: {e}]")
        for k, v in ents:
            print(f"   fmt key={k!r} val={v!r}")
        try:
            s.findById("wnd[1]/usr/radRB_OTHERS").select()
        except Exception:
            pass
        xlsx_key = next((k for k, v in ents
                         if "XLSX" in v.upper() or "OFFICE OPEN" in v.upper()), None)
        if xlsx_key is not None:
            cmb.Key = xlsx_key
            print(f"   → combo XLSX key={xlsx_key!r}")
        else:
            print(f"   [aviso] não achei XLSX nas entries; combo atual={cmb.Text.strip()!r}")
        s.findById("wnd[1]").sendVKey(0)     # confirma formato
        time.sleep(1.0)
    except Exception as e:
        print(f"   [fmt popup ausente/erro: {e}]")
    # POPUP 2 — salvar arquivo (path/filename) — diálogo SAP (DY_PATH/DY_FILENAME)
    try:
        s.findById("wnd[1]/usr/ctxtDY_PATH")
    except Exception:
        print("   [export] sem popup de salvar SAP — provável diálogo NATIVO (não-scriptável):")
        do_dump(s)
        # AJ-02-02
        raise RuntimeError("export save popup ausente (provavel dialogo nativo do Windows)")
    save_dir = args.save_dir or os.getcwd()
    fname = args.fname or "ZPPPRD_export_script.xlsx"
    target = os.path.join(save_dir, fname)
    if os.path.exists(target):
        try:
            os.remove(target)                # evita prompt de substituição (é nosso output)
        except Exception:
            pass
    s.findById("wnd[1]/usr/ctxtDY_PATH").Text = save_dir
    s.findById("wnd[1]/usr/ctxtDY_FILENAME").Text = fname
    print(f"   salvando: {target}")
    s.findById("wnd[1]/tbar[0]/btn[0]").press()   # Gerar
    time.sleep(1.5)
    # follow-ups (substituir? / abrir? / aviso) — preferir 'Substituir'; nunca abrir Excel
    for _ in range(3):
        try:
            w = s.findById("wnd[1]")
        except Exception:
            break
        print(f"   follow-up popup: {w.Text!r}")
        pressed = False
        for bid in ("wnd[1]/tbar[0]/btn[11]",):       # Substituir
            try:
                s.findById(bid).press(); pressed = True; break
            except Exception:
                pass
        if not pressed:
            try:
                w.sendVKey(0)                          # Enter (confirma aviso)
            except Exception:
                break
        time.sleep(0.8)
    if os.path.exists(target):
        print(f"   ✅ arquivo gerado: {target} ({os.path.getsize(target)} bytes)")
    else:
        print(f"   ❌ não encontrei {target} — ver se houve diálogo extra.")
        # AJ-02-02 — fim do fluxo: arquivo nao criado e erro classificado em "salvamento".
        raise RuntimeError(f"export: arquivo nao criado em {target}")
    if getattr(args, "kill_excel", False):
        # o &XXL auto-abre o arquivo no Excel. Em vez de delay fixo (frágil), ESPERA o Excel
        # realmente subir (PID novo) e mata só ESSE. O arquivo já está em disco antes disso.
        novos = kill_new_excel(excel_before, wait=20)
        if novos:
            print(f"   [kill-excel] Excel novo detectado e morto (PIDs {sorted(novos)}) — arquivo intacto")
        else:
            print("   [kill-excel] nenhum Excel novo surgiu em 20s (nada a matar)")


def export_via_b(s, args):
    """VIA B — lê a grade via GetCellValue (paginando o ALV virtualizado) e monta o
    .xlsx NO PYTHON (openpyxl). O SAP NÃO grava arquivo => ZERO diálogo de Segurança
    SAPGUI => 100% hands-off. Read-only no SAP."""
    from openpyxl import Workbook
    banner("VIA B — ler grade + montar xlsx no Python (sem I/O de arquivo pelo SAP)")
    if getattr(args, "no_nav", False):
        print("   [--no-nav] lendo a GRADE ATUAL na tela (sem re-navegar/re-aplicar layout)")
    else:
        _close_popups(s)
        navigate(s, args)
    grid = find_grid(s.findById("wnd[0]/usr"))
    if grid is None:
        print("[viab] sem GuiGridView — render falhou."); do_dump(s); return
    total = grid.RowCount
    cols = [c for c in coll(grid.ColumnOrder) if c is not None]
    titles = [col_title(grid, c) or str(c) for c in cols]
    # --csv => header com nomes TÉCNICOS (ColumnOrder); senão xlsx com títulos de exibição
    header = [str(c) for c in cols] if args.csv else titles
    limit = total if not args.rows else min(args.rows, total)
    amostra = "AMOSTRA" if limit < total else "COMPLETO"
    print(f"   grid: {total} linhas x {len(cols)} colunas | lendo {limit} ({amostra})")
    print(f"   header ({'técnico' if args.csv else 'exibição'}): {header}")
    try:
        block = int(grid.VisibleRowCount) or 20
    except Exception:
        block = 20
    t0 = time.time()
    data = []
    r = 0
    while r < limit:
        try:
            grid.firstVisibleRow = r          # materializa o bloco (ALV virtualiza)
        except Exception:
            pass
        end = min(r + block, limit)
        for rr in range(r, end):
            line = []
            for c in cols:
                try:
                    line.append(grid.GetCellValue(rr, c))
                except Exception:
                    line.append("")
            data.append(line)
        r = end
    ncells = len(data) * len(cols)
    out = args.out or ("export.csv" if args.csv else "ZPPPRD_viaB.xlsx")
    if args.csv:
        import csv
        with open(out, "w", newline="", encoding="utf-8") as fh:
            wtr = csv.writer(fh)
            wtr.writerow(header)
            wtr.writerows(data)        # valores PT crus, sem normalizar (pedido do consumidor)
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "ZPPPRD"
        ws.append(header)
        for line in data:
            ws.append(line)
        wb.save(out)
    dt = time.time() - t0
    print(f"   ✅ {'CSV' if args.csv else 'xlsx'} montado NO PYTHON: {out} ({os.path.getsize(out)} bytes)")
    print(f"      {limit} linhas + cabeçalho, {ncells} células lidas em {dt:.1f}s")
    print(f"   >>> nenhuma gravação pelo SAP, nenhum diálogo de Segurança SAPGUI, NENHUM Excel <<<")


def export_clip(s, args):
    """VIA B (clipboard) — seleciona tudo no ALV, copia (1 operação) e LÊ a área de
    transferência no Python (tab-delimitado). Sem gravação pelo SAP => sem diálogo.
    Deve ser MUITO mais rápido que célula-a-célula."""
    import win32clipboard
    from openpyxl import Workbook
    banner("VIA B (CLIPBOARD) — selecionar tudo + copiar + ler clipboard")
    _close_popups(s)
    navigate(s, args)
    grid = find_grid(s.findById("wnd[0]/usr"))
    if grid is None:
        print("[clip] sem grid"); do_dump(s); return
    total = grid.RowCount
    print(f"   grid: {total} linhas x {len(coll(grid.ColumnOrder))} colunas")
    # zera clipboard
    win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.CloseClipboard()
    t0 = time.time()
    try:
        grid.setCurrentCell(-1, "")
        grid.selectAll()
        print("   selectAll() OK")
    except Exception as e:
        print(f"   selectAll falhou ({e}); tentando contextMenu &ALL")
        grid.contextMenu(); grid.selectContextMenuItem("&ALL")
    # sweep de códigos de cópia (só clipboard; NUNCA &PC/&XXL que gravam arquivo)
    codes = [args.ctx_code] if args.ctx_code else \
            ["&CRB", "&CRL", "&CPY", "&COPY_ROW", "&MCOPY", "&XLC", "&COPY"]
    data = ""
    for code in codes:
        try:
            grid.contextMenu()
            grid.selectContextMenuItem(code)
        except Exception as e:
            print(f"   {code}: inválido ({str(e)[-40:-1]})")
            continue
        time.sleep(0.4)
        try:
            s.findById("wnd[1]").sendVKey(0)        # popup eventual
        except Exception:
            pass
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            data = ""
        win32clipboard.CloseClipboard()
        if data and len(data) > 100:
            print(f"   {code}: clipboard PREENCHIDO ({len(data)} chars) ✓")
            break
        print(f"   {code}: clipboard vazio")
    dt = time.time() - t0
    lines = [ln for ln in data.replace("\r\n", "\n").split("\n") if ln != ""]
    print(f"   clipboard: {len(data)} chars, {len(lines)} linhas em {dt:.1f}s")
    if len(lines) < 2:
        print("   [clip] clipboard vazio/insuficiente — código de cópia errado?")
        return
    rows = [ln.split("\t") for ln in lines]
    wb = Workbook(); ws = wb.active; ws.title = "ZPPPRD"
    for r in rows:
        ws.append(r)
    out = args.out or "ZPPPRD_clip.xlsx"
    wb.save(out)
    print(f"   ✅ {out} ({os.path.getsize(out)} bytes) — {len(rows)} linhas (1ª = cabeçalho)")
    print(f"   1ª linha: {rows[0][:6]} ...")
    print("   >>> sem gravação pelo SAP, sem diálogo de Segurança SAPGUI <<<")


def _flush(args, lines):
    if getattr(args, "out", None):
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            print(f"\n[gridcap] salvo em {args.out}")
        except Exception as e:
            print(f"[gridcap] não salvou {args.out}: {e}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list-sessions", action="store_true")
    p.add_argument("--gridcap", action="store_true")
    p.add_argument("--dump", action="store_true")
    p.add_argument("--goto")                      # navega /n<TX> + Enter e dá dump (discovery, sem F8)
    p.add_argument("--iw33")                      # 2b: lê ARBEI+ARBEH de uma ordem no IW33 (display)
    p.add_argument("--genfile", action="store_true")  # testa "Gerar Arquivo" (radP_ARQ)
    p.add_argument("--tx")
    p.add_argument("--set", action="append", default=[])  # "id=valor" (layout/filtros), repetível
    p.add_argument("--no-f8", action="store_true")
    p.add_argument("--export", action="store_true")   # VIA C: export ALV→planilha
    p.add_argument("--viab", action="store_true")     # VIA B: ler grade + montar xlsx no Python
    p.add_argument("--clip", action="store_true")     # VIA B via clipboard (selecionar tudo + copiar)
    p.add_argument("--csv", action="store_true")      # com --viab: grava CSV (headers técnicos), não xlsx
    p.add_argument("--no-nav", dest="no_nav", action="store_true")  # com --viab: lê a grade ATUAL (sem navegar)
    p.add_argument("--rows", type=int, default=0)     # limite de linhas (0 = todas)
    p.add_argument("--ctx-code", dest="ctx_code")     # código do item de menu (&XXL/&PC/&XLS/&XML)
    p.add_argument("--save-dir")
    p.add_argument("--fname")
    p.add_argument("--kill-excel", dest="kill_excel", action="store_true")  # mata Excel após export
    p.add_argument("--out")
    p.add_argument("--conn", type=int, default=0)
    p.add_argument("--sess", type=int, default=0)
    a = p.parse_args()

    bits = struct.calcsize("P") * 8
    print(f"Python {sys.version.split()[0]} | {bits}-bit")
    if bits != 32:
        print("[AVISO] NÃO é 32-bit — COM pode não conectar ao SAP GUI.")
    eng = get_engine()
    print("[OK] ScriptingEngine conectada")

    if a.list_sessions:
        for i in range(eng.Children.Count):
            conn = eng.Children(i)
            for j in range(conn.Children.Count):
                inf = conn.Children(j).Info
                print(f"  conn[{i}] sess[{j}] sys={inf.SystemName} user={inf.User} "
                      f"mandante={inf.Client} tx={inf.Transaction}")
        return

    s = eng.Children(a.conn).Children(a.sess)
    print(f"[OK] sessão {a.conn}/{a.sess} sys={s.Info.SystemName} user={s.Info.User} "
          f"mandante={s.Info.Client} tx={s.Info.Transaction}")

    if a.genfile:                                  # "Gerar Arquivo" (radP_ARQ): campos de arquivo
        # (radL_LOC/P_CAM/P_SOB) só aparecem após um F8 com radP_ARQ marcado. Gera arquivo
        # direto, sem grade/Excel. Aplica os --set 2x (antes e depois do F8 de reveal).
        def apply_sets(verbose=False):
            for kv in (a.set or []):
                k, _, v = kv.partition("=")
                try:
                    if v == "@select":
                        s.findById(k).select()
                    elif v == "@check":
                        s.findById(k).selected = True
                    else:
                        s.findById(k).Text = v
                    if verbose:
                        print(f"   set {k} = {v!r}")
                except Exception as e:
                    if verbose:
                        print(f"   [aviso] set {k}: {str(e)[-45:-1]}")
        s.findById("wnd[0]/tbar[0]/okcd").Text = f"/n{a.tx}"
        s.findById("wnd[0]").sendVKey(0); time.sleep(0.6)
        apply_sets()                               # passada 1 (radP_ARQ+filtros; campos de arquivo ainda não existem)
        s.findById("wnd[0]").sendVKey(8); time.sleep(0.9)   # F8 → revela radL_LOC/P_CAM/P_SOB
        print(f"   após reveal: {statusbar(s)}")
        apply_sets(verbose=True)                   # passada 2 (agora radL_LOC/P_CAM/P_SOB existem)
        if not a.no_f8:
            s.findById("wnd[0]").sendVKey(8); time.sleep(1.5)   # F8 → gera o arquivo
        print(f"   após gerar: tx={s.Info.Transaction} | {statusbar(s)}")
        try:
            s.findById("wnd[1]")
            print("   [popup] dump:"); walk(s.findById("wnd[1]/usr"))
        except Exception:
            pass
        return
    if a.iw33:                                     # 2b: lê unidade do trabalho planejado (ARBEH) no IW33 (display, sem lock)
        base = ("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/"
                "tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subAVO:SAPLCOI0:0310/")
        s.findById("wnd[0]/tbar[0]/okcd").Text = "/niw33"
        s.findById("wnd[0]").sendVKey(0); time.sleep(0.6)
        s.findById("wnd[0]/usr/ctxtCAUFVD-AUFNR").Text = a.iw33
        s.findById("wnd[0]").sendVKey(0); time.sleep(1.0)
        for _ in range(3):                         # popup "Exibir log?" → Não (btnSPOP-OPTION2)
            try:
                s.findById("wnd[1]")
            except Exception:
                break
            for b in ("wnd[1]/usr/btnSPOP-OPTION2", "wnd[1]/tbar[0]/btn[12]"):
                try:
                    s.findById(b).press(); break
                except Exception:
                    pass
            time.sleep(0.3)
        banner(f"IW33 ordem {a.iw33} — campo de trabalho da operação + unidade")
        for fld in ("txtAFVGD-ARBEI", "ctxtAFVGD-ARBEH", "txtAFVGD-ARBEH",
                    "cmbAFVGD-ARBEH", "lblAFVGD-ARBEH"):
            try:
                print(f"   {fld} = {s.findById(base + fld).Text!r}")
            except Exception:
                print(f"   {fld} = (n/a)")
        do_dump(s)
        return
    if a.goto:                                    # discovery read-only: navega e despeja a tela
        s.findById("wnd[0]/tbar[0]/okcd").Text = f"/n{a.goto}"
        s.findById("wnd[0]").sendVKey(0)
        time.sleep(0.6)
        do_dump(s); return
    if a.dump:
        do_dump(s); return
    if a.export:
        export_grid(s, a); return
    if a.viab:
        export_via_b(s, a); return
    if a.clip:
        export_clip(s, a); return
    if a.gridcap:
        gridcap(s, a); return
    print("Nada a fazer. Use --list-sessions | --gridcap --out X.txt | --dump")


if __name__ == "__main__":
    main()
