# -*- coding: utf-8 -*-
"""Trabalho `hh` — coleta de Hora-Homem (planejado IW37 + realizado IW47, planta BR02).

Dois jobs do daemon (`hh_planejado`, `hh_realizado`) promovidos do protótipo
`exploratorio/iw_fastexport.py`. Cada job exporta sua tela via ALV nativo (&XXL),
agrega por operação (AUFNR+VORNR) e grava snapshot atômico na sua collection-fonte
(`sap_hh_planejado` / `sap_hh_realizado`). A união planejado×realizado e a agregação
por ordem acontecem na LEITURA (webapp `hh_data.py`) — não na coleta — porque os dois
jobs são independentes (DS-02: falhas isoláveis). Read-only no SAP.

SDD: .dev-docs/projects/hh-management/ (fase 06, Bloco B1).
"""
