# callbacks/sidebar_filters_callbacks.py

from dash.dependencies import Input, Output
from dash import html

def register_sidebar_filter_callbacks(app):
    @app.callback(
        [
            # dcc.DatePickerRange
            Output('date-picker-range', 'style'),
            Output('date-picker-range', 'className'),
            Output('date-picker-range', 'start_date_placeholder_text'),
            Output('date-picker-range', 'end_date_placeholder_text'),

            # dcc.Dropdown - start-hour
            Output('start-hour', 'style'),
            Output('start-hour', 'className'),

            # dcc.Dropdown - end-hour
            Output('end-hour', 'style'),
            Output('end-hour', 'className'),

            # Dropdowns de máquinas
            Output('machine-dropdown-group1', 'className'),
            Output('machine-dropdown-group2', 'className'),

            # html.Label
            Output('label-date-range', 'style'),
            Output('label-start-hour', 'style'),
            Output('label-end-hour', 'style'),

            # Labels dos grupos de máquinas
            Output('label-group1', 'style'),
            Output('label-group2', 'style'),
        ],
        [Input('url', 'pathname')]  # Dummy input para não deixar callback vazio
    )
    def update_filter_styles(pathname):
        # ========== TEMA FIXO EM CLARO (Minty) ==========
        is_light_theme = True
        
        # Cores para o tema CLARO (Minty)
        light_bg = "white"
        light_text = "black"
        light_border = "#ced4da"
        
        # Cores para o tema ESCURO (Darkly)
        dark_bg = "#303030"
        dark_text = "white"
        dark_border = "#495057"
        
        # Seleciona cores baseado no tema
        bg_color = light_bg if is_light_theme else dark_bg
        text_color = light_text if is_light_theme else dark_text
        border_color = light_border if is_light_theme else dark_border
        
        # Placeholders
        placeholder_start = "Data início"
        placeholder_end = "Data fim"

        # Estilos para DatePickerRange
        date_picker_style = {
            'width': '100%',
            'backgroundColor': bg_color,
            'color': text_color,
            'border': f'1px solid {border_color}',
            'borderRadius': '5px',
            'font-size': '13px'
        }
        date_picker_class = "date-picker-light" if is_light_theme else "date-picker-dark"

        # Estilos para Dropdowns de hora
        dropdown_style = {
            'backgroundColor': bg_color,
            'color': text_color,
            'border': f'1px solid {border_color}',
            'borderRadius': '5px',
            'font-size': '13px'
        }
        dropdown_class = "dropdown-light" if is_light_theme else "dropdown-dark"

        # Classes para dropdowns de máquinas
        machine_dropdown_class_g1 = f"machine-dropdown-group1 {'dropdown-light' if is_light_theme else 'dropdown-dark'}"
        machine_dropdown_class_g2 = f"machine-dropdown-group2 {'dropdown-light' if is_light_theme else 'dropdown-dark'}"

        # Estilos para Labels
        label_style = {'color': text_color}

        # Estilos para Labels dos grupos (mantém cores originais)
        label_group1_style = {
            'color': '#1f77b4',  # Azul do Transversais
            'font-weight': 'bold',
            'margin-bottom': '5px'
        }
        label_group2_style = {
            'color': '#ff7f0e',  # Laranja do Longitudinais
            'font-weight': 'bold',
            'margin-bottom': '5px'
        }

        return (
            # DatePickerRange
            date_picker_style,
            date_picker_class,
            placeholder_start,
            placeholder_end,

            # Dropdown start-hour
            dropdown_style,
            dropdown_class,

            # Dropdown end-hour
            dropdown_style,
            dropdown_class,

            # Dropdowns de máquinas
            machine_dropdown_class_g1,
            machine_dropdown_class_g2,

            # Labels
            label_style,
            label_style,
            label_style,

            # Labels dos grupos
            label_group1_style,
            label_group2_style,
        )