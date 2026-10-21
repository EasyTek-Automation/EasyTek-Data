# src/utils/equipment_names.py

"""
Fonte única do mapa código→nome de exibição dos equipamentos.

Vive num módulo próprio, sem dependências, porque o mapa é um dado de domínio
consultado por partes do sistema que não deveriam arrastar pandas junto (o
cadastro de gatilhos da Análise de Falhas, por exemplo). Antes morava em
`zpp_kpi_calculator`, que importa pandas no topo — quem só quisesse traduzir
"LONGI002" para "LCL-4,5" pagava o import inteiro, e num ambiente sem pandas a
tradução falhava em silêncio e devolvia o gatilho errado.

`zpp_kpi_calculator` reexporta `EQUIPAMENTO_NOMES` daqui, então todos os
importadores antigos seguem funcionando.
"""

# Código do centro de trabalho (SAP/ZPP) → nome usado na planta e na interface.
# É esta a chave do cadastro `maintenance_breakdown_thresholds`.
EQUIPAMENTO_NOMES = {
    "LONGI001": "LCL-08",
    "LONGI002": "LCL-4,5",
    "PRENS001": "PRENSA-01",
    "PRENS002": "PRENSA-02",
    "TRANS001": "LCT-08",
    "TRANS002": "LCT-16",
    "TRANS003": "LCT-2,5",
    "DECAP001": "Decapado",
    "SOLDA001": "LWB",
}
