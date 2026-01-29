"""
Maintenance KPI Graphs Components
Gráficos de KPIs de manutenção (barras com tendência, sunburst, tabela)
"""

import plotly.graph_objects as go
import numpy as np
from dash import html
import dash_bootstrap_components as dbc
from typing import Dict, List


def create_empty_kpi_figure(kpi_name: str, template: str = 'minty') -> go.Figure:
    """
    Cria figura vazia para placeholder quando não há dados.

    Args:
        kpi_name: Nome do KPI ("MTBF", "MTTR", "Taxa de Avaria")
        template: Template do tema ('minty' ou 'darkly')

    Returns:
        Figura Plotly com mensagem de placeholder
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
                         target_value: float,
                         equipment_names_dict: Dict[str, str],
                         template: str = 'minty') -> go.Figure:
    """
    Cria gráfico de barras com média, meta e linha de tendência.

    Args:
        equipment_ids: Lista de IDs dos equipamentos
        values: Lista de valores do KPI
        kpi_name: "MTBF", "MTTR" ou "Taxa de Avaria"
        average_value: Valor médio calculado
        target_value: Valor da meta
        equipment_names_dict: Dicionário de nomes
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly com barras, linhas de média/meta e tendência
    """
    # Determinar unidade
    unit = "h" if kpi_name in ["MTBF", "MTTR"] else "%"

    # Lógica de cores das barras (verde: atende meta, vermelho: não atende)
    bar_colors = []
    for val in values:
        if kpi_name == "MTBF":
            # Maior é melhor
            color = '#20c997' if val >= target_value else '#dc3545'
        else:
            # Menor é melhor (MTTR, Taxa Avaria)
            color = '#20c997' if val <= target_value else '#dc3545'
        bar_colors.append(color)

    # Criar figura
    fig = go.Figure()

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
        text=[f'{v:.1f}' for v in values],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>%{y:.1f} ' + unit + '<extra></extra>'
    ))

    # Linha de média (azul tracejada)
    fig.add_hline(
        y=average_value,
        line_dash="dash",
        line_color="#0d6efd",
        line_width=2,
        annotation_text=f"Média: {average_value:.1f} {unit}",
        annotation_position="top right",
        annotation=dict(font=dict(size=11))
    )

    # Linha de meta (amarela tracejada)
    fig.add_hline(
        y=target_value,
        line_dash="dash",
        line_color="#ffc107",
        line_width=2,
        annotation_text=f"Meta: {target_value:.1f} {unit}",
        annotation_position="bottom right",
        annotation=dict(font=dict(size=11))
    )

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
                               template: str = 'minty') -> go.Figure:
    """
    Cria gráfico Sunburst com hierarquia por categoria.

    Args:
        data_by_equipment: {"LONGI001": 22.3, "PRENS001": 18.5, ...}
        kpi_name: "MTBF", "MTTR" ou "Taxa de Avaria"
        categories_dict: EQUIPMENT_CATEGORIES do maintenance_demo_data
        equipment_names_dict: EQUIPMENT_NAMES do maintenance_demo_data
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly Sunburst com 3 níveis
    """
    unit = "h" if kpi_name in ["MTBF", "MTTR"] else "%"

    labels = ["Total"]
    parents = [""]
    values = [0]  # Será calculado como soma das categorias
    text_info = []

    # Adicionar categorias (anel 1)
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

    # Adicionar equipamentos individuais (anel 2)
    for cat_name, eq_list in categories_dict.items():
        for eq_id in eq_list:
            if eq_id in data_by_equipment:
                labels.append(equipment_names_dict.get(eq_id, eq_id))
                parents.append(cat_name)
                values.append(data_by_equipment[eq_id])

    # Calcular total (soma das categorias)
    values[0] = sum(v for v in values[1:len(categories_dict) + 1])

    # Determinar formato de texto baseado no KPI
    # MTBF e MTTR: mostrar valores absolutos em horas
    # Taxa de Avaria: mostrar porcentagens
    if kpi_name in ["MTBF", "MTTR"]:
        text_display = 'label+text'
        # Criar textos customizados com valores em horas
        custom_text = [f"{v:.1f}h" for v in values]
    else:
        text_display = 'label+percent parent'
        custom_text = None

    # Criar sunburst
    fig = go.Figure(go.Sunburst(
        labels=labels,
        parents=parents,
        values=values,
        text=custom_text,
        branchvalues="total",
        marker=dict(
            line=dict(color='#fff', width=2),
            colorscale=[
                [0, '#0d6efd'],      # Azul
                [0.33, '#20c997'],   # Verde
                [0.66, '#fd7e14'],   # Laranja
                [1, '#6c757d']       # Cinza
            ]
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
                             targets: Dict[str, float],
                             equipment_names_dict: Dict[str, str]) -> dbc.Table:
    """
    Cria tabela resumo com todos KPIs por equipamento.

    Args:
        data_by_equipment: {
            "LONGI001": {"mtbf": 22.3, "mttr": 1.8, "breakdown_rate": 2.9},
            ...
        }
        targets: {"mtbf": 20.0, "mttr": 2.0, "breakdown_rate": 3.0}
        equipment_names_dict: Dicionário de nomes

    Returns:
        Componente dbc.Table
    """
    from src.utils.maintenance_demo_data import check_equipment_meets_targets

    # Ordenar equipamentos por ID
    sorted_equipment = sorted(data_by_equipment.keys())

    rows = []
    for eq_id in sorted_equipment:
        eq_data = data_by_equipment[eq_id]

        # Verificar se atende todas as metas
        meets_all = check_equipment_meets_targets(
            eq_data["mtbf"],
            eq_data["mttr"],
            eq_data["breakdown_rate"]
        )

        rows.append(
            html.Tr([
                html.Td(equipment_names_dict.get(eq_id, eq_id)),
                html.Td(
                    f"{eq_data['mtbf']:.1f}",
                    className="text-center"
                ),
                html.Td(
                    f"{eq_data['mttr']:.1f}",
                    className="text-center"
                ),
                html.Td(
                    f"{eq_data['breakdown_rate']:.1f}",
                    className="text-center"
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
                html.Th("MTBF (h)", className="text-center"),
                html.Th("MTTR (h)", className="text-center"),
                html.Th("Taxa Avaria (%)", className="text-center"),
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
                          template: str = 'minty') -> go.Figure:
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
    month_names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                   "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    x_labels = [month_names[m-1] for m in months_list]

    # Determinar se maior ou menor é melhor
    higher_is_better = kpi_name == "MTBF"

    # Calcular cores para cada barra baseado em performance
    bar_colors = []
    for value, avg_value in zip(values, avg_values):
        if higher_is_better:
            # MTBF: maior é melhor
            if value >= target_value:
                color = '#198754'  # Verde escuro - Excelente (atende meta)
            elif value >= avg_value:
                color = '#20c997'  # Verde claro - Bom (acima da média)
            elif value >= target_value * 0.8:
                color = '#ffc107'  # Amarelo - Atenção (próximo da meta)
            elif value >= target_value * 0.6:
                color = '#fd7e14'  # Laranja - Ruim (abaixo da média)
            else:
                color = '#dc3545'  # Vermelho - Crítico (muito abaixo)
        else:
            # MTTR e Taxa de Avaria: menor é melhor
            if value <= target_value:
                color = '#198754'  # Verde escuro - Excelente (atende meta)
            elif value <= avg_value:
                color = '#20c997'  # Verde claro - Bom (abaixo da média)
            elif value <= target_value * 1.2:
                color = '#ffc107'  # Amarelo - Atenção (próximo da meta)
            elif value <= target_value * 1.5:
                color = '#fd7e14'  # Laranja - Ruim (acima da média)
            else:
                color = '#dc3545'  # Vermelho - Crítico (muito acima)

        bar_colors.append(color)

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
        text=[f'{v:.1f}' for v in values],
        textposition='outside',
        textfont=dict(size=10),
        hovertemplate='<b>%{x}</b><br>Valor: %{y:.1f}<extra></extra>'
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

    unit = "h" if kpi_name in ["MTBF", "MTTR"] else "%"

    # Criar legenda de cores baseado no tipo de KPI
    if higher_is_better:
        color_legend = "Verde Escuro: ≥ Meta | Verde Claro: ≥ Média | Amarelo: < Média | Laranja/Vermelho: Abaixo"
    else:
        color_legend = "Verde Escuro: ≤ Meta | Verde Claro: ≤ Média | Amarelo: > Média | Laranja/Vermelho: Acima"

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
        equipment_data["mttr"],
        equipment_data["breakdown_rate"]
    ]
    avg_values = [
        general_avg["mtbf"],
        general_avg["mttr"],
        general_avg["breakdown_rate"]
    ]

    fig = go.Figure()

    # Barras do equipamento
    fig.add_trace(go.Bar(
        x=kpis,
        y=equipment_values,
        name=equipment_name,
        marker_color='#0d6efd',
        text=[f'{v:.1f}' for v in equipment_values],
        textposition='outside'
    ))

    # Barras da média geral
    fig.add_trace(go.Bar(
        x=kpis,
        y=avg_values,
        name='Média Geral',
        marker_color='#6c757d',
        text=[f'{v:.1f}' for v in avg_values],
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
