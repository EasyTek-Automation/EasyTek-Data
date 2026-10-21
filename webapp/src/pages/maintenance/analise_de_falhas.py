# src/pages/maintenance/analise_de_falhas.py

"""
Página "Análise de Falhas" (/maintenance/analise-de-falhas).

Pareto de paradas de manutenção — ranqueia o que mais parou a planta,
ponderado pelo tempo de parada apontado (`duracao_min` de ZPP_Paradas).

Front replica o visual E os mecanismos da indicators-v2: switcher de idioma
PT/ES/EN (bandeiras + store), filtros em dois estágios (Aplicar/Atualizar
escrevem num store; callback de render reage ao store, disparado também por
`url.pathname`). Dados vêm dos readers de `utils/zpp_kpi_calculator`.

IMPORTANTE: todos os ids usam prefixo `af-` para NÃO colidir com os ~76
callbacks globais da indicators-v2 (inclusive o tipo de pattern-id das
bandeiras é `af-lang-btn`, distinto do `v2-lang-btn`).

Acesso: perfil manutenção nível ≥ 2.
"""

import base64

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from src.utils.failure_events import (
    FAIXAS_DURACAO, GATILHO_MODO_ACIMA, GATILHO_MODO_TODAS, ano_padrao, anos_disponiveis,
)
from src.utils.zpp_kpi_calculator import BREAKDOWN_CODES

ACCENT = "#c0392b"        # vermelho — "falhas"
ACCENT_EQUIP = "#fd7e14"  # laranja — Pareto por equipamento

# ---------------------------------------------------------------------------
# i18n — dicionário de traduções (mesma ideia do TRANS da indicators-v2)
# ---------------------------------------------------------------------------
TRANS = {
    "pt": {
        "title": "Análise de Falhas",
        "subtitle": "Pareto de paradas de manutenção — ponderado pelo tempo de parada.",
        "btn_refresh": "Atualizar", "btn_filters": "Filtros", "btn_sendmail": "Enviar E-mail",
        "mail_subject": "[AMG] Resumo de Paradas — Análise de Falhas",
        "mail_title": "Resumo de Paradas",
        "mail_ok": "Resumo enviado por e-mail com sucesso.",
        "mail_fail": "Falha ao enviar o e-mail. Verifique a configuração SMTP.",
        "mail_empty": "Carregue os dados antes de enviar (nenhum resumo disponível).",
        "btn_export": "Exportar", "btn_apply": "Aplicar",
        "filter_period": "Período", "filter_year": "Ano de referência",
        "filter_range": "Período personalizado", "filter_equip": "Equipamentos",
        "filter_codes": "Códigos de avaria",
        "filter_duracao": "Duração da parada",
        "duracao_placeholder": "(todas as faixas)",
        "filter_gatilho": "Paradas exibidas",
        "gatilho_acima": "Somente acima do gatilho",
        "gatilho_todas": "Todas as paradas",
        "gatilho_hint": "Vale apenas na aba Análise de Paradas.",
        "paradas_vazio_gatilho": ("Nenhuma parada atinge o gatilho do equipamento no período. "
                                  "Use 'Todas as paradas' para ver as demais."),
        "col_gatilho": "Gatilho",
        # ── Gestão das Análises (aba nova) ────────────────────────
        "tab_gestao": "📈 Gestão das Análises",
        "g_title": "Gestão das Análises",
        "g_sub": ("O que a manutenção fez com as falhas que analisou — nos últimos "
                  "12 meses. Clique num mês para olhar só ele."),
        "g_kpi_eleg": "Paradas elegíveis",
        "g_kpi_eleg_sub": "acima do gatilho do equipamento",
        "g_kpi_analisadas": "Analisadas",
        "g_kpi_analisadas_sub": "aceitas pelo gestor",
        "g_kpi_fila": "Aguardando aceite",
        "g_kpi_fila_sub": "entregues, esperando o gestor",
        "g_kpi_plano": "Com plano de ação",
        "g_kpi_plano_sub": "análises com ação escrita",
        "g_kpi_vencidas": "Ações vencidas",
        "g_kpi_vencidas_sub": "passaram do prazo e não foram feitas",
        "g_kpi_voltaram": "Falhas que voltaram",
        "g_kpi_voltaram_sub": "reapareceram em até 3 meses",
        "g_graf_title": "Mês a mês",
        "g_graf_sub": ("Quanto apareceu, quanto foi analisado e quanto virou ação. "
                       "Clique numa barra para pôr o mês em foco."),
        "g_serie_eleg": "Paradas elegíveis",
        "g_serie_analisadas": "Analisadas",
        "g_serie_plano": "Com plano de ação",
        "g_mes_andamento": "mês em andamento",
        "g_foco": "Mostrando",
        "g_foco_limpar": "ver o período inteiro",
        "g_de": "de",
        "g_mais_antiga": "a mais antiga há {n} dias",
        "g_fila_todos_meses": "toda a fila, de qualquer mês",
        "g_vazio_sem_parada": "Nenhuma parada acima do gatilho neste mês.",
        "g_vazio_sem_analise": "Nenhuma das {n} paradas foi analisada.",
        "g_vazio_sem_dado": "Sem dados para este mês.",
        "g_sem_dado_curto": "sem dados",
        "g_vazio_fila": "Nada aguardando aceite.",
        "g_erro": "Não foi possível consultar os dados agora.",
        # Unidades com singular e plural: "faltam 1 meses" e "1 causas" saltam aos
        # olhos de quem lê a tela todo dia.
        "g_un_dia": "dia", "g_un_dias": "dias",
        "g_un_mes": "mês", "g_un_meses": "meses",
        "g_un_parada": "parada", "g_un_paradas": "paradas",
        "g_un_acao": "ação", "g_un_acoes": "ações",
        "g_un_causa": "causa", "g_un_causas": "causas",
        # Gestão das Análises — tabelas (bloco C)
        "g_resp_title": "Por responsável",
        "g_resp_sub": "Quem está com o quê, no período em foco.",
        "g_col_pessoa": "Pessoa",
        "g_col_acoes": "Ações",
        "g_col_vencidas": "Vencidas",
        "g_col_em_aberto": "Em aberto",
        "g_col_feitas": "Feitas",
        "g_col_total": "Total",
        "g_resp_nota": ("Ação com mais de um responsável conta para cada um — por isso a "
                        "soma passa do total de ações."),
        "g_sem_responsavel": "sem responsável",
        "g_resp_vazio": "Nenhuma ação escrita no período.",
        "g_aten_title": "Precisa de atenção",
        "g_aten_sub": "Pendências concretas. Clique para abrir a análise.",
        "g_aten_vazio": "Nada precisando de atenção.",
        "g_aten_filtro": "Mostrando só as ações de",
        "g_aten_limpar": "ver todas",
        "g_mot_vencida": "venceu há {n} {u}",
        "g_mot_sem_resp": "sem responsável",
        "g_mot_sem_prazo": "sem prazo",
        "g_mot_elaboracao": "análise aberta, nunca entregue",
        "g_mot_devolvida": "devolvida",
        "g_aten_mais": "e mais {n}",
        "g_aten_ver_todas": "ver todas",
        # Gestão das Análises — fila e reincidência (blocos E e F)
        "g_fila_title": "Aguardando aceite",
        "g_fila_sub": "Entregues, esperando o gestor. Clique para abrir e julgar.",
        "g_fila_nota": "Esta lista ignora o mês em foco — pendência não tem mês.",
        "g_fila_col_equip": "Equipamento",
        "g_fila_col_mes": "Mês",
        "g_fila_col_falha": "Falha",
        "g_fila_col_por": "Entregue por",
        "g_fila_col_espera": "Esperando",
        "g_fila_col_conteudo": "Conteúdo",
        "g_fila_dias": "há {n} {u}",
        "g_fila_hoje": "hoje",
        "g_fila_conteudo": "{c} {uc} · {a} {ua}",
        "g_fila_devolvida": "devolvida {n}×",
        "g_reinc_title": "A falha voltou?",
        "g_reinc_sub": "Único número que fala de resultado, e não de esforço.",
        "g_reinc_vazio": "Nenhuma análise em observação no período.",
        "g_reinc_voltou": "voltou em {m}",
        "g_reinc_observando": "ainda observando",
        "g_reinc_faltam": "faltando {n} {u}",
        "g_reinc_repetiu": "{min} min · {d} {ud} · {v} {uv}",
        "g_reinc_depois": "depois do aceite",
        "g_reinc_antes": "antes do aceite",
        "g_reinc_acoes": "hoje: {a} {ua}, {f} feitas",
        "tab_pareto": "📊 Pareto", "tab_dados": "📋 Dados",
        "tab_paradas": "🔧 Análise de Paradas",
        "paradas_title": "Paradas do período",
        "paradas_sub": ("Cada linha é uma falha do mês — apontamentos do mesmo "
                        "equipamento, causa e relato ao longo do mês são uma só parada. "
                        "A análise vale para o mês; o gatilho conta o acumulado."),
        "paradas_page_size": "Registros por página",
        "col_mes": "Mês", "col_dias": "Dias", "col_apont": "Apont.",
        "card_paradas": "paradas", "card_pendentes": "sem análise",
        "card_analisado": "tudo analisado", "meses_ano": "Ano",
        "voltar_meses": "Voltar aos meses",
        "slides_btn": "Exportar slides do mês", "slides_gerando": "Gerando…",
        "slides_vazio": "Nenhuma análise neste mês — nada a exportar.",
        "slides_erro": "Não foi possível gerar os slides do mês.",
        "col_duracao": "Duração", "col_analise": "Análise", "col_abrir": "Abrir Diagrama de Ishikawa",
        "btn_abrir": "Abrir diagrama", "sem_causa": "Causa não informada",
        "paradas_vazio": "Nenhuma parada de avaria no período.",
        "paradas_erro": "Não foi possível carregar as paradas. Verifique a conexão com o banco.",
        "an_aberta": "Em andamento", "an_concluida": "Concluída", "an_nenhuma": "—",
        "kpi_total_title": "Tempo total de parada", "kpi_total_sub": "Soma de duração (min)",
        "kpi_count_title": "Nº de paradas", "kpi_count_sub": "Eventos de avaria no período",
        "kpi_top_title": "Maior ofensor", "kpi_top_sub": "Causa que mais parou",
        "causa_title": "Pareto por Causa",
        "causa_sub": "Ordenado por tempo de parada · % acumulada + marca 80%",
        "equip_title": "Pareto por Equipamento",
        "equip_sub": "Tempo de parada por centro de trabalho",
        "table_title": "Top paradas do período",
        "period_year": "Por ano", "period_last12": "Últimos 12 meses", "period_custom": "Personalizado",
        "equip_placeholder": "(todos)", "beta_badge": "BETA",
        "beta_tooltip": "Página em validação.",
        "empty": "Sem dados no período", "loading": "Carregando…",
        "bars_name": "Tempo (min)", "cum_name": "% acumulada",
        "y_time": "Tempo de parada (min)", "y_pct": "% acumulada",
        "col_num": "#", "col_dt": "Data/Hora", "col_equip": "Equipamento",
        "col_cause": "Causa", "col_dur": "Duração (min)", "col_desc": "Descrição",
    },
    "es": {
        "title": "Análisis de Fallas",
        "subtitle": "Pareto de paradas de mantenimiento — ponderado por el tiempo de parada.",
        "btn_refresh": "Actualizar", "btn_filters": "Filtros", "btn_sendmail": "Enviar Correo",
        "mail_subject": "[AMG] Resumen de Paradas — Análisis de Fallas",
        "mail_title": "Resumen de Paradas",
        "mail_ok": "Resumen enviado por correo con éxito.",
        "mail_fail": "Fallo al enviar el correo. Verifique la configuración SMTP.",
        "mail_empty": "Cargue los datos antes de enviar (ningún resumen disponible).",
        "btn_export": "Exportar", "btn_apply": "Aplicar",
        "filter_period": "Período", "filter_year": "Año de referencia",
        "filter_range": "Período personalizado", "filter_equip": "Equipos",
        "filter_codes": "Códigos de avería",
        "filter_duracao": "Duración de la parada",
        "duracao_placeholder": "(todos los rangos)",
        "filter_gatilho": "Paradas mostradas",
        "gatilho_acima": "Solo por encima del gatillo",
        "gatilho_todas": "Todas las paradas",
        "gatilho_hint": "Solo se aplica en la pestaña Análisis de Paradas.",
        "paradas_vazio_gatilho": ("Ninguna parada alcanza el gatillo del equipo en el período. "
                                  "Use 'Todas las paradas' para ver las demás."),
        "col_gatilho": "Gatillo",
        # ── Gestão das Análises (aba nova) ────────────────────────
        "tab_gestao": "📈 Gestión de Análisis",
        "g_title": "Gestión de los Análisis",
        "g_sub": ("Qué hizo mantenimiento con las fallas que analizó — en los últimos "
                  "12 meses. Haga clic en un mes para ver solo ese mes."),
        "g_kpi_eleg": "Paradas elegibles",
        "g_kpi_eleg_sub": "por encima del umbral del equipo",
        "g_kpi_analisadas": "Analizadas",
        "g_kpi_analisadas_sub": "aceptadas por el gestor",
        "g_kpi_fila": "Esperando aceptación",
        "g_kpi_fila_sub": "entregadas, esperando al gestor",
        "g_kpi_plano": "Con plan de acción",
        "g_kpi_plano_sub": "análisis con acción escrita",
        "g_kpi_vencidas": "Acciones vencidas",
        "g_kpi_vencidas_sub": "pasaron del plazo y no se hicieron",
        "g_kpi_voltaram": "Fallas que volvieron",
        "g_kpi_voltaram_sub": "reaparecieron en hasta 3 meses",
        "g_graf_title": "Mes a mes",
        "g_graf_sub": ("Cuánto apareció, cuánto se analizó y cuánto se convirtió en acción. "
                       "Haga clic en una barra para enfocar el mes."),
        "g_serie_eleg": "Paradas elegibles",
        "g_serie_analisadas": "Analizadas",
        "g_serie_plano": "Con plan de acción",
        "g_mes_andamento": "mes en curso",
        "g_foco": "Mostrando",
        "g_foco_limpar": "ver todo el período",
        "g_de": "de",
        "g_mais_antiga": "la más antigua hace {n} días",
        "g_fila_todos_meses": "toda la fila, de cualquier mes",
        "g_vazio_sem_parada": "Ninguna parada por encima del umbral en este mes.",
        "g_vazio_sem_analise": "Ninguna de las {n} paradas fue analizada.",
        "g_vazio_sem_dado": "Sin datos para este mes.",
        "g_sem_dado_curto": "sin datos",
        "g_vazio_fila": "Nada esperando aceptación.",
        "g_erro": "No fue posible consultar los datos ahora.",
        "g_un_dia": "día", "g_un_dias": "días",
        "g_un_mes": "mes", "g_un_meses": "meses",
        "g_un_parada": "parada", "g_un_paradas": "paradas",
        "g_un_acao": "acción", "g_un_acoes": "acciones",
        "g_un_causa": "causa", "g_un_causas": "causas",
        # Gestão das Análises — tabelas (bloco C)
        "g_resp_title": "Por responsable",
        "g_resp_sub": "Quién tiene qué, en el período en foco.",
        "g_col_pessoa": "Persona",
        "g_col_acoes": "Acciones",
        "g_col_vencidas": "Vencidas",
        "g_col_em_aberto": "Abiertas",
        "g_col_feitas": "Hechas",
        "g_col_total": "Total",
        "g_resp_nota": ("Una acción con más de un responsable cuenta para cada uno — por eso "
                        "la suma pasa del total de acciones."),
        "g_sem_responsavel": "sin responsable",
        "g_resp_vazio": "Ninguna acción escrita en el período.",
        "g_aten_title": "Necesita atención",
        "g_aten_sub": "Pendencias concretas. Haga clic para abrir el análisis.",
        "g_aten_vazio": "Nada necesitando atención.",
        "g_aten_filtro": "Mostrando solo las acciones de",
        "g_aten_limpar": "ver todas",
        "g_mot_vencida": "venció hace {n} {u}",
        "g_mot_sem_resp": "sin responsable",
        "g_mot_sem_prazo": "sin plazo",
        "g_mot_elaboracao": "análisis abierto, nunca entregado",
        "g_mot_devolvida": "devuelto",
        "g_aten_mais": "y {n} más",
        "g_aten_ver_todas": "ver todas",
        # Gestão das Análises — fila e reincidência (blocos E e F)
        "g_fila_title": "Esperando aceptación",
        "g_fila_sub": "Entregados, esperando al gestor. Haga clic para abrir y juzgar.",
        "g_fila_nota": "Esta lista ignora el mes en foco — una pendencia no tiene mes.",
        "g_fila_col_equip": "Equipo",
        "g_fila_col_mes": "Mes",
        "g_fila_col_falha": "Falla",
        "g_fila_col_por": "Entregado por",
        "g_fila_col_espera": "Esperando",
        "g_fila_col_conteudo": "Contenido",
        "g_fila_dias": "hace {n} {u}",
        "g_fila_hoje": "hoy",
        "g_fila_conteudo": "{c} {uc} · {a} {ua}",
        "g_fila_devolvida": "devuelto {n}×",
        "g_reinc_title": "¿La falla volvió?",
        "g_reinc_sub": "Único número que habla de resultado, y no de esfuerzo.",
        "g_reinc_vazio": "Ningún análisis en observación en el período.",
        "g_reinc_voltou": "volvió en {m}",
        "g_reinc_observando": "aún observando",
        "g_reinc_faltam": "faltando {n} {u}",
        "g_reinc_repetiu": "{min} min · {d} {ud} · {v} {uv}",
        "g_reinc_depois": "después de la aceptación",
        "g_reinc_antes": "antes de la aceptación",
        "g_reinc_acoes": "hoy: {a} {ua}, {f} hechas",
        "tab_pareto": "📊 Pareto", "tab_dados": "📋 Datos",
        "tab_paradas": "🔧 Análisis de Paradas",
        "paradas_title": "Paradas del período",
        "paradas_sub": ("Cada línea es una falla del mes — los registros del mismo "
                        "equipo, causa y relato durante el mes son una sola parada. "
                        "El análisis vale para el mes; el umbral cuenta el acumulado."),
        "paradas_page_size": "Registros por página",
        "col_mes": "Mes", "col_dias": "Días", "col_apont": "Apunt.",
        "card_paradas": "paradas", "card_pendentes": "sin análisis",
        "card_analisado": "todo analizado", "meses_ano": "Año",
        "voltar_meses": "Volver a los meses",
        "slides_btn": "Exportar diapositivas del mes", "slides_gerando": "Generando…",
        "slides_vazio": "Ningún análisis en este mes — nada que exportar.",
        "slides_erro": "No fue posible generar las diapositivas del mes.",
        "col_duracao": "Duración", "col_analise": "Análisis", "col_abrir": "Abrir Diagrama de Ishikawa",
        "btn_abrir": "Abrir diagrama", "sem_causa": "Causa no informada",
        "paradas_vazio": "Ninguna parada de avería en el período.",
        "paradas_erro": "No fue posible cargar las paradas. Verifique la conexión con la base de datos.",
        "an_aberta": "En curso", "an_concluida": "Concluida", "an_nenhuma": "—",
        "kpi_total_title": "Tiempo total de parada", "kpi_total_sub": "Suma de duración (min)",
        "kpi_count_title": "N.º de paradas", "kpi_count_sub": "Eventos de avería en el período",
        "kpi_top_title": "Mayor ofensor", "kpi_top_sub": "Causa que más paró",
        "causa_title": "Pareto por Causa",
        "causa_sub": "Ordenado por tiempo de parada · % acumulado + marca 80%",
        "equip_title": "Pareto por Equipo",
        "equip_sub": "Tiempo de parada por centro de trabajo",
        "table_title": "Top paradas del período",
        "period_year": "Por año", "period_last12": "Últimos 12 meses", "period_custom": "Personalizado",
        "equip_placeholder": "(todos)", "beta_badge": "BETA",
        "beta_tooltip": "Página en validación.",
        "empty": "Sin datos en el período", "loading": "Cargando…",
        "bars_name": "Tiempo (min)", "cum_name": "% acumulado",
        "y_time": "Tiempo de parada (min)", "y_pct": "% acumulado",
        "col_num": "#", "col_dt": "Fecha/Hora", "col_equip": "Equipo",
        "col_cause": "Causa", "col_dur": "Duración (min)", "col_desc": "Descripción",
    },
    "en": {
        "title": "Failure Analysis",
        "subtitle": "Maintenance stoppage Pareto — weighted by stoppage time.",
        "btn_refresh": "Refresh", "btn_filters": "Filters", "btn_sendmail": "Send Mail",
        "mail_subject": "[AMG] Stoppage Summary — Failure Analysis",
        "mail_title": "Stoppage Summary",
        "mail_ok": "Summary sent by e-mail successfully.",
        "mail_fail": "Failed to send e-mail. Check the SMTP configuration.",
        "mail_empty": "Load the data before sending (no summary available).",
        "btn_export": "Export", "btn_apply": "Apply",
        "filter_period": "Period", "filter_year": "Reference year",
        "filter_range": "Custom period", "filter_equip": "Equipment",
        "filter_codes": "Breakdown codes",
        "filter_duracao": "Stoppage duration",
        "duracao_placeholder": "(all ranges)",
        "filter_gatilho": "Stoppages shown",
        "gatilho_acima": "Only above threshold",
        "gatilho_todas": "All stoppages",
        "gatilho_hint": "Applies to the Stoppage Analysis tab only.",
        "paradas_vazio_gatilho": ("No stoppage reaches the equipment threshold in the period. "
                                  "Use 'All stoppages' to see the rest."),
        "col_gatilho": "Threshold",
        # ── Gestão das Análises (aba nova) ────────────────────────
        "tab_gestao": "📈 Analysis Management",
        "g_title": "Analysis Management",
        "g_sub": ("What maintenance did with the failures it analysed — over the last "
                  "12 months. Click a month to focus on it."),
        "g_kpi_eleg": "Eligible stoppages",
        "g_kpi_eleg_sub": "above the equipment threshold",
        "g_kpi_analisadas": "Analysed",
        "g_kpi_analisadas_sub": "accepted by the manager",
        "g_kpi_fila": "Awaiting acceptance",
        "g_kpi_fila_sub": "submitted, waiting for the manager",
        "g_kpi_plano": "With action plan",
        "g_kpi_plano_sub": "analyses with a written action",
        "g_kpi_vencidas": "Overdue actions",
        "g_kpi_vencidas_sub": "past due and not done",
        "g_kpi_voltaram": "Failures that came back",
        "g_kpi_voltaram_sub": "reappeared within 3 months",
        "g_graf_title": "Month by month",
        "g_graf_sub": ("How much came up, how much was analysed and how much became action. "
                       "Click a bar to focus that month."),
        "g_serie_eleg": "Eligible stoppages",
        "g_serie_analisadas": "Analysed",
        "g_serie_plano": "With action plan",
        "g_mes_andamento": "month in progress",
        "g_foco": "Showing",
        "g_foco_limpar": "see the whole period",
        "g_de": "of",
        "g_mais_antiga": "the oldest {n} days ago",
        "g_fila_todos_meses": "the whole queue, any month",
        "g_vazio_sem_parada": "No stoppage above the threshold this month.",
        "g_vazio_sem_analise": "None of the {n} stoppages were analysed.",
        "g_vazio_sem_dado": "No data for this month.",
        "g_sem_dado_curto": "no data",
        "g_vazio_fila": "Nothing awaiting acceptance.",
        "g_erro": "Could not query the data right now.",
        "g_un_dia": "day", "g_un_dias": "days",
        "g_un_mes": "month", "g_un_meses": "months",
        "g_un_parada": "stoppage", "g_un_paradas": "stoppages",
        "g_un_acao": "action", "g_un_acoes": "actions",
        "g_un_causa": "cause", "g_un_causas": "causes",
        # Gestão das Análises — tabelas (bloco C)
        "g_resp_title": "By owner",
        "g_resp_sub": "Who has what, in the period in focus.",
        "g_col_pessoa": "Person",
        "g_col_acoes": "Actions",
        "g_col_vencidas": "Overdue",
        "g_col_em_aberto": "Open",
        "g_col_feitas": "Done",
        "g_col_total": "Total",
        "g_resp_nota": ("An action with more than one owner counts for each of them — that is "
                        "why the sum exceeds the total number of actions."),
        "g_sem_responsavel": "no owner",
        "g_resp_vazio": "No action written in the period.",
        "g_aten_title": "Needs attention",
        "g_aten_sub": "Concrete pending items. Click to open the analysis.",
        "g_aten_vazio": "Nothing needing attention.",
        "g_aten_filtro": "Showing only the actions of",
        "g_aten_limpar": "see all",
        "g_mot_vencida": "overdue by {n} {u}",
        "g_mot_sem_resp": "no owner",
        "g_mot_sem_prazo": "no due date",
        "g_mot_elaboracao": "analysis open, never submitted",
        "g_mot_devolvida": "returned",
        "g_aten_mais": "and {n} more",
        "g_aten_ver_todas": "see all",
        # Gestão das Análises — fila e reincidência (blocos E e F)
        "g_fila_title": "Awaiting acceptance",
        "g_fila_sub": "Submitted, waiting for the manager. Click to open and judge.",
        "g_fila_nota": "This list ignores the month in focus — a pending item has no month.",
        "g_fila_col_equip": "Equipment",
        "g_fila_col_mes": "Month",
        "g_fila_col_falha": "Failure",
        "g_fila_col_por": "Submitted by",
        "g_fila_col_espera": "Waiting",
        "g_fila_col_conteudo": "Content",
        "g_fila_dias": "{n} {u} ago",
        "g_fila_hoje": "today",
        "g_fila_conteudo": "{c} {uc} · {a} {ua}",
        "g_fila_devolvida": "returned {n}×",
        "g_reinc_title": "Did the failure come back?",
        "g_reinc_sub": "The only number about results, not effort.",
        "g_reinc_vazio": "No analysis under observation in the period.",
        "g_reinc_voltou": "came back in {m}",
        "g_reinc_observando": "still observing",
        "g_reinc_faltam": "{n} {u} to go",
        "g_reinc_repetiu": "{min} min · {d} {ud} · {v} {uv}",
        "g_reinc_depois": "after acceptance",
        "g_reinc_antes": "before acceptance",
        "g_reinc_acoes": "today: {a} {ua}, {f} done",
        "tab_pareto": "📊 Pareto", "tab_dados": "📋 Data",
        "tab_paradas": "🔧 Stoppage Analysis",
        "paradas_title": "Stoppages in the period",
        "paradas_sub": ("Each row is a monthly failure — records for the same equipment, "
                        "cause and report across the month are one stoppage. "
                        "The analysis covers the month; the threshold counts the total."),
        "paradas_page_size": "Rows per page",
        "col_mes": "Month", "col_dias": "Days", "col_apont": "Entries",
        "card_paradas": "stoppages", "card_pendentes": "no analysis",
        "card_analisado": "all analyzed", "meses_ano": "Year",
        "voltar_meses": "Back to months",
        "slides_btn": "Export month slides", "slides_gerando": "Generating…",
        "slides_vazio": "No analysis in this month — nothing to export.",
        "slides_erro": "Could not generate the month slides.",
        "col_duracao": "Duration", "col_analise": "Analysis", "col_abrir": "Open Ishikawa Diagram",
        "btn_abrir": "Open diagram", "sem_causa": "Cause not informed",
        "paradas_vazio": "No breakdown stoppages in the period.",
        "paradas_erro": "Could not load the stoppages. Check the database connection.",
        "an_aberta": "In progress", "an_concluida": "Completed", "an_nenhuma": "—",
        "kpi_total_title": "Total stoppage time", "kpi_total_sub": "Sum of duration (min)",
        "kpi_count_title": "No. of stoppages", "kpi_count_sub": "Breakdown events in the period",
        "kpi_top_title": "Top offender", "kpi_top_sub": "Cause with most downtime",
        "causa_title": "Pareto by Cause",
        "causa_sub": "Sorted by stoppage time · cumulative % + 80% marker",
        "equip_title": "Pareto by Equipment",
        "equip_sub": "Stoppage time by work center",
        "table_title": "Top stoppages of the period",
        "period_year": "By year", "period_last12": "Last 12 months", "period_custom": "Custom",
        "equip_placeholder": "(all)", "beta_badge": "BETA",
        "beta_tooltip": "Page under validation.",
        "empty": "No data in the period", "loading": "Loading…",
        "bars_name": "Time (min)", "cum_name": "cumulative %",
        "y_time": "Stoppage time (min)", "y_pct": "cumulative %",
        "col_num": "#", "col_dt": "Date/Time", "col_equip": "Equipment",
        "col_cause": "Cause", "col_dur": "Duration (min)", "col_desc": "Description",
    },
}

_PT = TRANS["pt"]

# Bandeiras SVG inline (idênticas às da indicators-v2)
_FLAG_SVGS = {
    "pt": '''<svg viewBox="0 0 60 42" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="42" fill="#009c3b"/>
        <polygon points="30,5 55,21 30,37 5,21" fill="#ffdf00"/>
        <circle cx="30" cy="21" r="8.5" fill="#002776"/>
        <path d="M22,21 a8,8 0 0 1 16,0" stroke="#fff" stroke-width="1.4" fill="none"/>
    </svg>''',
    "es": '''<svg viewBox="0 0 60 42" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="11" fill="#aa151b"/>
        <rect y="11" width="60" height="20" fill="#f1bf00"/>
        <rect y="31" width="60" height="11" fill="#aa151b"/>
    </svg>''',
    "en": '''<svg viewBox="0 0 60 42" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="42" fill="#012169"/>
        <path d="M0,0 L60,42 M60,0 L0,42" stroke="#fff" stroke-width="5"/>
        <rect x="25" width="10" height="42" fill="#fff"/>
        <rect y="16" width="60" height="10" fill="#fff"/>
        <rect x="27" width="6" height="42" fill="#c8102e"/>
        <rect y="18" width="60" height="6" fill="#c8102e"/>
    </svg>''',
}


def _lang_switcher():
    """3 bandeiras SVG inline (PT/ES/EN) + badge BETA — pattern-id `af-lang-btn`."""
    flags = [("pt", "Português"), ("es", "Español"), ("en", "English")]
    return html.Div(
        [
            *[
                html.Button(
                    html.Img(
                        src="data:image/svg+xml;base64," + base64.b64encode(_FLAG_SVGS[c].encode()).decode(),
                        alt=t,
                        style={"width": "28px", "height": "20px", "borderRadius": "3px",
                               "boxShadow": "0 1px 3px rgba(0,0,0,0.2)"},
                    ),
                    id={"type": "af-lang-btn", "lang": c},
                    title=t, n_clicks=0, className="v2-lang-flag",
                ) for c, t in flags
            ],
            html.Span("BETA", className="v2-beta-badge", title="Beta"),
        ],
        className="d-flex align-items-center gap-2 mb-2 v2-lang-switcher",
    )


def _blank_fig(height=340, msg=None):
    """Figura Plotly vazia com placeholder — figura inicial dos gráficos."""
    fig = go.Figure()
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        annotations=[dict(text=msg or f"⌛ {_PT['loading']}", showarrow=False,
                          font=dict(size=14, color="#9aa5b1"),
                          xref="paper", yref="paper", x=0.5, y=0.5)],
    )
    return fig


def _af_kpi_card(card_id, title_id, sub_id, title, subtitle, accent, value_id):
    """KPI card com o look da indicators-v2 (borderTop + valor grande)."""
    return dbc.Col(
        dbc.Card(
            [
                dbc.CardHeader(
                    html.Div([
                        html.Strong(title, id=title_id, style={"fontSize": "1rem"}),
                        html.Div(subtitle, id=sub_id, className="text-muted",
                                 style={"fontSize": "0.78rem"}),
                    ]),
                    className="py-2",
                ),
                dbc.CardBody(
                    html.Span("—", id=value_id,
                              style={"fontSize": "2.1rem", "fontWeight": "800",
                                     "color": accent, "letterSpacing": "-0.5px",
                                     "lineHeight": "1"}),
                    className="py-4 px-4 d-flex align-items-center",
                    style={"minHeight": "120px"},
                ),
            ],
            id=card_id, className="shadow-sm h-100 w-100 indicator-v2-card",
            style={"borderTop": f"4px solid {accent}"},
        ),
        xs=12, md=4, className="d-flex",
    )


def _filtro(label, label_id, control, width=3, col_id=None, col_style=None):
    """Campo de filtro padronizado (label i18n + controle)."""
    kwargs = {"md": width, "xs": 12}
    if col_id:
        kwargs["id"] = col_id
    if col_style:
        kwargs["style"] = col_style
    return dbc.Col([
        html.Label(label, id=label_id, className="form-label small fw-semibold mb-1"),
        control,
    ], **kwargs)


def _barra_filtros():
    """Barra de filtros (Collapse) — período, ano, range, equipamento, códigos, duração.

    Os filtros ficam acima do `dbc.Tabs`, então valem para as três abas (Pareto,
    Dados e Análise de Paradas) — é o mesmo `store-af-filters` para todas.
    """
    anos = anos_disponiveis()
    return dbc.Collapse(
        dbc.Card(
            [
                dbc.CardBody(dbc.Row(
                    [
                        _filtro(_PT["filter_period"], "af-i18n-filter-period", dcc.Dropdown(
                            id="filter-af-period-type", clearable=False, value="year",
                            options=[
                                {"label": _PT["period_year"], "value": "year"},
                                {"label": _PT["period_last12"], "value": "last12"},
                                {"label": _PT["period_custom"], "value": "custom"},
                            ]), width=2),
                        # Ano e opções derivados da data corrente: o padrão é
                        # sempre o ano mais recente.
                        _filtro(_PT["filter_year"], "af-i18n-filter-year", dcc.Dropdown(
                            id="filter-af-year", clearable=False, value=ano_padrao(),
                            options=[{"label": str(a), "value": a} for a in anos]),
                            width=2, col_id="col-filter-af-year"),
                        _filtro(_PT["filter_range"], "af-i18n-filter-range", dcc.DatePickerRange(
                            id="filter-af-date-range", display_format="DD/MM/YYYY",
                            className="d-block", minimum_nights=0),
                            width=4, col_id="col-filter-af-range", col_style={"display": "none"}),
                        _filtro(_PT["filter_equip"], "af-i18n-filter-equip", dcc.Dropdown(
                            id="filter-af-equipment", multi=True, placeholder=_PT["equip_placeholder"]),
                            width=2),
                        _filtro(_PT["filter_codes"], "af-i18n-filter-codes", dcc.Dropdown(
                            id="filter-af-codes", multi=True,
                            options=[{"label": c, "value": c} for c in BREAKDOWN_CODES],
                            value=list(BREAKDOWN_CODES)), width=2),
                        # Nada selecionado = todas as faixas, mesma convenção do
                        # filtro de códigos acima.
                        _filtro(_PT["filter_duracao"], "af-i18n-filter-duracao", dcc.Dropdown(
                            id="filter-af-duracao", multi=True,
                            placeholder=_PT["duracao_placeholder"],
                            options=[{"label": f["label"], "value": f["value"]}
                                     for f in FAIXAS_DURACAO],
                            value=[f["value"] for f in FAIXAS_DURACAO]), width=2),
                        # Enum de string, não booleano: o store é persistido em
                        # `local` e os filtros já gravados não têm esta chave —
                        # com bool, o ausente inverteria o padrão.
                        _filtro(_PT["filter_gatilho"], "af-i18n-filter-gatilho", html.Div([
                            dcc.Dropdown(
                                id="filter-af-gatilho", clearable=False,
                                value=GATILHO_MODO_ACIMA,
                                options=[
                                    {"label": _PT["gatilho_acima"], "value": GATILHO_MODO_ACIMA},
                                    {"label": _PT["gatilho_todas"], "value": GATILHO_MODO_TODAS},
                                ]),
                            html.Small(_PT["gatilho_hint"], id="af-i18n-gatilho-hint",
                                       className="text-muted d-block",
                                       style={"fontSize": "0.7rem"}),
                        ]), width=2),
                    ],
                    className="g-3",
                )),
                dbc.CardFooter(
                    dbc.Button([html.I(className="bi bi-check2 me-1"),
                                html.Span(_PT["btn_apply"], id="af-i18n-btn-apply")],
                               id="btn-apply-af-filters", color="primary", size="sm"),
                    className="bg-transparent border-0 d-flex justify-content-end",
                ),
            ],
            className="shadow-sm mb-3",
        ),
        id="collapse-af-filters", is_open=False,
    )


def _card_grafico(title, title_id, sub_id, subtitle, graph_id, accent):
    """Card contêiner de um gráfico Pareto (look estático da v2)."""
    return dbc.Card(
        [
            dbc.CardHeader(html.Div([
                html.Strong(title, id=title_id),
                html.Div(subtitle, id=sub_id, className="text-muted", style={"fontSize": "0.8rem"}),
            ]), className="py-2"),
            dbc.CardBody(dcc.Loading(
                dcc.Graph(id=graph_id, figure=_blank_fig(),
                          config={"displayModeBar": False, "responsive": True}),
                type="circle", color=accent, delay_show=120)),
        ],
        className="shadow-sm mb-4 indicator-v2-card-static",
        style={"borderTop": f"4px solid {accent}"},
    )


def _g_card(card_id, chave, valor_id, accent):
    """Cartão do quadro de gestão. Reusa o cartão da página, com um rodapé próprio
    para o "de quanto" — percentual sozinho engana (SP-02)."""
    return dbc.Col(
        dbc.Card(
            [
                dbc.CardHeader(html.Div([
                    html.Strong(_PT[chave], id=f"af-i18n-{chave.replace('_', '-')}",
                                style={"fontSize": "0.95rem"}),
                    html.Div(_PT[f"{chave}_sub"], id=f"af-i18n-{chave.replace('_', '-')}-sub",
                             className="text-muted", style={"fontSize": "0.75rem"}),
                ]), className="py-2"),
                dbc.CardBody([
                    html.Span("—", id=valor_id,
                              style={"fontSize": "2.1rem", "fontWeight": "800",
                                     "color": accent, "letterSpacing": "-0.5px",
                                     "lineHeight": "1"}),
                    html.Div("", id=f"{valor_id}-de", className="text-muted mt-1",
                             style={"fontSize": "0.8rem"}),
                ], className="py-3 px-4", style={"minHeight": "110px"}),
            ],
            className="shadow-sm h-100 w-100 indicator-v2-card",
            style={"borderTop": f"4px solid {accent}"}, id=card_id,
        ),
        xs=12, sm=6, lg=4, className="d-flex mb-3",
    )


def _aba_gestao():
    """Aba "Gestão das Análises": o que a manutenção fez com as falhas que analisou.

    Só o esqueleto — os números vêm de `failure_management_callbacks`. Os blocos de
    fila, responsáveis, atenção e reincidência entram nas fatias seguintes.
    """
    return html.Div([
        html.Div([
            html.H5([html.I(className="bi bi-clipboard-check me-2"),
                     html.Span(_PT["g_title"], id="af-i18n-g-title")], className="mb-1"),
            html.P(_PT["g_sub"], id="af-i18n-g-sub", className="text-muted mb-3",
                   style={"fontSize": "0.85rem"}),
        ]),

        dbc.Row([
            _g_card("g-card-eleg", "g_kpi_eleg", "g-val-eleg", ACCENT),
            _g_card("g-card-analisadas", "g_kpi_analisadas", "g-val-analisadas", "#198754"),
            _g_card("g-card-fila", "g_kpi_fila", "g-val-fila", "#0d6efd"),
            _g_card("g-card-plano", "g_kpi_plano", "g-val-plano", "#6f42c1"),
            _g_card("g-card-vencidas", "g_kpi_vencidas", "g-val-vencidas", "#e67e22"),
            _g_card("g-card-voltaram", "g_kpi_voltaram", "g-val-voltaram", "#d63384"),
        ], className="g-3 kpi-row-v2"),

        dbc.Card([
            dbc.CardHeader(html.Div([
                html.Div([
                    html.Strong(_PT["g_graf_title"], id="af-i18n-g-graf-title"),
                    html.Div(_PT["g_graf_sub"], id="af-i18n-g-graf-sub",
                             className="text-muted", style={"fontSize": "0.8rem"}),
                ]),
                # Aparece só com um mês em foco: sem esta linha, quem clicou sem
                # querer não descobre como voltar ao período inteiro (SP-03).
                # O link nasce aqui, e não dentro do callback: componente criado por
                # callback não pode ser Input de outro — o clique nunca chegaria.
                html.Div([
                    html.Span("", id="g-foco-texto"),
                    html.A(_PT["g_foco_limpar"], id="g-foco-limpar", href="#",
                           className="text-decoration-none ms-1"),
                ], id="g-foco-aviso", className="small mt-2", style={"display": "none"}),
            ]), className="py-2"),
            dbc.CardBody(dcc.Loading(
                dcc.Graph(id="g-grafico-meses", figure=_blank_fig(height=320),
                          config={"displayModeBar": False, "responsive": True}),
                type="circle", color=ACCENT, delay_show=120)),
        ], className="shadow-sm mb-4 indicator-v2-card-static",
            style={"borderTop": f"4px solid {ACCENT}"}),

        # A fila vem antes das tabelas: é a única coisa da tela com alguém
        # esperando do outro lado.
        dbc.Card([
            dbc.CardHeader(html.Div([
                html.Strong(_PT["g_fila_title"], id="af-i18n-g-fila-title"),
                html.Div(_PT["g_fila_sub"], id="af-i18n-g-fila-sub",
                         className="text-muted", style={"fontSize": "0.8rem"}),
            ]), className="py-2"),
            dbc.CardBody(dcc.Loading(html.Div(id="g-bloco-fila"),
                                     type="circle", color=ACCENT, delay_show=120)),
        ], className="shadow-sm mb-4 indicator-v2-card-static",
            style={"borderTop": "4px solid #0d6efd"}),

        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader(html.Div([
                    html.Strong(_PT["g_resp_title"], id="af-i18n-g-resp-title"),
                    html.Div(_PT["g_resp_sub"], id="af-i18n-g-resp-sub",
                             className="text-muted", style={"fontSize": "0.8rem"}),
                ]), className="py-2"),
                dbc.CardBody(dcc.Loading(html.Div(id="g-tabela-responsaveis"),
                                         type="circle", color=ACCENT, delay_show=120)),
            ], className="shadow-sm h-100 indicator-v2-card-static",
                style={"borderTop": "4px solid #0d6efd"}), xs=12, lg=5, className="mb-3"),

            dbc.Col(dbc.Card([
                dbc.CardHeader(html.Div([
                    html.Div([
                        html.Strong(_PT["g_aten_title"], id="af-i18n-g-aten-title"),
                        html.Div(_PT["g_aten_sub"], id="af-i18n-g-aten-sub",
                                 className="text-muted", style={"fontSize": "0.8rem"}),
                    ]),
                    # Filtro por pessoa: nasce no layout (não no callback) para poder
                    # ser Input do callback que limpa.
                    html.Div([
                        html.Span("", id="g-aten-filtro-texto", className="me-1"),
                        html.A(_PT["g_aten_limpar"], id="g-aten-limpar", href="#",
                               className="text-decoration-none"),
                    ], id="g-aten-filtro", className="small mt-2",
                        style={"display": "none"}),
                ]), className="py-2"),
                dbc.CardBody(dcc.Loading(html.Div(id="g-lista-atencao"),
                                         type="circle", color=ACCENT, delay_show=120)),
            ], className="shadow-sm h-100 indicator-v2-card-static",
                style={"borderTop": "4px solid #e67e22"}), xs=12, lg=7, className="mb-3"),
        ], className="g-3"),

        dbc.Card([
            dbc.CardHeader(html.Div([
                html.Strong(_PT["g_reinc_title"], id="af-i18n-g-reinc-title"),
                html.Div(_PT["g_reinc_sub"], id="af-i18n-g-reinc-sub",
                         className="text-muted", style={"fontSize": "0.8rem"}),
            ]), className="py-2"),
            dbc.CardBody(dcc.Loading(html.Div(id="g-bloco-reincidencia"),
                                     type="circle", color=ACCENT, delay_show=120)),
        ], className="shadow-sm mb-4 indicator-v2-card-static",
            style={"borderTop": "4px solid #d63384"}),
    ], className="p-3")


def _aba_paradas():
    """Aba "Análise de Paradas": lista os eventos de falha e abre o diagrama de cada um.

    Cada linha é um **evento** (apontamentos contíguos agrupados), não um doc cru
    de ZPP_Paradas — ver `utils/failure_events.agrupar_eventos`.

    Paginação client-side do DataTable, seguindo o padrão do projeto (precedente:
    `pages/maintenance/backlog.py`). São ~1.000 eventos em todo o histórico, o
    que não justifica paginação server-side (que não tem precedente no codebase).
    """
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col([
                        html.H5([html.I(className="bi bi-diagram-3 me-2"),
                                 html.Span(_PT["paradas_title"], id="af-i18n-paradas-title")],
                                className="mb-1"),
                        html.P(_PT["paradas_sub"], id="af-i18n-paradas-sub",
                               className="text-muted mb-0", style={"fontSize": "0.82rem"}),
                    ], xs=12, md=8),
                    dbc.Col(
                        html.Div([
                            html.Label(_PT["paradas_page_size"], id="af-i18n-paradas-page-size",
                                       className="form-label small fw-semibold mb-1"),
                            dbc.Select(
                                id="af-paradas-page-size",
                                options=[{"label": str(n), "value": str(n)} for n in (10, 20, 50, 100)],
                                value="20", size="sm",
                            ),
                        ], style={"maxWidth": "180px"}),
                        xs=12, md=4, className="d-flex justify-content-md-end mt-3 mt-md-0",
                    ),
                ],
                className="mt-2 mb-3 align-items-end",
            ),
            dcc.Loading(
                html.Div(id="af-paradas-container"),
                type="circle", color=ACCENT, delay_show=120,
            ),
        ],
        className="p-3",
    )


def layout():
    """Layout da página Análise de Falhas (Pareto de paradas)."""
    return dbc.Container(
        [
            dcc.Store(id="store-af-lang", storage_type="local", data="pt"),
            # `local` (era `memory`): os filtros precisam sobreviver a recarregar
            # a página e a navegar até o diagrama e voltar. Vale para as 3 abas,
            # que leem este mesmo store.
            dcc.Store(id="store-af-filters", storage_type="local"),
            dcc.Store(id="store-af-data", storage_type="memory"),
            # `session` (e não `memory`): navegar para o diagrama desmonta a
            # página, e o usuário precisa reencontrar a listagem na mesma página,
            # ordenação e tamanho ao voltar.
            dcc.Store(id="store-af-paradas-view", storage_type="session"),
            # Mês aberto na aba Análise de Paradas (drill dos cards de mês).
            # None/ausente = grade dos 12 meses; 1–12 = lista daquele mês.
            dcc.Store(id="store-af-paradas-mes", storage_type="session"),
            # Gestão das Análises: o mês em foco e a pessoa filtrada precisam
            # sobreviver à ida ao diagrama e à volta — quem tem 8 pendências não pode
            # reencontrar o caminho 8 vezes (SP-08).
            dcc.Store(id="store-af-gestao-mes", storage_type="session"),
            dcc.Store(id="store-af-gestao-pessoa", storage_type="session"),
            # Resultado do agregador. Em memória: mudar o foco é recorte do que já
            # está na mão, não motivo para reconsultar o banco (DS-06).
            dcc.Store(id="store-af-gestao-data", storage_type="memory"),

            # ── Cabeçalho + toolbar ──────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col([
                        html.H2([
                            html.I(className="bi bi-bar-chart-steps me-3", style={"color": ACCENT}),
                            html.Span(_PT["title"], id="af-i18n-title"),
                            dbc.Badge([html.I(className="bi bi-exclamation-triangle-fill me-1"),
                                       html.Span(_PT["beta_badge"], id="af-i18n-beta")],
                                      id="af-beta-badge", color="warning", text_color="dark",
                                      pill=True, className="v2-beta-badge ms-3 align-middle"),
                            dbc.Tooltip(_PT["beta_tooltip"], id="af-beta-tooltip",
                                        target="af-beta-badge", placement="bottom"),
                        ], className="mb-1 d-flex align-items-center flex-wrap"),
                        html.P(_PT["subtitle"], id="af-i18n-subtitle",
                               className="text-muted mb-0", style={"fontSize": "0.9rem"}),
                    ], xs=12, md=8),
                    dbc.Col(
                        html.Div([
                            _lang_switcher(),
                            dbc.ButtonGroup([
                                dbc.Button([html.I(className="bi bi-envelope me-1"),
                                            html.Span(_PT["btn_sendmail"], id="af-i18n-btn-sendmail")],
                                           id="btn-af-sendmail", color="info", outline=True, size="sm"),
                                dbc.Button([html.I(className="bi bi-arrow-clockwise me-1"),
                                            html.Span(_PT["btn_refresh"], id="af-i18n-btn-refresh")],
                                           id="btn-af-refresh", color="primary", outline=True, size="sm"),
                                dbc.Button([html.I(className="bi bi-funnel me-1"),
                                            html.Span(_PT["btn_filters"], id="af-i18n-btn-filters")],
                                           id="btn-af-filters", color="secondary", outline=True, size="sm"),
                                dbc.Button([html.I(className="bi bi-file-earmark-excel me-1"),
                                            html.Span(_PT["btn_export"], id="af-i18n-btn-export")],
                                           id="btn-af-export", color="success", outline=True, size="sm"),
                            ]),
                        ], className="d-flex flex-column align-items-md-end align-items-start"),
                        xs=12, md=4,
                        className="d-flex align-items-end justify-content-md-end mt-3 mt-md-0",
                    ),
                ],
                className="mb-4 align-items-start",
            ),

            _barra_filtros(),
            dcc.Download(id="download-af-xlsx"),
            # Material mensal em PowerPoint (botão no cabeçalho do mês aberto, na aba
            # Análise de Paradas). Fica na página, e não dentro do container que o
            # callback redesenha, para o download sobreviver ao re-render da lista.
            dcc.Download(id="download-af-slides"),
            dbc.Toast(id="af-mail-toast", header="E-mail", is_open=False, dismissable=True,
                      duration=6000, icon="info",
                      style={"position": "fixed", "top": "90px", "right": "20px",
                             "width": "360px", "zIndex": 1060}),
            dbc.Toast(id="af-slides-toast", header="Slides", is_open=False, dismissable=True,
                      duration=6000, icon="danger",
                      style={"position": "fixed", "top": "90px", "right": "20px",
                             "width": "360px", "zIndex": 1060}),

            # ── Tabs ─────────────────────────────────────────────────────
            dbc.Tabs(
                [
                    dbc.Tab(
                        _aba_gestao(),
                        tab_id="tab-af-gestao", id="tab-af-gestao-component",
                        label=_PT["tab_gestao"],
                    ),
                    dbc.Tab(
                        html.Div([
                            dbc.Row([
                                _af_kpi_card("af-card-total", "af-i18n-kpi-total-title",
                                             "af-i18n-kpi-total-sub", _PT["kpi_total_title"],
                                             _PT["kpi_total_sub"], ACCENT, "af-kpi-total-min"),
                                _af_kpi_card("af-card-count", "af-i18n-kpi-count-title",
                                             "af-i18n-kpi-count-sub", _PT["kpi_count_title"],
                                             _PT["kpi_count_sub"], "#e67e22", "af-kpi-count"),
                                _af_kpi_card("af-card-top", "af-i18n-kpi-top-title",
                                             "af-i18n-kpi-top-sub", _PT["kpi_top_title"],
                                             _PT["kpi_top_sub"], "#8e44ad", "af-kpi-top"),
                            ], className="mb-4 g-3 kpi-row-v2"),
                            _card_grafico(_PT["causa_title"], "af-i18n-causa-title", "af-i18n-causa-sub",
                                          _PT["causa_sub"], "af-pareto-causa", ACCENT),
                            _card_grafico(_PT["equip_title"], "af-i18n-equip-title", "af-i18n-equip-sub",
                                          _PT["equip_sub"], "af-pareto-equip", ACCENT_EQUIP),
                        ], className="p-3"),
                        tab_id="tab-af-pareto", id="tab-af-pareto-component", label=_PT["tab_pareto"],
                    ),
                    dbc.Tab(
                        html.Div([
                            html.H5([html.I(className="bi bi-table me-2"),
                                     html.Span(_PT["table_title"], id="af-i18n-table-title")],
                                    className="mt-2 mb-3"),
                            dcc.Loading(html.Div(id="af-top-table"), type="circle", color=ACCENT),
                        ], className="p-3"),
                        tab_id="tab-af-dados", id="tab-af-dados-component", label=_PT["tab_dados"],
                    ),
                    dbc.Tab(
                        _aba_paradas(),
                        tab_id="tab-af-paradas", id="tab-af-paradas-component",
                        label=_PT["tab_paradas"],
                    ),
                ],
                id="tabs-af", active_tab="tab-af-gestao",
                # A aba ativa precisa sobreviver à ida ao diagrama e à volta: sem
                # isto, "Voltar às paradas" remonta a página no default (Pareto) e
                # obriga o usuário a reencontrar a aba Análise de Paradas — mesmo
                # com o mês e a página da tabela já preservados nos stores de
                # sessão. `session` (e não `local`) para acompanhar o escopo dos
                # stores `store-af-paradas-mes` / `store-af-paradas-view`.
                persistence=True, persistence_type="session",
            ),
        ],
        fluid=True,
        className="p-4",
    )
