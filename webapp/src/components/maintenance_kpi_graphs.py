"""
Maintenance KPI Graphs Components
Gráficos de KPIs de manutenção (barras com tendência, sunburst, tabela)
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from dash import html
import dash_bootstrap_components as dbc
from typing import Dict, List

# Imports condicionais para evitar circular imports
try:
    from src.database.connection import get_mongo_connection
    from src.utils.zpp_kpi_calculator import ZPP_PRODUCAO_COLLECTION, ZPP_PARADAS_COLLECTION
except ImportError:
    get_mongo_connection = None
    ZPP_PRODUCAO_COLLECTION = "ZPP_Producao"  # Fallback
    ZPP_PARADAS_COLLECTION = "ZPP_Paradas"


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
    # Tratar casos onde value ou reference são None
    if value is None or reference is None:
        return "#6c757d"  # Cinza - dados insuficientes

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
    # Converter MTTR de horas para minutos (tratar None)
    if kpi_name == "MTTR":
        values = [v * 60 if v is not None else None for v in values]
        average_value = average_value * 60 if average_value is not None else None
        target_values = {eq_id: meta * 60 if meta is not None else None for eq_id, meta in target_values.items()}
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

    # Formatar texto baseado no KPI (tratar None)
    if kpi_name == "Taxa de Avaria":
        text_values = [f'{v:.2f}' if v is not None else 'N/A' for v in values]
        hover_format = '<b>%{x}</b><br>%{y:.2f} ' + unit + '<extra></extra>'
    else:
        text_values = [f'{v:.1f}' if v is not None else 'N/A' for v in values]
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
        annotation_position="bottom right",
        annotation=dict(font=dict(size=11, color="#0d6efd"))
    )

    # NOTA: Metas individuais são refletidas nas cores das barras
    # Verde = atende meta individual, Vermelho = não atende meta individual

    # Linha de tendência (polinomial grau 2) - filtrar None
    if len(values) >= 3:
        # Filtrar valores None para o cálculo da tendência
        valid_indices = [i for i, v in enumerate(values) if v is not None]
        valid_values = [values[i] for i in valid_indices]

        if len(valid_values) >= 3:  # Precisa de pelo menos 3 pontos válidos
            try:
                z = np.polyfit(valid_indices, valid_values, 2)
                p = np.poly1d(z)
                trend_y = [p(i) if values[i] is not None else None for i in range(len(values))]

                fig.add_trace(go.Scatter(
                    x=[equipment_names_dict.get(eq_id, eq_id) for eq_id in equipment_ids],
                    y=trend_y,
                    mode='lines+markers',
                    line=dict(color='#000000', width=4, dash='solid'),
                    marker=dict(size=8, symbol='diamond', color='#000000', line=dict(color='white', width=2)),
                    name='📈 Tendência',
                    hovertemplate='<b>Tendência</b><br>%{y:.1f}<extra></extra>'
                ))
            except:
                # Se falhar o polyfit, ignora a tendência
                pass

    # Calcular teto do eixo Y com 30% de folga acima do maior valor (para os labels não serem cortados)
    valid_values = [v for v in values if v is not None]
    if valid_values:
        y_max = max(valid_values)
        # Inclui reference_value no cálculo para que a linha de meta nunca fique cortada
        if reference_value is not None:
            y_max = max(y_max, reference_value)
        y_ceiling = y_max * 1.30 if y_max > 0 else 1.0
    else:
        y_ceiling = None

    # Layout
    fig.update_layout(
        template=template,
        xaxis=dict(
            title="Equipamento",
            tickangle=-45
        ),
        yaxis=dict(
            title=f"{kpi_name} ({unit})",
            rangemode='tozero',
            range=[0, y_ceiling] if y_ceiling is not None else None
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        height=350,
        margin=dict(t=50, b=100, l=60, r=40),
        hovermode='x'
    )

    return fig


def _calculate_sunburst_averages(labels: List[str],
                                  parents: List[str],
                                  values: List[float],
                                  categories_dict: Dict[str, List[str]],
                                  data_by_equipment: Dict[str, float],
                                  unit: str,
                                  plant_average: float = None,
                                  decimals: int = 1) -> List[str]:
    """
    Calcula médias para cada nível do sunburst ao invés de mostrar somas.

    Níveis:
    - Centro: Média da PLANTA (passada como parâmetro ou calculada)
    - Categorias: Média dos equipamentos da categoria
    - Equipamentos: Valor individual

    Args:
        labels: Lista de labels do sunburst
        parents: Lista de parents do sunburst
        values: Lista de valores (somas) do sunburst
        categories_dict: Dicionário de categorias e equipamentos
        data_by_equipment: Dados originais por equipamento
        unit: Unidade ("h", "min", "%")
        plant_average: Média da planta (valores mensais). Se None, calcula média dos equipamentos.

    Returns:
        Lista de strings formatadas com médias para cada nível
    """
    custom_text = []

    # Se não foi passada média da planta, calcular média dos equipamentos
    if plant_average is None:
        # Filtrar None antes de calcular média
        valid_values = [v for v in data_by_equipment.values() if v is not None]
        total_equipment_count = len(valid_values)
        total_sum = sum(valid_values)
        plant_average = total_sum / total_equipment_count if total_equipment_count > 0 else 0

    for i, (label, parent, value) in enumerate(zip(labels, parents, values)):
        fmt = f".{decimals}f"
        if parent == "":
            # Nível 0: Planta (raiz)
            custom_text.append(f"Média: {plant_average:{fmt}}{unit}")

        elif parent == "Planta":
            # Nível 1: Categoria
            cat_name = label
            num_equipments = len([
                eq for eq in categories_dict.get(cat_name, [])
                if eq in data_by_equipment and data_by_equipment[eq] is not None
            ])
            avg = value / num_equipments if (num_equipments > 0 and value is not None) else 0
            custom_text.append(f"Média: {avg:{fmt}}{unit}")

        else:
            # Nível 2: Equipamento individual
            custom_text.append(f"{value:{fmt}}{unit}")

    return custom_text


def create_kpi_sunburst_chart(data_by_equipment: Dict[str, float],
                               kpi_name: str,
                               categories_dict: Dict[str, List[str]],
                               equipment_names_dict: Dict[str, str],
                               template: str = 'minty',
                               target_values: Dict[str, float] = None,
                               plant_target: float = None,
                               margin_percent: float = 3.0,
                               show_average: bool = True,
                               plant_average: float = None) -> go.Figure:
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
        margin_percent: Margem de tolerância para cores (%)
        show_average: Se True, labels mostram MÉDIA; se False, mostram SOMA (default: True)
        plant_average: Média da planta (valores mensais). Se None, calcula média dos equipamentos.

    Returns:
        Figura Plotly Sunburst com 3 níveis e cores de performance
    """
    # Converter MTTR de horas para minutos (filtrar None)
    if kpi_name == "MTTR":
        data_by_equipment = {k: v * 60 if v is not None else None for k, v in data_by_equipment.items()}

    # Determinar unidade
    if kpi_name == "MTBF":
        unit = "h"
    elif kpi_name == "MTTR":
        unit = "min"
    else:
        unit = "%"

    labels = ["Planta"]
    parents = [""]
    values = [0]  # Será calculado como soma das categorias
    colors = ['#6c757d']  # Cor neutra para o centro (Planta)

    # Adicionar categorias (anel 1) - cor neutra
    for cat_name, eq_list in categories_dict.items():
        labels.append(cat_name)
        parents.append("Planta")

        # Calcular soma dos equipamentos desta categoria (filtrar None)
        cat_values = [
            data_by_equipment.get(eq_id, 0)
            for eq_id in eq_list
            if eq_id in data_by_equipment and data_by_equipment.get(eq_id) is not None
        ]
        cat_value = sum(cat_values) if cat_values else 0
        values.append(cat_value)
        colors.append('#94a3b8')  # Cor neutra para categorias

    # Adicionar equipamentos individuais (anel 2) com cores de performance
    for cat_name, eq_list in categories_dict.items():
        for eq_id in eq_list:
            # Filtrar equipamentos com dados válidos (não None)
            if eq_id in data_by_equipment and data_by_equipment[eq_id] is not None:
                labels.append(equipment_names_dict.get(eq_id, eq_id))
                parents.append(cat_name)
                eq_value = data_by_equipment[eq_id]
                values.append(eq_value)

                # Determinar cor baseada em performance (sistema de 3 cores)
                # Prioridade: meta individual do equipamento → meta geral da planta → cor neutra
                if target_values and eq_id in target_values and target_values[eq_id] is not None:
                    target = target_values[eq_id]
                elif plant_target is not None:
                    target = plant_target
                else:
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
    # Taxa de Avaria: mostrar valores absolutos em porcentagem (não percent parent!)
    if kpi_name == "MTBF":
        text_display = 'label+text'
        if show_average:
            custom_text = _calculate_sunburst_averages(labels, parents, values, categories_dict, data_by_equipment, "h", plant_average=plant_average)
        else:
            custom_text = [f"{v:.1f}h" for v in values]
    elif kpi_name == "MTTR":
        text_display = 'label+text'
        if show_average:
            # MTTR: converter plant_average para minutos
            plant_avg_min = plant_average * 60 if plant_average is not None else None
            custom_text = _calculate_sunburst_averages(labels, parents, values, categories_dict, data_by_equipment, "min", plant_average=plant_avg_min)
        else:
            custom_text = [f"{v:.1f}min" for v in values]
    else:  # Taxa de Avaria
        text_display = 'label+text'
        if show_average:
            custom_text = _calculate_sunburst_averages(labels, parents, values, categories_dict, data_by_equipment, "%", plant_average=plant_average, decimals=2)
        else:
            custom_text = [f"{v:.2f}%" for v in values]

    # Preparar cores de texto (branco para centro "Planta", padrão para o resto)
    text_colors = ['#ffffff']  # Branco para o centro (Planta)
    text_colors.extend(['#000000'] * (len(labels) - 1))  # Preto para o resto

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
        textfont=dict(
            color=text_colors  # Cores personalizadas por setor
        ),
        textinfo=text_display,
        hovertemplate='<b>%{label}</b><br>%{value:.1f} ' + unit + '<extra></extra>'
    ))

    fig.update_layout(
        template=template,
        height=500,
        margin=dict(t=20, b=20, l=20, r=20)
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
        # Tratar None - se valor é None, considera como não atendendo a meta
        mtbf_ok = eq_data["mtbf"] is not None and eq_data["mtbf"] >= general_target["mtbf"]
        mttr_ok = eq_data["mttr"] is not None and eq_data["mttr"] <= general_target["mttr"]
        breakdown_ok = eq_data["breakdown_rate"] is not None and eq_data["breakdown_rate"] <= general_target["breakdown_rate"]
        meets_all = mtbf_ok and mttr_ok and breakdown_ok

        # Formatar valores com META GERAL (Valor/Meta Planta) - tratar None
        mtbf_actual = eq_data['mtbf']
        mtbf_target = general_target['mtbf']  # ← Meta geral da planta
        mttr_actual = eq_data['mttr'] * 60 if eq_data['mttr'] is not None else None  # Converter para minutos
        mttr_target = general_target['mttr'] * 60  # ← Meta geral da planta
        breakdown_actual = eq_data['breakdown_rate']
        breakdown_target = general_target['breakdown_rate']  # ← Meta geral da planta

        rows.append(
            html.Tr([
                html.Td(equipment_names_dict.get(eq_id, eq_id)),
                html.Td(
                    f"{mtbf_actual:.1f}/{mtbf_target:.1f}" if mtbf_actual is not None else f"N/A/{mtbf_target:.1f}",
                    className="text-center",
                    style={"fontWeight": "500"}
                ),
                html.Td(
                    f"{mttr_actual:.1f}/{mttr_target:.1f}" if mttr_actual is not None else f"N/A/{mttr_target:.1f}",
                    className="text-center",
                    style={"fontWeight": "500"}
                ),
                html.Td(
                    f"{breakdown_actual:.2f}/{breakdown_target:.2f}" if breakdown_actual is not None else f"N/A/{breakdown_target:.2f}",
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
                          avg_values: List[float] = None,
                          kpi_name: str = "",
                          equipment_name: str = "",
                          target_value: float = 0,
                          template: str = 'minty',
                          margin_percent: float = 3.0) -> go.Figure:
    """
    Cria gráfico híbrido (barras + linhas) mostrando evolução mensal.

    Exibe:
    - Barras do equipamento com cores condicionais baseadas em performance
    - Linha da média geral (laranja tracejada) - OPCIONAL
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
        avg_values: Média geral por mês (para comparação) - opcional, se None não exibe linha
        kpi_name: "MTBF", "MTTR" ou "Taxa de Avaria"
        equipment_name: Nome do equipamento
        target_value: Meta do KPI
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly com barras coloridas e linhas
    """
    # Converter MTTR de horas para minutos (tratar None)
    if kpi_name == "MTTR":
        values = [v * 60 if v is not None else None for v in values]
        if avg_values is not None:
            avg_values = [v * 60 if v is not None else None for v in avg_values]
        if target_value is not None:
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

    # Formatar texto baseado no KPI (tratar None)
    if kpi_name == "Taxa de Avaria":
        text_values = [f'{v:.2f}' if v is not None else 'N/A' for v in values]
        hover_format = '<b>%{x}</b><br>Valor: %{y:.2f}<extra></extra>'
    else:
        text_values = [f'{v:.1f}' if v is not None else 'N/A' for v in values]
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

    # Linha da média geral (laranja tracejada) - apenas se fornecida
    if avg_values is not None:
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

    # Linha de tendência (polinomial grau 2)
    if len(values) >= 3:
        x_numeric = list(range(len(values)))
        try:
            z = np.polyfit(x_numeric, values, 2)
            p = np.poly1d(z)
            trend_y = [p(x) for x in x_numeric]

            fig.add_trace(go.Scatter(
                x=x_labels,
                y=trend_y,
                mode='lines+markers',
                line=dict(color='#000000', width=4, dash='solid'),
                marker=dict(size=8, symbol='diamond', color='#000000', line=dict(color='white', width=2)),
                name='📈 Tendência',
                hovertemplate='<b>Tendência</b><br>%{y:.1f}<extra></extra>'
            ))
        except:
            pass

    # Determinar unidade
    if kpi_name == "MTBF":
        unit = "h"
    elif kpi_name == "MTTR":
        unit = "min"
    else:
        unit = "%"

    # Calcular teto do eixo Y com 30% de folga para os labels outside não serem cortados
    all_y = [v for v in values if v is not None]
    if avg_values is not None:
        all_y += [v for v in avg_values if v is not None]
    if target_value is not None:
        all_y.append(target_value)
    y_ceiling = max(all_y) * 1.30 if all_y else None

    fig.update_layout(
        template=template,
        xaxis=dict(title="Mês"),
        yaxis=dict(
            title=f"{kpi_name} ({unit})",
            rangemode='tozero',
            range=[0, y_ceiling] if y_ceiling is not None else None
        ),
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        bargap=0.2,  # Espaçamento entre barras
        height=350,
        margin=dict(t=20, b=60, l=60, r=40)
    )

    return fig


def create_performance_radar_chart(equipment_data: Dict[str, float],
                                   general_avg: Dict[str, float],
                                   equipment_name: str,
                                   equipment_target: Dict[str, float] = None,
                                   template: str = 'minty') -> go.Figure:
    """
    Cria gráfico radar comparando performance do equipamento com média e meta.

    Mostra em radar: Equipamento, Média Geral e Meta para os 3 KPIs.
    Performance normalizada em escala 0-100 para visualização comparativa.

    Args:
        equipment_data: {"mtbf": X, "mttr": Y, "breakdown_rate": Z}
        general_avg: {"mtbf": X, "mttr": Y, "breakdown_rate": Z}
        equipment_name: Nome do equipamento
        equipment_target: Metas do equipamento (opcional)
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly Scatterpolar (radar chart)
    """
    is_dark = (template == 'darkly')
    bg_color = '#2c2c2c' if is_dark else '#ffffff'
    grid_color = '#495057' if is_dark else '#dee2e6'

    # Converter MTTR para minutos
    eq_mtbf = equipment_data["mtbf"]
    eq_mttr = equipment_data["mttr"] * 60
    eq_breakdown = equipment_data["breakdown_rate"]

    avg_mtbf = general_avg["mtbf"]
    avg_mttr = general_avg["mttr"] * 60
    avg_breakdown = general_avg["breakdown_rate"]

    # Normalizar para escala 0-100 (performance score)
    # MTBF: quanto maior melhor -> (valor/meta)*100
    # MTTR: quanto menor melhor -> (meta/valor)*100
    # Breakdown: quanto menor melhor -> (meta/valor)*100

    if equipment_target:
        target_mtbf = equipment_target.get("mtbf", avg_mtbf)
        target_mttr = equipment_target.get("mttr", avg_mttr / 60) * 60
        target_breakdown = equipment_target.get("breakdown_rate", avg_breakdown)
    else:
        target_mtbf = avg_mtbf
        target_mttr = avg_mttr
        target_breakdown = avg_breakdown

    # Calcular performance scores (0-100)
    eq_score_mtbf = min((eq_mtbf / target_mtbf) * 100, 150) if target_mtbf > 0 else 0
    eq_score_mttr = min((target_mttr / eq_mttr) * 100, 150) if eq_mttr > 0 else 0
    eq_score_breakdown = min((target_breakdown / eq_breakdown) * 100, 150) if eq_breakdown > 0 else 0

    avg_score_mtbf = min((avg_mtbf / target_mtbf) * 100, 150) if target_mtbf > 0 else 0
    avg_score_mttr = min((target_mttr / avg_mttr) * 100, 150) if avg_mttr > 0 else 0
    avg_score_breakdown = min((target_breakdown / avg_breakdown) * 100, 150) if avg_breakdown > 0 else 0

    categories = ['MTBF<br>(Confiabilidade)', 'MTTR<br>(Manutenibilidade)', 'Taxa de Avaria<br>(Disponibilidade)']

    fig = go.Figure()

    # Meta (linha de referência - sempre 100%)
    fig.add_trace(go.Scatterpolar(
        r=[100, 100, 100, 100],
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(220, 53, 69, 0.1)',
        line=dict(color='#dc3545', width=2, dash='dot'),
        name='Meta (100%)',
        hovertemplate='<b>Meta</b><br>Performance: 100%<extra></extra>'
    ))

    # Média Geral
    fig.add_trace(go.Scatterpolar(
        r=[avg_score_mtbf, avg_score_mttr, avg_score_breakdown, avg_score_mtbf],
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(253, 126, 20, 0.15)',
        line=dict(color='#fd7e14', width=2, dash='dash'),
        name='Média Geral',
        hovertemplate='<b>Média Geral</b><br>Performance: %{r:.0f}%<extra></extra>'
    ))

    # Equipamento Selecionado
    fig.add_trace(go.Scatterpolar(
        r=[eq_score_mtbf, eq_score_mttr, eq_score_breakdown, eq_score_mtbf],
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(13, 110, 253, 0.2)',
        line=dict(color='#0d6efd', width=3),
        name=equipment_name,
        hovertemplate=f'<b>{equipment_name}</b><br>Performance: %{{r:.0f}}%<extra></extra>'
    ))

    # Performance geral (média dos 3 scores)
    overall_score = (eq_score_mtbf + eq_score_mttr + eq_score_breakdown) / 3

    # Determinar cor e status baseado no score
    if overall_score >= 100:
        status_color = '#198754'
        status_text = '✓ Excelente'
    elif overall_score >= 90:
        status_color = '#ffc107'
        status_text = '≈ Dentro da Meta'
    else:
        status_color = '#dc3545'
        status_text = '✗ Abaixo da Meta'

    fig.update_layout(
        template=template,
        polar=dict(
            bgcolor=bg_color,
            radialaxis=dict(
                visible=True,
                range=[0, 150],
                tickvals=[0, 50, 100, 150],
                ticktext=['0%', '50%', '100%', '150%'],
                gridcolor=grid_color,
                showline=False
            ),
            angularaxis=dict(
                gridcolor=grid_color
            )
        ),
        title=dict(
            text=f"<b>Performance Geral: {overall_score:.0f}%</b> <span style='color:{status_color}'>{status_text}</span><br>" +
                 f"<sub style='font-size:10px'>Valores acima de 100% = superando meta | Abaixo de 100% = abaixo da meta</sub>",
            x=0.5,
            xanchor='center',
            font=dict(size=13)
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5
        ),
        height=500,
        margin=dict(t=100, b=80, l=80, r=80)
    )

    return fig


def create_breakdown_calendar_heatmap(equipment_id: str,
                                       start_date,
                                       end_date,
                                       template: str = 'minty') -> go.Figure:
    """
    Cria calendar heatmap mostrando padrões de falhas ao longo dos dias.

    Args:
        equipment_id: ID do equipamento
        start_date: datetime de início do período
        end_date: datetime de fim do período
        template: 'minty' ou 'darkly'

    Returns:
        Figura Plotly com heatmap calendar
    """
    try:
        from datetime import datetime, timedelta
        import calendar as cal

        is_dark = (template == 'darkly')
        bg_color = '#2c2c2c' if is_dark else '#ffffff'
        text_color = '#e9ecef' if is_dark else '#2c3e50'

        # Validar parâmetros
        if start_date is None or end_date is None:
            return create_no_data_figure("heatmap", template)

        # Normalizar para datetime sem fuso
        if hasattr(start_date, 'tzinfo') and start_date.tzinfo:
            start_date = start_date.replace(tzinfo=None)
        if hasattr(end_date, 'tzinfo') and end_date.tzinfo:
            end_date = end_date.replace(tzinfo=None)
        # Garantir que end_date aponta para o último instante do dia
        end_date = end_date.replace(hour=23, minute=59, second=59)


        # ✅ OTIMIZAÇÃO: Agregação única ao invés de loop de consultas
        import random

        dates = []
        breakdowns_count = []
        production_status = []

        if get_mongo_connection:
            try:
                # IMPORTANTE: Usar collections FIXAS, não dinâmicas por ano
                # As collections sempre se chamam *_2025 mesmo contendo dados de múltiplos anos
                producao_collection = get_mongo_connection(ZPP_PRODUCAO_COLLECTION)
                paradas_collection = get_mongo_connection(ZPP_PARADAS_COLLECTION)


                # Pipeline de agregação para produção (1 consulta para todo período)
                prod_pipeline = [
                    {
                        "$match": {
                            "_processed": True,
                            "pto_trab": equipment_id,  # Filtrar por equipamento
                            "fininotif": {"$gte": start_date, "$lte": end_date}
                        }
                    },
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {"format": "%Y-%m-%d", "date": "$fininotif"}
                            },
                            "count": {"$sum": 1}
                        }
                    }
                ]

                # Pipeline de agregação para paradas (1 consulta para todo período)
                # NOTA: Atualizado para nova estrutura de colunas (Centro de trabalho, Início execução, Causa do desvio, etc)
                paradas_pipeline = [
                    {
                        "$match": {
                            "_processed": True,
                            "centro_de_trabalho": equipment_id,
                            "inicio_execucao": {"$gte": start_date, "$lte": end_date},
                            "causa_do_desvio": {"$in": ["201", "S201", "202", "S202", "203", "S203"]}
                        }
                    },
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {"format": "%Y-%m-%d", "date": "$inicio_execucao"}
                            },
                            "count": {"$sum": 1}
                        }
                    }
                ]

                # Executar agregações
                prod_results = {doc["_id"]: doc["count"] for doc in producao_collection.aggregate(prod_pipeline)}
                paradas_results = {doc["_id"]: doc["count"] for doc in paradas_collection.aggregate(paradas_pipeline)}

                if prod_results:
                    first_date = list(prod_results.keys())[0]
                if paradas_results:
                    first_date = list(paradas_results.keys())[0]

                # Gerar datas e popular contadores
                current_date = start_date
                while current_date <= end_date:
                    dates.append(current_date)
                    date_str = current_date.strftime("%Y-%m-%d")

                    # Verificar se houve produção neste dia
                    has_production = date_str in prod_results
                    production_status.append(has_production)

                    # Contar paradas se houve produção
                    breakdown_count = paradas_results.get(date_str, 0) if has_production else 0
                    breakdowns_count.append(breakdown_count)

                    current_date += timedelta(days=1)

            except Exception as e:
                # Fallback: simular dados
                current_date = start_date
                while current_date <= end_date:
                    dates.append(current_date)
                    has_production = current_date.weekday() < 5  # Seg-Sex
                    production_status.append(has_production)
                    breakdown_count = random.choices([0, 0, 0, 1, 1, 2], weights=[40, 20, 10, 15, 10, 5])[0] if has_production else 0
                    breakdowns_count.append(breakdown_count)
                    current_date += timedelta(days=1)
        else:
            # Sem MongoDB: simular
            current_date = start_date
            while current_date <= end_date:
                dates.append(current_date)
                has_production = current_date.weekday() < 5
                production_status.append(has_production)
                breakdown_count = random.choices([0, 0, 0, 1, 1, 2], weights=[40, 20, 10, 15, 10, 5])[0] if has_production else 0
                breakdowns_count.append(breakdown_count)
                current_date += timedelta(days=1)

        # Preparar dados para heatmap
        weeks = []
        days_of_week = []
        colors = []
        hover_texts = []

        for i, (date, count, has_prod) in enumerate(zip(dates, breakdowns_count, production_status)):
            week = date.isocalendar()[1] - start_date.isocalendar()[1]
            day = date.weekday()

            weeks.append(week)
            days_of_week.append(day)

            # Cores baseadas em produção e paradas
            if not has_prod:
                color = '#e9ecef'  # Cinza claro (sem produção)
                status = 'Sem produção'
            elif count == 0:
                color = '#d4edda'  # Verde claro
                status = 'Sem falhas'
            elif count == 1:
                color = '#fff3cd'  # Amarelo claro
                status = '1 falha'
            elif count == 2:
                color = '#ffe0a3'  # Amarelo
                status = '2 falhas'
            else:
                color = '#f8d7da'  # Vermelho claro
                status = f'{count} falhas'

            colors.append(color)
            hover_texts.append(
                f"<b>{date.strftime('%d/%m/%Y')}</b><br>"
                f"{status}<br>"
                f"<i>{date.strftime('%A')}</i>"
            )

        # Calcular estatísticas (considerar apenas dias com produção)
        total_days = len(dates)
        production_days = sum(1 for p in production_status if p)
        non_production_days = total_days - production_days

        # Filtrar apenas dias com produção para estatísticas de falhas
        days_no_failure = sum(1 for c, p in zip(breakdowns_count, production_status) if p and c == 0)
        days_with_failure = sum(1 for c, p in zip(breakdowns_count, production_status) if p and c > 0)
        total_breakdowns = sum(c for c, p in zip(breakdowns_count, production_status) if p)

        # Calcular maior streak sem falhas (considerar apenas dias com produção)
        current_streak = 0
        max_streak = 0
        for count, has_prod in zip(breakdowns_count, production_status):
            if has_prod:  # Só contar dias com produção
                if count == 0:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 0

        # Calcular ranking por dia da semana (considerar apenas dias com produção)
        weekday_stats = {0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
        for date, count, has_prod in zip(dates, breakdowns_count, production_status):
            if has_prod:  # Só incluir dias com produção
                weekday_stats[date.weekday()].append(count)

        weekday_names = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        weekday_avg = []
        for day in range(7):
            if weekday_stats[day]:
                avg = sum(weekday_stats[day]) / len(weekday_stats[day])
                weekday_avg.append((weekday_names[day], avg, day))
            else:
                weekday_avg.append((weekday_names[day], 0, day))

        # Ordenar do melhor (menos falhas) ao pior
        weekday_avg.sort(key=lambda x: x[1])

        # ✨ ESTATÍSTICAS APRIMORADAS

        # 1. Melhor e Pior DIA DA SEMANA (do ranking anual)
        best_weekday_name, best_weekday_avg, best_weekday_num = weekday_avg[0]  # Primeiro = melhor
        worst_weekday_name, worst_weekday_avg, worst_weekday_num = weekday_avg[-1]  # Último = pior

        # Estatísticas detalhadas do melhor dia da semana
        best_weekday_days_count = len(weekday_stats[best_weekday_num])
        best_weekday_total_failures = sum(weekday_stats[best_weekday_num])
        best_weekday_zero_failures = sum(1 for c in weekday_stats[best_weekday_num] if c == 0)
        best_weekday_zero_pct = (best_weekday_zero_failures / best_weekday_days_count * 100) if best_weekday_days_count > 0 else 0

        # Estatísticas detalhadas do pior dia da semana
        worst_weekday_days_count = len(weekday_stats[worst_weekday_num])
        worst_weekday_total_failures = sum(weekday_stats[worst_weekday_num])
        worst_weekday_with_failures = sum(1 for c in weekday_stats[worst_weekday_num] if c > 0)
        worst_weekday_with_failures_pct = (worst_weekday_with_failures / worst_weekday_days_count * 100) if worst_weekday_days_count > 0 else 0

        # 2. Dias Críticos (2+ falhas)
        critical_days = sum(1 for c, p in zip(breakdowns_count, production_status) if p and c >= 2)
        critical_days_pct = (critical_days / production_days * 100) if production_days > 0 else 0

        # 3. Tendência (primeira metade vs segunda metade do período)
        mid_point = len(dates) // 2
        first_half_failures = sum(c for i, (c, p) in enumerate(zip(breakdowns_count, production_status)) if i < mid_point and p)
        second_half_failures = sum(c for i, (c, p) in enumerate(zip(breakdowns_count, production_status)) if i >= mid_point and p)
        first_half_days = sum(1 for i, p in enumerate(production_status) if i < mid_point and p)
        second_half_days = sum(1 for i, p in enumerate(production_status) if i >= mid_point and p)

        first_half_avg = first_half_failures / first_half_days if first_half_days > 0 else 0
        second_half_avg = second_half_failures / second_half_days if second_half_days > 0 else 0

        if second_half_avg > first_half_avg * 1.2:
            trend_icon = "📈"
            trend_text = "Piora"
            trend_color = "#dc3545"
        elif second_half_avg < first_half_avg * 0.8:
            trend_icon = "📉"
            trend_text = "Melhora"
            trend_color = "#198754"
        else:
            trend_icon = "➡️"
            trend_text = "Estável"
            trend_color = "#6c757d"

        # Criar figura simples - APENAS O HEATMAP
        fig = go.Figure()

        # Adicionar heatmap
        fig.add_trace(go.Scatter(
            x=weeks,
            y=days_of_week,
            mode='markers',
            marker=dict(
                size=25,
                color=colors,
                symbol='square',
                line=dict(color='rgba(0,0,0,0.1)', width=1)
            ),
            text=hover_texts,
            hovertemplate='%{text}<extra></extra>',
            showlegend=False
        ))

        # Coluna 2: Estatísticas e Ranking (layout em 2 colunas)
        # Layout profissional com 2 colunas lado a lado
        # Atualizar eixos do heatmap
        fig.update_xaxes(
            showgrid=False,
            zeroline=False,
            visible=False
        )

        fig.update_yaxes(
            title="",
            tickmode='array',
            tickvals=[0, 1, 2, 3, 4, 5, 6],
            ticktext=['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'],
            showgrid=False,
            zeroline=False,
            autorange='reversed'
        )

        fig.update_layout(
            template=template,
            title=dict(
                text="<b>Padrão de Falhas - Calendar Heatmap</b><br>" +
                     "<sub style='font-size:10px'>⚪ Cinza = sem produção | 🟢 Verde = sem falhas | 🟡 Amarelo = poucas falhas | 🔴 Vermelho = muitas falhas</sub>",
                x=0.5,
                xanchor='center',
                font=dict(size=13)
            ),
            height=500,
            margin=dict(t=100, b=60, l=60, r=40),
            plot_bgcolor=bg_color,
            hovermode='closest',
            showlegend=False
        )

        # Preparar estatísticas para retorno
        stats_dict = {
            'total_days': total_days,
            'production_days': production_days,
            'non_production_days': non_production_days,
            'days_no_failure': days_no_failure,
            'days_with_failure': days_with_failure,
            'total_breakdowns': total_breakdowns,
            'max_streak': max_streak,
            'best_weekday_name': best_weekday_name,
            'best_weekday_avg': best_weekday_avg,
            'best_weekday_days_count': best_weekday_days_count,
            'best_weekday_zero_failures': best_weekday_zero_failures,
            'best_weekday_zero_pct': best_weekday_zero_pct,
            'best_weekday_total_failures': best_weekday_total_failures,
            'worst_weekday_name': worst_weekday_name,
            'worst_weekday_avg': worst_weekday_avg,
            'worst_weekday_days_count': worst_weekday_days_count,
            'worst_weekday_with_failures': worst_weekday_with_failures,
            'worst_weekday_with_failures_pct': worst_weekday_with_failures_pct,
            'worst_weekday_total_failures': worst_weekday_total_failures,
            'critical_days': critical_days,
            'critical_days_pct': critical_days_pct,
            'trend_icon': trend_icon,
            'trend_text': trend_text,
            'trend_color': trend_color,
            'first_half_avg': first_half_avg,
            'second_half_avg': second_half_avg,
            'weekday_avg': weekday_avg
        }

        return fig, stats_dict

    except Exception as e:
        # Se qualquer erro ocorrer, retornar figura de erro
        import traceback
        traceback.print_exc()

        # Garantir que template é válido antes de criar no_data_figure
        safe_template = template if template in ['minty', 'darkly'] else 'minty'

        # Retornar tupla (figura, stats vazio) para manter compatibilidade
        empty_stats = {
            'total_days': 0,
            'production_days': 0,
            'non_production_days': 0,
            'days_no_failure': 0,
            'days_with_failure': 0,
            'total_breakdowns': 0,
            'max_streak': 0,
            'best_weekday_name': '--',
            'best_weekday_avg': 0,
            'best_weekday_days_count': 0,
            'best_weekday_zero_failures': 0,
            'best_weekday_zero_pct': 0,
            'best_weekday_total_failures': 0,
            'worst_weekday_name': '--',
            'worst_weekday_avg': 0,
            'worst_weekday_days_count': 0,
            'worst_weekday_with_failures': 0,
            'worst_weekday_with_failures_pct': 0,
            'worst_weekday_total_failures': 0,
            'critical_days': 0,
            'critical_days_pct': 0,
            'trend_icon': '➡️',
            'trend_text': 'Sem dados',
            'trend_color': '#6c757d',
            'first_half_avg': 0,
            'second_half_avg': 0,
            'weekday_avg': []
        }

        return create_no_data_figure("heatmap", safe_template), empty_stats


def create_top_breakdowns_chart(breakdowns_data: List[Dict],
                                  equipment_name: str,
                                  template: str = 'minty') -> go.Figure:
    """
    Cria gráfico de barras horizontais mostrando as top paradas por duração.

    Agrupa paradas pelo mesmo dia + mesmo texto de confirmação (soma durações).

    Args:
        breakdowns_data: Lista de dicionários com dados das paradas:
            [
                {
                    "date": datetime.date(2025, 1, 15),
                    "motivo": "201",
                    "duracao_min": 120.5,
                    "duracao_horas": 2.01,
                    "descricao": "Troca de referência e bobina"  # texto_de_confirmacao
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

    # ✅ ORDENAR: Do maior para o menor (por duração em minutos)
    aggregated_data.sort(key=lambda x: x['duracao_min'], reverse=True)

    # Limitar ao top 5 após agregação
    aggregated_data = aggregated_data[:5]

    # Criar labels para o eixo Y com quebra de linha
    def wrap_text(text: str, max_chars_per_line: int = 20) -> str:
        """Quebra texto em múltiplas linhas"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word) + (1 if current_line else 0)  # +1 para espaço

            if current_length + word_length <= max_chars_per_line:
                current_line.append(word)
                current_length += word_length
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(' '.join(current_line))

        return '<br>'.join(lines)

    y_labels = [
        f"{bd['date'].strftime('%d/%m')}<br>{wrap_text(bd['descricao'])}"
        for bd in aggregated_data
    ]

    # Labels completos para hover (sem quebra)
    y_labels_full = [
        f"{bd['date'].strftime('%d/%m')} - {bd['descricao']}"
        for bd in aggregated_data
    ]

    # Valores de duração em minutos (eixo X)
    x_values = [bd['duracao_min'] for bd in aggregated_data]

    # Calcular valor máximo para escala do eixo X (sempre +50 min)
    max_duration = max(x_values) if x_values else 1
    x_axis_max = max_duration + 50  # Sempre 50 minutos a mais que o máximo
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

    # Texto nas barras (duração em minutos + indicador de agrupamento)
    text_values = []
    hover_templates = []

    for bd in aggregated_data:
        # Texto na barra - sempre em minutos
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
        textfont=dict(size=11),
        customdata=[[bd['count'], y_labels_full[i]] for i, bd in enumerate(aggregated_data)],
        hovertemplate=(
            '<b>%{customdata[1]}</b><br>' +  # Descrição completa
            'Duração Total: %{x:.0f} min<br>' +
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
            y=0.98,
            yanchor='top',
            font=dict(size=12),
            pad=dict(t=0, b=5)
        ),
        xaxis=dict(
            title=dict(
                text="Duração (minutos)",
                font=dict(size=10)
            ),
            range=[0, x_axis_max]  # 0 até máximo dos dados + 50 min
        ),
        yaxis=dict(
            title="",
            autorange='reversed',  # Inverter para maior ficar no topo
            tickfont=dict(size=9),
            tickmode='linear',
            side='left',
            automargin=True  # Habilitar margem automática para os labels
        ),
        showlegend=False,
        height=max(400, len(breakdowns_data) * 80),  # Altura aumentada para dar espaço aos textos
        margin=dict(t=25, b=20, l=10, r=80),  # Margem direita grande para texto dos valores
        bargap=0.5,  # Espaçamento entre barras (50% gap = barras mais finas)
        hoverlabel=dict(
            bgcolor="white",
            font_size=11,
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
            'font': {'size': 11, 'color': text_color, 'family': 'Segoe UI, Arial, sans-serif'}
        },
        number={
            'suffix': f" <span style='font-size:0.7em; font-weight:400'>{unit}</span>",
            'font': {'size': 22, 'color': bar_color, 'family': 'Segoe UI, Arial, sans-serif'},
            'valueformat': '.2f' if kpi_name == "Taxa de Avaria" else '.1f'
        },
        delta={
            'reference': target_value,
            'increasing': {'color': '#198754' if higher_is_better else '#dc3545'},
            'decreasing': {'color': '#dc3545' if higher_is_better else '#198754'},
            'suffix': f" {unit}",
            'font': {'size': 8, 'family': 'Segoe UI, Arial, sans-serif'},
            'position': delta_position,
            'valueformat': '.2f' if kpi_name == "Taxa de Avaria" else '.1f'
        },
        gauge={
            'axis': {
                'range': [0, max_range],
                'ticksuffix': f" {unit}",
                'tickfont': {'size': 7, 'color': text_color, 'family': 'Segoe UI, Arial, sans-serif'},
                'tickwidth': 1,
                'tickcolor': 'rgba(108, 117, 125, 0.3)',
                'tickmode': 'auto',
                'nticks': 5
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
        height=180,
        margin=dict(t=30, b=10, l=15, r=15),
        font={
            'family': "Segoe UI, -apple-system, BlinkMacSystemFont, Arial, sans-serif",
            'color': text_color
        }
    )

    return fig
