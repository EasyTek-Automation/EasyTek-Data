"""Feature 'Controle de Custo de Manutenção' (SDD CostsManagement).

Pacote autocontido (IN-05): hierarquia de contas, esquema/indices Mongo e loader
de seed. A metade de consumo (aba Dash, leitura) le exclusivamente do MongoDB —
a fronteira entre fonte (CSV agora / SAP depois) e consumo e o proprio banco
(DS-01). Destacavel depois sem tocar as demais abas de indicators-v2.
"""
