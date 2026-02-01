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
                         target_values: Dict[str, float],  # ALTERADO: Dict de metas por equipamento
                         equipment_names_dict: Dict[str, str],
                         template: str = 'minty') -> go.Figure:
    """
    Cria gráfico de barras com média e metas individualizadas por equipamento.

    Args:
        equipment_ids: Lista de IDs dos equipamentos
        values: Lista de valores do KPI
        kpi_name: "MTBF", "MTTR" ou "Taxa de Avaria"
        average_value: Valor médio calculado
        target_values: Dicionário de metas {equipment_id: meta_value}
        equipment_names_dict: Dicionário de nomes
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly com barras, linhas de média e tendência
    """
    # Converter MTTR de horas para minutos
    if kpi_name == "MTTR":
        values = [v * 60 for v in values]
        average_value = average_value * 60
        target_values = {eq_id: meta * 60 for eq_id, meta in target_values.items()}

    # Determinar unidade
    if kpi_name == "MTBF":
        unit = "h"
    elif kpi_name == "MTTR":
        unit = "min"
    else:
        unit = "%"

    # Lógica de cores das barras (verde: atende meta individual, vermelho: não atende)
    bar_colors = []
    for eq_id, val in zip(equipment_ids, values):
        # Obter meta específica do equipamento (fallback para média geral)
        eq_target = target_values.get(eq_id, average_value)

        if kpi_name == "MTBF":
            # Maior é melhor
            color = '#20c997' if val >= eq_target else '#dc3545'
        else:
            # Menor é melhor (MTTR, Taxa Avaria)
            color = '#20c997' if val <= eq_target else '#dc3545'
        bar_colors.append(color)

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

    # Linha de média (azul tracejada)
    fig.add_hline(
        y=average_value,
        line_dash="dash",
        line_color="#0d6efd",
        line_width=2,
        annotation_text=f"Média Geral: {average_value:.1f} {unit}",
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

        # Obter meta específica do equipamento (ou usar meta geral como fallback)
        eq_target = targets.get(eq_id, general_target)

        # Verificar se atende todas as metas INDIVIDUAIS
        mtbf_ok = eq_data["mtbf"] >= eq_target["mtbf"]
        mttr_ok = eq_data["mttr"] <= eq_target["mttr"]
        breakdown_ok = eq_data["breakdown_rate"] <= eq_target["breakdown_rate"]
        meets_all = mtbf_ok and mttr_ok and breakdown_ok

        rows.append(
            html.Tr([
                html.Td(equipment_names_dict.get(eq_id, eq_id)),
                html.Td(
                    f"{eq_data['mtbf']:.1f}",
                    className="text-center"
                ),
                html.Td(
                    f"{eq_data['mttr'] * 60:.1f}",
                    className="text-center"
                ),
                html.Td(
                    f"{eq_data['breakdown_rate']:.2f}",
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
                html.Th("MTTR (min)", className="text-center"),
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
    # Converter MTTR de horas para minutos
    if kpi_name == "MTTR":
        values = [v * 60 for v in values]
        avg_values = [v * 60 for v in avg_values]
        target_value = target_value * 60

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
                     template: str = 'minty') -> go.Figure:
    """
    Cria gráfico gauge (velocímetro) para um KPI individual.

    Args:
        value: Valor atual do KPI
        kpi_name: "MTBF", "MTTR" ou "Taxa de Avaria"
        target_value: Meta do KPI
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly com gauge indicator
    """
    # Converter MTTR de horas para minutos
    if kpi_name == "MTTR":
        value = value * 60
        target_value = target_value * 60

    # Determinar unidade e configurações específicas
    if kpi_name == "MTBF":
        unit = "h"
        max_range = max(target_value * 2, value * 1.2)  # Range dinâmico
        higher_is_better = True
        # Zonas do gauge (verde-amarelo-vermelho)
        steps = [
            {'range': [0, target_value * 0.5], 'color': '#dc3545'},      # Vermelho: muito abaixo
            {'range': [target_value * 0.5, target_value], 'color': '#ffc107'},  # Amarelo: abaixo da meta
            {'range': [target_value, max_range], 'color': '#20c997'}     # Verde: acima da meta
        ]
    elif kpi_name == "MTTR":
        unit = "min"
        max_range = max(target_value * 2, value * 1.2)
        higher_is_better = False
        # Zonas invertidas (menor é melhor)
        steps = [
            {'range': [0, target_value], 'color': '#20c997'},            # Verde: abaixo da meta
            {'range': [target_value, target_value * 1.5], 'color': '#ffc107'},  # Amarelo: acima da meta
            {'range': [target_value * 1.5, max_range], 'color': '#dc3545'}  # Vermelho: muito acima
        ]
    else:  # Taxa de Avaria
        unit = "%"
        max_range = max(target_value * 2, value * 1.2, 10)  # Mínimo de 10%
        higher_is_better = False
        steps = [
            {'range': [0, target_value], 'color': '#20c997'},
            {'range': [target_value, target_value * 1.5], 'color': '#ffc107'},
            {'range': [target_value * 1.5, max_range], 'color': '#dc3545'}
        ]

    # Determinar cor da barra atual
    if higher_is_better:
        bar_color = '#20c997' if value >= target_value else '#dc3545'
    else:
        bar_color = '#20c997' if value <= target_value else '#dc3545'

    # Criar gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={
            'text': f"<b>{kpi_name}</b>",
            'font': {'size': 18}
        },
        number={
            'suffix': f" {unit}",
            'font': {'size': 32}
        },
        delta={
            'reference': target_value,
            'increasing': {'color': '#20c997' if higher_is_better else '#dc3545'},
            'decreasing': {'color': '#dc3545' if higher_is_better else '#20c997'},
            'suffix': f" {unit}"
        },
        gauge={
            'axis': {
                'range': [0, max_range],
                'ticksuffix': f" {unit}",
                'tickfont': {'size': 12}
            },
            'bar': {'color': bar_color, 'thickness': 0.75},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': steps,
            'threshold': {
                'line': {'color': "#0d6efd", 'width': 3},
                'thickness': 0.75,
                'value': target_value
            }
        }
    ))

    # Layout
    fig.update_layout(
        template=template,
        height=280,
        margin=dict(t=40, b=10, l=20, r=20),
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': "Arial"}
    )

    return fig
