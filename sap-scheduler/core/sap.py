# -*- coding: utf-8 -*-
"""Conexão com a sessão SAP GUI já aberta (read-only — o daemon só DIRIGE a sessão)."""
from __future__ import annotations


def conectar_sessao(conn: int = 0, sess: int = 0):
    """Retorna a GuiSession (conn/sess). Levanta RuntimeError se não conectar."""
    import win32com.client  # noqa: PLC0415
    eng = None
    try:
        eng = win32com.client.GetObject("SAPGUI").GetScriptingEngine
    except Exception:
        try:
            wr = win32com.client.Dispatch("SapROTWr.SapROTWrapper")
            eng = wr.GetROTEntry("SAPGUI").GetScriptingEngine
        except Exception as e:
            raise RuntimeError(f"nao conectou ao SAP GUI Scripting: {e}")
    if eng is None:
        raise RuntimeError("SAP GUI Scripting indisponivel (SAP logado? scripting habilitado?)")
    return eng.Children(conn).Children(sess)
