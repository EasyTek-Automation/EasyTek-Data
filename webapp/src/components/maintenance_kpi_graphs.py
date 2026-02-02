"""
Maintenance KPI Graphs Components
Gráficos de KPIs de manutenção (barras com tendência, sunburst, tabela)
"""

import plotly.graph_objects as go
import numpy as np
from dash import html
import dash_bootstrap_components as dbc
from typing import Dict, List


# ==================== SISTEMA DE CORES SIMPLIFICADO ====================

def get_kpi_color(value: float, reference: float, kpi_type: str, margin_percent: float = 3.0) -> str:
    """
    Calcula a cor baseada no valor vs referência com margem de tolerância.

    Sistema de 3 cores:
    - Verde (#198754): Melhor que referência e fora da margem
    - Amarelo (#ffc107): Dentro da margem de ±3% da referência
    - Vermelho (#dc3545): Pior que referência e fora da margem

    Args:
        value: Valor atual do KPI
        reference: Valor de referência (meta ou média geral)
        kpi_type: Tipo do KPI ("MTBF", "MTTR", "breakdown_rate")
        margin_percent: Margem de tolerância em % (padrão 3%)

    Returns:
        String com código hexadecimal da cor
    """
    # Calcular margem de tolerância
    margin = reference * (margin_percent / 100.0)
    lower_bound = reference - margin
    upper_bound = reference + margin

    # MTBF: Maior é melhor
    if kpi_type == "MTBF":
        if value >= upper_bound:
            return "#198754"  # Verde - muito acima da referência
        elif value >= lower_bound:
            return "#ffc107"  # Amarelo - dentro da margem
        else:
            return "#dc3545"  # Vermelho - abaixo da referência

    # MTTR e Taxa de Avaria: Menor é melhor
    else:  # "MTTR" ou "breakdown_rate"
        if value <= lower_bound:
            return "#198754"  # Verde - muito abaixo da referência
        elif value <= upper_bound:
            return "#ffc107"  # Amarelo - dentro da margem
        else:
            return "#dc3545"  # Vermelho - acima da referência


def get_multiple_colors(values: List[float], references: List[float],
                       kpi_type: str, margin_percent: float = 3.0) -> List[str]:
    """
    Calcula cores para múltiplos valores (para gráficos de barras).

    Args:
        values: Lista de valores
        references: Lista de referências (mesmo tamanho que values)
        kpi_type: Tipo do KPI
        margin_percent: Margem de tolerância em %

    Returns:
        Lista de cores (strings hex)
    """
    return [
        get_kpi_color(val, ref, kpi_type, margin_percent)
        for val, ref in zip(values, references)
    ]


def create_database_error_figure(kpi_name: str = "KPI", error_message: str = None, template: str = 'minty') -> go.Figure:
    """
    Cria figura para quando o BANCO DE DADOS está OFFLINE (erro de conexão).

    Args:
        kpi_name: Nome do KPI
        error_message: Mensagem de erro técnica (opcional)
        template: Template do tema ('minty' ou 'darkly')

    Returns:
        Figura Plotly com mensagem de erro de banco de dados
    """
    is_dark = (template == 'darkly')
    bg_color = '#2c2c2c' if is_dark else '#fff3cd'  # Fundo amarelo claro para alerta
    text_color = '#e0e0e0' if is_dark else '#856404'
    subtitle_color = '#a0a0a0' if is_dark else '#6c757d'

    fig = go.Figure()

    # Ícone de banco de dados com problema
    fig.add_annotation(
        x=0.5, y=0.65,
        text="<span style='font-size:80px;'>🔌</span>",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle'
    )

    # Título
    fig.add_annotation(
        x=0.5, y=0.45,
        text="<b>Banco de Dados Offline</b>",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=18, color=text_color)
    )

    # Mensagem principal
    fig.add_annotation(
        x=0.5, y=0.35,
        text=f"Não foi possível carregar os dados de {kpi_name}",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=14, color=subtitle_color)
    )

    # Submensagem
    fig.add_annotation(
        x=0.5, y=0.25,
        text="O MongoDB está inacessível. Verifique se o serviço está rodando.",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=12, color=subtitle_color)
    )

    # Detalhes técnicos (se fornecidos)
    if error_message:
        fig.add_annotation(
            x=0.5, y=0.15,
            text=f"<i>Erro: {error_message[:80]}...</i>",
            xref="paper", yref="paper",
            showarrow=False,
            xanchor='center', yanchor='middle',
            font=dict(size=10, color=subtitle_color)
        )

    fig.update_layout(
        template=template,
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        height=400,
        margin=dict(t=20, b=20, l=20, r=20),
        hovermode=False
    )

    return fig


def create_no_data_figure(graph_type: str = "geral", template: str = 'minty') -> go.Figure:
    """
    Cria figura para quando NÃO HÁ DADOS NO BANCO (estado de erro).

    Args:
        graph_type: Tipo do gráfico ("geral", "sunburst", "gauge", "linha", etc)
        template: Template do tema ('minty' ou 'darkly')

    Returns:
        Figura Plotly com mensagem de sem dados
    """
    is_dark = (template == 'darkly')
    bg_color = '#2c2c2c' if is_dark else '#f8f9fa'
    text_color = '#e0e0e0' if is_dark else '#2c3e50'
    subtitle_color = '#a0a0a0' if is_dark else '#6c757d'

    fig = go.Figure()

    # Ícone grande de sem dados
    fig.add_annotation(
        x=0.5, y=0.65,
        text="<span style='font-size:80px;'>📭</span>",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle'
    )

    # Título
    fig.add_annotation(
        x=0.5, y=0.45,
        text="<b>Nenhum Dado Disponível</b>",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=18, color=text_color)
    )

    # Mensagem
    fig.add_annotation(
        x=0.5, y=0.35,
        text="Não há dados de manutenção no banco de dados",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=14, color=subtitle_color)
    )

    # Submensagem
    fig.add_annotation(
        x=0.5, y=0.25,
        text="Os dados são carregados automaticamente quando disponíveis",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=12, color=subtitle_color)
    )

    fig.update_layout(
        template=template,
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        height=400,
        margin=dict(t=20, b=20, l=20, r=20),
        hovermode=False
    )

    return fig


def create_empty_kpi_figure(kpi_name: str, template: str = 'minty') -> go.Figure:
    """
    Cria figura vazia para placeholder quando dados estão sendo carregados.

    Args:
        kpi_name: Nome do KPI ("MTBF", "MTTR", "Taxa de Avaria")
        template: Template do tema ('minty' ou 'darkly')

    Returns:
        Figura Plotly com mensagem de carregamento
    """
    is_dark = (template == 'darkly')
    bg_color = '#2c2c2c' if is_dark else '#ffffff'
    text_color = '#adb5bd' if is_dark else '#495057'

    fig = go.Figure()

    # Ícone
    fig.add_annotation(
        x=0.5, y=0.6,
        text="<span style='font-size:60px;'>📊</span>",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle'
    )

    # Título
    fig.add_annotation(
        x=0.5, y=0.45,
        text=f"<b>{kpi_name} por Equipamento</b>",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=16, color=text_color)
    )

    # Mensagem
    fig.add_annotation(
        x=0.5, y=0.32,
        text="Os dados serão carregados automaticamente",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=14, color=text_color)
    )

    fig.add_annotation(
        x=0.5, y=0.25,
        text="Ou ajuste os filtros acima e clique em 'Aplicar'",
        xref="paper", yref="paper",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=12, color=text_color)
    )

    fig.update_layout(
        template=template,
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        height=400,
        margin=dict(t=20, b=20, l=20, r=20)
    )

    return fig


def create_kpi_bar_chart(equipment_ids: List[str],
                         values: List[float],
                         kpi_name: str,
                         average_value: float,
                         target_values: Dict[str, float],  # ALTERADO: Dict de metas por equipamento
                         equipment_names_dict: Dict[str, str],
                         template: str = 'minty',
                         plant_target: float = None,
                         margin_percent: float = 3.0) -> go.Figure:
    """
    Cria gráfico de barras com meta da planta e metas individualizadas por equipamento.

    Args:
        equipment_ids: Lista de IDs dos equipamentos
        values: Lista de valores do KPI
        kpi_name: "MTBF", "MTTR" ou "Taxa de Avaria"
        average_value: Valor médio calculado (usado para colorir barras)
        target_values: Dicionário de metas {equipment_id: meta_value}
        equipment_names_dict: Dicionário de nomes
        template: 'minty' ou 'darkly'
        plant_target: Meta geral da planta (exibida como linha de referência)

    Returns:
        Figura Plotly com barras, linha de meta da planta e tendência
    """
    # Converter MTTR de horas para minutos
    if kpi_name == "MTTR":
        values = [v * 60 for v in values]
        average_value = average_value * 60
        target_values = {eq_id: meta * 60 for eq_id, meta in target_values.items()}
        if plant_target is not None:
            plant_target = plant_target * 60

    # Determinar unidade
    if kpi_name == "MTBF":
        unit = "h"
    elif kpi_name == "MTTR":
        unit = "min"
    else:
        unit = "%"

    # Sistema de cores simplificado (3 cores)
    # Na TAB GERAL: Compara com MÉDIA GERAL (planta), não com meta individual
    # Verde: Melhor que média e fora da margem
    # Amarelo: Dentro de ±margin_percent% da média
    # Vermelho: Pior que média e fora da margem
    references = [average_value] * len(values)  # Usar média geral como referência
    bar_colors = get_multiple_colors(values, references, kpi_name, margin_percent=margin_percent)

    # Criar figura
    fig = go.Figure()

    # Formatar texto baseado no KPI
    if kpi_name == "Taxa de Avaria":
        text_values = [f'{v:.2f}' for v in values]
        hover_format = '<b>%{x}</b><br>%{y:.2f} ' + unit + '<extra></extra>'
    else:
        text_values = [f'{v:.1f}' for v in values]
        hover_format = '<b>%{x}</b><br>%{y:.1f} ' + unit + '<extra></extra>'

    # Adicionar barras
    fig.add_trace(go.Bar(
        x=[equipment_names_dict.get(eq_id, eq_id) for eq_id in equipment_ids],
        y=values,
        name=kpi_name,
        marker=dict(
            color=bar_colors,
            line=dict(color='rgba(0,0,0,0.3)', width=1),
            cornerradius=4
        ),
        text=text_values,
        textposition='outside',
        hovertemplate=hover_format
    ))

    # Linha de meta da planta (azul tracejada)
    # Se meta da planta não foi fornecida, usa a média como fallback
    reference_value = plant_target if plant_target is not None else average_value
    reference_label = "Meta da Planta" if plant_target is not None else "Média Geral"

    fig.add_hline(
        y=reference_value,
        line_dash="dash",
        line_color="#0d6efd",
        line_width=2,
        annotation_text=f"{reference_label}: {reference_value:.1f} {unit}",
        annotation_position="top right",
        annotation=dict(font=dict(size=11))
    )

    # NOTA: Metas individuais são refletidas nas cores das barras
    # Verde = atende meta individual, Vermelho = não atende meta individual

    # Linha de tendência (polinomial grau 2)
    if len(values) >= 3:
        x_numeric = list(range(len(values)))
        try:
            z = np.polyfit(x_numeric, values, 2)
            p = np.poly1d(z)
            trend_y = [p(x) for x in x_numeric]

            fig.add_trace(go.Scatter(
                x=[equipment_names_dict.get(eq_id, eq_id) for eq_id in equipment_ids],
                y=trend_y,
                mode='lines',
                line=dict(color='rgba(108,117,125,0.6)', width=2, dash='dot'),
                name='Tendência',
                hoverinfo='skip'
            ))
        except:
            # Se falhar o polyfit, ignora a tendência
            pass

    # Layout
    fig.update_layout(
        template=template,
        title=dict(
            text=f"{kpi_name} por Equipamento",
            x=0.5,
            xanchor='center',
            font=dict(size=16)
        ),
        xaxis=dict(
            title="Equipamento",
            tickangle=-45
        ),
        yaxis=dict(
            title=f"{kpi_name} ({unit})",
            rangemode='tozero'
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        height=400,
        margin=dict(t=60, b=100, l=60, r=40),
        hovermode='x'
    )

    return fig


def create_kpi_sunburst_chart(data_by_equipment: Dict[str, float],
                               kpi_name: str,
                               categories_dict: Dict[str, List[str]],
                               equipment_names_dict: Dict[str, str],
                               template: str = 'minty',
                               target_values: Dict[str, float] = None,
                               plant_target: float = None,
                               margin_percent: float = 3.0) -> go.Figure:
    """
    Cria gráfico Sunburst com hierarquia por categoria e cores baseadas em performance.

    Args:
        data_by_equipment: {"LONGI001": 22.3, "PRENS001": 18.5, ...}
        kpi_name: "MTBF", "MTTR" ou "Taxa de Avaria"
        categories_dict: EQUIPMENT_CATEGORIES do maintenance_demo_data
        equipment_names_dict: EQUIPMENT_NAMES do maintenance_demo_data
        template: 'minty' ou 'darkly'
        target_values: Dicionário de metas por equipamento (opcional)
        plant_target: Meta geral da planta (opcional)

    Returns:
        Figura Plotly Sunburst com 3 níveis e cores de performance
    """
    # Converter MTTR de horas para minutos
    if kpi_name == "MTTR":
        data_by_equipment = {k: v * 60 for k, v in data_by_equipment.items()}

    # Determinar unidade
    if kpi_name == "MTBF":
        unit = "h"
    elif kpi_name == "MTTR":
        unit = "min"
    else:
        unit = "%"

    labels = ["Total"]
    parents = [""]
    values = [0]  # Será calculado como soma das categorias
    colors = ['#6c757d']  # Cor neutra para o centro (Total)

    # Usar meta da planta se disponível, senão usar target_values individuais
    use_plant_target = plant_target is not None

    # Adicionar categorias (anel 1) - cor neutra
    for cat_name, eq_list in categories_dict.items():
        labels.append(cat_name)
        parents.append("Total")

        # Calcular soma dos equipamentos desta categoria
        cat_value = sum(
            data_by_equipment.get(eq_id, 0)
            for eq_id in eq_list
            if eq_id in data_by_equipment
        )
        values.append(cat_value)
        colors.append('#94a3b8')  # Cor neutra para categorias

    # Adicionar equipamentos individuais (anel 2) com cores de performance
    for cat_name, eq_list in categories_dict.items():
        for eq_id in eq_list:
            if eq_id in data_by_equipment:
                labels.append(equipment_names_dict.get(eq_id, eq_id))
                parents.append(cat_name)
                eq_value = data_by_equipment[eq_id]
                values.append(eq_value)

                # Determinar cor baseada em performance (sistema de 3 cores)
                if use_plant_target:
                    # Usar meta geral da planta
                    target = plant_target
                elif target_values and eq_id in target_values:
                    # Usar meta individual do equipamento
                    target = target_values[eq_id]
                else:
                    # Sem meta definida - usar cor neutra
                    colors.append('#6c757d')
                    continue

                # Calcular cor usando função helper
                color = get_kpi_color(eq_value, target, kpi_name, margin_percent=margin_percent)
                colors.append(color)

    # Calcular total (soma das categorias)
    values[0] = sum(v for v in values[1:len(categories_dict) + 1])

    # Determinar formato de texto baseado no KPI
    # MTBF: mostrar valores absolutos em horas
    # MTTR: mostrar valores absolutos em minutos
    # Taxa de Avaria: mostrar porcentagens
    if kpi_name == "MTBF":
        text_display = 'label+text'
        custom_text = [f"{v:.1f}h" for v in values]
    elif kpi_name == "MTTR":
        text_display = 'label+text'
        custom_text = [f"{v:.1f}min" for v in values]
    else:
        text_display = 'label+percent parent'
        custom_text = None

    # Criar sunburst com cores de performance
    fig = go.Figure(go.Sunburst(
        labels=labels,
        parents=parents,
        values=values,
        text=custom_text,
        branchvalues="total",
        marker=dict(
            colors=colors,  # Cores customizadas baseadas em performance
            line=dict(color='#fff', width=2)
        ),
        textinfo=text_display,
        hovertemplate='<b>%{label}</b><br>%{value:.1f} ' + unit + '<extra></extra>'
    ))

    fig.update_layout(
        template=template,
        title=dict(
            text=f"Hierarquia de {kpi_name}",
            x=0.5,
            xanchor='center',
            font=dict(size=16)
        ),
        height=500,
        margin=dict(t=50, b=20, l=20, r=20)
    )

    return fig


def create_kpi_summary_table(data_by_equipment: Dict[str, Dict[str, float]],
                             targets: Dict[str, Dict[str, float]],  # ALTERADO: Dict de metas por equipamento
                             equipment_names_dict: Dict[str, str]) -> dbc.Table:
    """
    Cria tabela resumo com todos KPIs por equipamento com metas individualizadas.

    Args:
        data_by_equipment: {
            "LONGI001": {"mtbf": 22.3, "mttr": 1.8, "breakdown_rate": 2.9},
            ...
        }
        targets: {
            "LONGI001": {"mtbf": 11.3, "mttr": 0.533, "breakdown_rate": 3.2},
            "GENERAL": {"mtbf": 11.3, "mttr": 0.65, "breakdown_rate": 5.1},
            ...
        }
        equipment_names_dict: Dicionário de nomes

    Returns:
        Componente dbc.Table
    """
    # Ordenar equipamentos por ID
    sorted_equipment = sorted(data_by_equipment.keys())

    # Meta geral como fallback
    general_target = targets.get("GENERAL", {"mtbf": 0, "mttr": 999, "breakdown_rate": 100})

    rows = []
    for eq_id in sorted_equipment:
        eq_data = data_by_equipment[eq_id]

        # ⚠️ NA ABA GERAL: Comparar SEMPRE com a META GERAL DA PLANTA
        # (não com metas individuais dos equipamentos)
        mtbf_ok = eq_data["mtbf"] >= general_target["mtbf"]
        mttr_ok = eq_data["mttr"] <= general_target["mttr"]
        breakdown_ok = eq_data["breakdown_rate"] <= general_target["breakdown_rate"]
        meets_all = mtbf_ok and mttr_ok and breakdown_ok

        # Formatar valores com META GERAL (Valor/Meta Planta)
        mtbf_actual = eq_data['mtbf']
        mtbf_target = general_target['mtbf']  # ← Meta geral da planta
        mttr_actual = eq_data['mttr'] * 60  # Converter para minutos
        mttr_target = general_target['mttr'] * 60  # ← Meta geral da planta
        breakdown_actual = eq_data['breakdown_rate']
        breakdown_target = general_target['breakdown_rate']  # ← Meta geral da planta

        rows.append(
            html.Tr([
                html.Td(equipment_names_dict.get(eq_id, eq_id)),
                html.Td(
                    f"{mtbf_actual:.1f}/{mtbf_target:.1f}",
                    className="text-center",
                    style={"fontWeight": "500"}
                ),
                html.Td(
                    f"{mttr_actual:.1f}/{mttr_target:.1f}",
                    className="text-center",
                    style={"fontWeight": "500"}
                ),
                html.Td(
                    f"{breakdown_actual:.2f}/{breakdown_target:.2f}",
                    className="text-center",
                    style={"fontWeight": "500"}
                ),
                html.Td([
                    dbc.Badge(
                        "✓ OK" if meets_all else "⚠ Atenção",
                        color="success" if meets_all else "warning",
                        className="px-3"
                    )
                ], className="text-center")
            ])
        )

    return dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Equipamento"),
                html.Th([
                    "MTBF (h)",
                    html.Br(),
                    html.Small("Valor/Meta", className="text-muted")
                ], className="text-center"),
                html.Th([
                    "MTTR (min)",
                    html.Br(),
                    html.Small("Valor/Meta", className="text-muted")
                ], className="text-center"),
                html.Th([
                    "Taxa Avaria (%)",
                    html.Br(),
                    html.Small("Valor/Meta", className="text-muted")
                ], className="text-center"),
                html.Th("Status", className="text-center"),
            ], className="table-light")
        ]),
        html.Tbody(rows)
    ], bordered=True, hover=True, responsive=True, striped=True, className="mb-0")


def create_kpi_line_chart(months_list: List[int],
                          values: List[float],
                          avg_values: List[float],
                          kpi_name: str,
                          equipment_name: str,
                          target_value: float,
                          template: str = 'minty',
                          margin_percent: float = 3.0) -> go.Figure:
    """
    Cria gráfico híbrido (barras + linhas) mostrando evolução mensal.

    Exibe:
    - Barras do equipamento com cores condicionais baseadas em performance
    - Linha da média geral (laranja tracejada)
    - Linha da meta (vermelha pontilhada)

    Lógica de Cores:
    - MTBF (maior é melhor):
      * Verde escuro: >= meta
      * Verde claro: >= média e < meta
      * Amarelo: < média e < meta
      * Vermelho: muito abaixo
    - MTTR/Taxa Avaria (menor é melhor):
      * Verde escuro: <= meta
      * Verde claro: <= média e > meta
      * Amarelo: > média e > meta
      * Vermelho: muito acima

    Args:
        months_list: Lista de meses [1, 2, 3, ..., 12]
        values: Valores do equipamento por mês
        avg_values: Média geral por mês (para comparação)
        kpi_name: "MTBF", "MTTR" ou "Taxa de Avaria"
        equipment_name: Nome do equipamento
        target_value: Meta do KPI
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly com barras coloridas e linhas
    """
    # Converter MTTR de horas para minutos
    if kpi_name == "MTTR":
        values = [v * 60 for v in values]
        avg_values = [v * 60 for v in avg_values]
        target_value = target_value * 60

    month_names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                   "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    x_labels = [month_names[m-1] for m in months_list]

    # Sistema de cores simplificado (3 cores apenas)
    # Verde: Melhor que meta e fora da margem de 3%
    # Amarelo: Dentro de ±3% da meta
    # Vermelho: Pior que meta e fora da margem de 3%

    # Determinar se maior é melhor (para lógica de cores)
    higher_is_better = (kpi_name == "MTBF")

    # Usar meta como referência para coloração (não média)
    references = [target_value] * len(values)
    bar_colors = get_multiple_colors(values, references, kpi_name, margin_percent=margin_percent)

    # Formatar texto baseado no KPI
    if kpi_name == "Taxa de Avaria":
        text_values = [f'{v:.2f}' for v in values]
        hover_format = '<b>%{x}</b><br>Valor: %{y:.2f}<extra></extra>'
    else:
        text_values = [f'{v:.1f}' for v in values]
        hover_format = '<b>%{x}</b><br>Valor: %{y:.1f}<extra></extra>'

    fig = go.Figure()

    # Barras do equipamento com cores condicionais
    fig.add_trace(go.Bar(
        x=x_labels,
        y=values,
        name=equipment_name,
        marker=dict(
            color=bar_colors,
            cornerradius=4,
            line=dict(width=0)
        ),
        text=text_values,
        textposition='outside',
        textfont=dict(size=10),
        hovertemplate=hover_format
    ))

    # Linha da média geral (laranja tracejada)
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=avg_values,
        mode='lines',
        name='Média Geral',
        line=dict(color='#fd7e14', width=2, dash='dash')
    ))

    # Linha da meta (vermelha pontilhada)
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=[target_value] * len(months_list),
        mode='lines',
        name='Meta',
        line=dict(color='#dc3545', width=2, dash='dot')
    ))

    # Determinar unidade
    if kpi_name == "MTBF":
        unit = "h"
    elif kpi_name == "MTTR":
        unit = "min"
    else:
        unit = "%"

    # Criar legenda de cores baseado no tipo de KPI (sistema de 3 cores)
    if higher_is_better:
        color_legend = "🟢 Verde: Acima da Meta | 🟡 Amarelo: ±3% da Meta | 🔴 Vermelho: Abaixo da Meta"
    else:
        color_legend = "🟢 Verde: Abaixo da Meta | 🟡 Amarelo: ±3% da Meta | 🔴 Vermelho: Acima da Meta"

    fig.update_layout(
        template=template,
        title=dict(
            text=f"{kpi_name} - {equipment_name}<br><sub style='font-size: 9px'>{color_legend}</sub>",
            x=0.5,
            xanchor='center',
            font=dict(size=14)
        ),
        xaxis=dict(title="Mês"),
        yaxis=dict(title=f"{kpi_name} ({unit})", rangemode='tozero'),
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        bargap=0.2,  # Espaçamento entre barras
        height=370,  # Aumentado para acomodar legenda
        margin=dict(t=80, b=60, l=60, r=40)  # Margem superior aumentada
    )

    return fig


def create_comparison_bar_chart(equipment_data: Dict[str, float],
                                general_avg: Dict[str, float],
                                equipment_name: str,
                                template: str = 'minty') -> go.Figure:
    """
    Cria gráfico de barras comparando equipamento com média geral.

    Mostra lado a lado: Equipamento vs Média Geral para os 3 KPIs.

    Args:
        equipment_data: {"mtbf": X, "mttr": Y, "breakdown_rate": Z}
        general_avg: {"mtbf": X, "mttr": Y, "breakdown_rate": Z}
        equipment_name: Nome do equipamento
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly com barras agrupadas
    """
    kpis = ["MTBF", "MTTR", "Taxa de Avaria"]
    equipment_values = [
        equipment_data["mtbf"],
        equipment_data["mttr"] * 60,  # Converter MTTR para minutos
        equipment_data["breakdown_rate"]
    ]
    avg_values = [
        general_avg["mtbf"],
        general_avg["mttr"] * 60,  # Converter MTTR para minutos
        general_avg["breakdown_rate"]
    ]

    # Formatar texto: 1 casa para MTBF/MTTR, 2 casas para Taxa de Avaria
    equipment_text = [
        f'{equipment_values[0]:.1f}',  # MTBF
        f'{equipment_values[1]:.1f}',  # MTTR
        f'{equipment_values[2]:.2f}'   # Taxa de Avaria
    ]
    avg_text = [
        f'{avg_values[0]:.1f}',  # MTBF
        f'{avg_values[1]:.1f}',  # MTTR
        f'{avg_values[2]:.2f}'   # Taxa de Avaria
    ]

    fig = go.Figure()

    # Barras do equipamento
    fig.add_trace(go.Bar(
        x=kpis,
        y=equipment_values,
        name=equipment_name,
        marker_color='#0d6efd',
        text=equipment_text,
        textposition='outside'
    ))

    # Barras da média geral
    fig.add_trace(go.Bar(
        x=kpis,
        y=avg_values,
        name='Média Geral',
        marker_color='#6c757d',
        text=avg_text,
        textposition='outside'
    ))

    fig.update_layout(
        template=template,
        title=dict(
            text=f"Comparação: {equipment_name} vs Média Geral",
            x=0.5,
            xanchor='center',
            font=dict(size=14)
        ),
        barmode='group',
        xaxis=dict(title=""),
        yaxis=dict(title="Valor", rangemode='tozero'),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        height=400,
        margin=dict(t=60, b=60, l=60, r=40)
    )

    return fig


def create_top_breakdowns_chart(breakdowns_data: List[Dict],
                                  equipment_name: str,
                                  template: str = 'minty') -> go.Figure:
    """
    Cria gráfico de barras horizontais mostrando as top paradas por duração.

    Args:
        breakdowns_data: Lista de dicionários com dados das paradas:
            [
                {
                    "date": datetime.date(2025, 1, 15),
                    "motivo": "201",
                    "duracao_min": 120.5,
                    "duracao_horas": 2.01,
                    "descricao": "Avaria Elétrica"
                },
                ...
            ]
        equipment_name: Nome do equipamento
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly com barras horizontais ordenadas por duração
    """
    if not breakdowns_data:
        # Retornar figura vazia com mensagem
        is_dark = (template == 'darkly')
        bg_color = '#2c2c2c' if is_dark else '#ffffff'
        text_color = '#adb5bd' if is_dark else '#495057'

        fig = go.Figure()
        fig.add_annotation(
            x=0.5, y=0.5,
            text="Nenhuma parada registrada no período selecionado",
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=14, color=text_color)
        )
        fig.update_layout(
            template=template,
            plot_bgcolor=bg_color,
            paper_bgcolor=bg_color,
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            height=400,
            margin=dict(t=40, b=20, l=20, r=20)
        )
        return fig

    # ✅ AGRUPAR: Mesmo dia + mesmo motivo = somar durações
    from collections import defaultdict

    grouped = defaultdict(lambda: {"duracao_horas": 0, "duracao_min": 0, "count": 0})

    for bd in breakdowns_data:
        # Chave única: data + descrição
        key = (bd['date'], bd['descricao'])
        grouped[key]['duracao_horas'] += bd['duracao_horas']
        grouped[key]['duracao_min'] += bd['duracao_min']
        grouped[key]['count'] += 1

    # Reconstruir lista agrupada
    aggregated_data = []
    for (date, descricao), values in grouped.items():
        aggregated_data.append({
            'date': date,
            'descricao': descricao,
            'duracao_horas': round(values['duracao_horas'], 2),
            'duracao_min': round(values['duracao_min'], 1),
            'count': values['count']  # Quantas paradas foram somadas
        })

    # ✅ ORDENAR: Do maior para o menor (por duração)
    aggregated_data.sort(key=lambda x: x['duracao_horas'], reverse=True)

    # Limitar ao top 10 após agregação
    aggregated_data = aggregated_data[:10]

    # Criar labels para o eixo Y (data + descrição)
    y_labels = [
        f"{bd['date'].strftime('%d/%m')} - {bd['descricao']}"
        for bd in aggregated_data
    ]

    # Valores de duração em horas (eixo X)
    x_values = [bd['duracao_horas'] for bd in aggregated_data]

    # Definir cores baseado na duração (gradiente de vermelho)
    max_duration = max(x_values) if x_values else 1
    colors = []
    for duration in x_values:
        # Gradiente de vermelho: mais escuro = maior duração
        intensity = duration / max_duration
        if intensity > 0.8:
            color = '#8b0000'  # Vermelho escuro (DarkRed)
        elif intensity > 0.6:
            color = '#dc3545'  # Vermelho padrão (Bootstrap danger)
        elif intensity > 0.4:
            color = '#fd7e14'  # Laranja
        elif intensity > 0.2:
            color = '#ffc107'  # Amarelo
        else:
            color = '#20c997'  # Verde (paradas curtas)
        colors.append(color)

    # Texto nas barras (duração em formato legível + indicador de agrupamento)
    text_values = []
    hover_templates = []

    for bd in aggregated_data:
        # Texto na barra
        if bd['duracao_horas'] >= 1:
            base_text = f"{bd['duracao_horas']:.1f}h"
        else:
            base_text = f"{bd['duracao_min']:.0f}min"

        # Se houver múltiplas paradas agrupadas, indicar
        if bd['count'] > 1:
            text_values.append(f"{base_text} ({bd['count']}x)")
        else:
            text_values.append(base_text)

    # Criar figura
    fig = go.Figure()

    # Adicionar barras horizontais (invertidas para mostrar maior no topo)
    fig.add_trace(go.Bar(
        x=x_values,
        y=y_labels,
        orientation='h',
        marker=dict(
            color=colors,
            line=dict(color='rgba(0,0,0,0.3)', width=1),
            cornerradius=4
        ),
        text=text_values,
        textposition='outside',
        customdata=[[bd['count']] for bd in aggregated_data],
        hovertemplate=(
            '<b>%{y}</b><br>' +
            'Duração Total: %{x:.2f}h<br>' +
            'Paradas Agrupadas: %{customdata[0]}<br>' +
            '<extra></extra>'
        )
    ))

    # Layout
    fig.update_layout(
        template=template,
        title=dict(
            text=f"Top {len(breakdowns_data)} Paradas - {equipment_name}",
            x=0.5,
            xanchor='center',
            font=dict(size=14)
        ),
        xaxis=dict(
            title="Duração (horas)",
            rangemode='tozero'
        ),
        yaxis=dict(
            title="",
            autorange='reversed',  # Inverter para maior ficar no topo
            tickfont=dict(size=10)
        ),
        showlegend=False,
        height=max(400, len(breakdowns_data) * 40),  # Altura dinâmica baseada no número de barras
        margin=dict(t=60, b=60, l=250, r=80),  # Margem esquerda maior para labels
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )

    return fig


def create_kpi_gauge(value: float,
                     kpi_name: str,
                     target_value: float,
                     template: str = 'minty',
                     margin_percent: float = 3.0) -> go.Figure:
    """
    Cria gráfico gauge (velocímetro) sofisticado para um KPI individual.

    Design moderno com gradientes suaves, tipografia refinada e visual profissional.

    Args:
        value: Valor atual do KPI
        kpi_name: "MTBF", "MTTR" ou "Taxa de Avaria"
        target_value: Meta do KPI
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly com gauge indicator sofisticado
    """
    # Detectar tema escuro/claro
    is_dark = (template == 'darkly')
    bg_color = 'rgba(44, 44, 44, 0.05)' if is_dark else 'rgba(248, 249, 250, 0.8)'
    text_color = '#e9ecef' if is_dark else '#2c3e50'

    # Converter MTTR de horas para minutos
    if kpi_name == "MTTR":
        value = value * 60
        target_value = target_value * 60

    # Sistema de cores simplificado (3 cores apenas)
    # Verde: Muito melhor que meta
    # Amarelo: Dentro de ±3% da meta
    # Vermelho: Pior que meta

    if kpi_name == "MTBF":
        unit = "h"
        max_range = max(target_value * 2, value * 1.2)
        higher_is_better = True
    elif kpi_name == "MTTR":
        unit = "min"
        max_range = max(target_value * 2, value * 1.2)
        higher_is_better = False
    else:  # Taxa de Avaria
        unit = "%"
        max_range = max(target_value * 2, value * 1.2, 10)
        higher_is_better = False

    # Calcular margem dinâmica
    margin = target_value * (margin_percent / 100.0)
    lower_bound = target_value - margin
    upper_bound = target_value + margin

    # Zonas simplificadas (3 cores)
    if kpi_name == "MTBF":
        # Maior é melhor
        steps = [
            {'range': [0, lower_bound], 'color': 'rgba(220, 53, 69, 0.1)'},       # Vermelho claro
            {'range': [lower_bound, upper_bound], 'color': 'rgba(255, 193, 7, 0.1)'},  # Amarelo claro
            {'range': [upper_bound, max_range], 'color': 'rgba(25, 135, 84, 0.1)'}     # Verde claro
        ]
    else:
        # Menor é melhor (MTTR e Taxa Avaria)
        steps = [
            {'range': [0, lower_bound], 'color': 'rgba(25, 135, 84, 0.1)'},       # Verde claro
            {'range': [lower_bound, upper_bound], 'color': 'rgba(255, 193, 7, 0.1)'},  # Amarelo claro
            {'range': [upper_bound, max_range], 'color': 'rgba(220, 53, 69, 0.1)'}     # Vermelho claro
        ]

    # Cor da barra usando função helper
    bar_color = get_kpi_color(value, target_value, kpi_name, margin_percent=margin_percent)

    # Formatar valor de exibição
    if kpi_name == "Taxa de Avaria":
        value_display = round(value, 2)
        delta_position = "bottom"
    else:
        value_display = round(value, 1)
        delta_position = "bottom"

    # Criar gauge sofisticado
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value_display,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={
            'text': f"<b style='font-weight:600; letter-spacing:0.5px'>{kpi_name}</b>",
            'font': {'size': 16, 'color': text_color, 'family': 'Segoe UI, Arial, sans-serif'}
        },
        number={
            'suffix': f" <span style='font-size:0.7em; font-weight:400'>{unit}</span>",
            'font': {'size': 40, 'color': bar_color, 'family': 'Segoe UI, Arial, sans-serif'},
            'valueformat': '.2f' if kpi_name == "Taxa de Avaria" else '.1f'
        },
        delta={
            'reference': target_value,
            'increasing': {'color': '#198754' if higher_is_better else '#dc3545'},
            'decreasing': {'color': '#dc3545' if higher_is_better else '#198754'},
            'suffix': f" {unit}",
            'font': {'size': 12, 'family': 'Segoe UI, Arial, sans-serif'},
            'position': delta_position,
            'valueformat': '.2f' if kpi_name == "Taxa de Avaria" else '.1f'
        },
        gauge={
            'axis': {
                'range': [0, max_range],
                'ticksuffix': f" {unit}",
                'tickfont': {'size': 10, 'color': text_color, 'family': 'Segoe UI, Arial, sans-serif'},
                'tickwidth': 1,
                'tickcolor': 'rgba(108, 117, 125, 0.3)',
                'tickmode': 'auto',
                'nticks': 6
            },
            'bar': {
                'color': bar_color,
                'thickness': 0.6,
                'line': {'color': 'rgba(255, 255, 255, 0.3)', 'width': 1}
            },
            'bgcolor': bg_color,
            'borderwidth': 1,
            'bordercolor': 'rgba(108, 117, 125, 0.2)',
            'steps': steps,
            'threshold': {
                'line': {'color': '#0d6efd', 'width': 2.5},
                'thickness': 0.8,
                'value': target_value
            }
        }
    ))

    # Layout sofisticado
    fig.update_layout(
        template=template,
        height=300,
        margin=dict(t=50, b=20, l=30, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        font={
            'family': "Segoe UI, -apple-system, BlinkMacSystemFont, Arial, sans-serif",
            'color': text_color
        }
    )

    return fig
