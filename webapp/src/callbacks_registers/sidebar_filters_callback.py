# callbacks/sidebar_filters_callbacks.py

from dash.dependencies import Input, Output
from dash import html
from dash_bootstrap_templates import ThemeSwitchAIO

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

            # html.Label
            Output('label-date-range', 'style'),
            Output('label-start-hour', 'style'),
            Output('label-end-hour', 'style'),

            # dbc.Switch e seu tooltip
            Output('auto-update-switch', 'label'),
            Output('tooltip-target', 'className'),
        ],
        [Input(ThemeSwitchAIO.ids.switch("theme"), "value")]
    )
    def update_filter_styles(toggle):
        if toggle is None:
            toggle = True
        
        # ========== CORREÇÃO: INVERTIDO! ==========
        # toggle = True  -> TEMA CLARO (Minty)
        # toggle = False -> TEMA ESCURO (Darkly)
        
        # Cores para o tema CLARO (Minty) - quando toggle = True
        light_bg = "white"
        light_text = "black"
        light_border = "#ced4da"
        
        # Cores para o tema ESCURO (Darkly) - quando toggle = False
        dark_bg = "#303030"
        dark_text = "white"
        dark_border = "#495057"
        
        # Placeholders
        placeholder_start = "Data início"
        placeholder_end = "Data fim"

        # Estilos para DatePickerRange
        date_picker_style = {
            'width': '100%',
            'backgroundColor': light_bg if toggle else dark_bg,
            'color': light_text if toggle else dark_text,
            'border': f'1px solid {light_border if toggle else dark_border}',
            'borderRadius': '5px',
            'font-size': '13px'
        }
        # CORRIGIDO: Agora aplica a classe correta
        date_picker_class = "date-picker-light" if toggle else "date-picker-dark"

        # Estilos para Dropdowns
        dropdown_style = {
            'width': '150px',
            'backgroundColor': light_bg if toggle else dark_bg,
            'color': light_text if toggle else dark_text,
            'border': f'1px solid {light_border if toggle else dark_border}',
            'borderRadius': '5px',
            'font-size': '13px'
        }
        # CORRIGIDO: Agora aplica a classe correta
        dropdown_class = "dropdown-light" if toggle else "dropdown-dark"

        # Estilos para Labels
        label_style = {'color': light_text if toggle else dark_text}

        # Estilos para Switch e Tooltip
        switch_label_content = html.Span(
            "Atualização Automática (a cada 10s)",
            style={'color': light_text if toggle else dark_text}
        )
        tooltip_icon_class = f"bi bi-info-circle {'text-dark' if toggle else 'text-light'}"

        return (
            date_picker_style,
            date_picker_class,
            placeholder_start,
            placeholder_end,

            dropdown_style,
            dropdown_class,

            dropdown_style,
            dropdown_class,

            label_style,
            label_style,
            label_style,

            switch_label_content,
            tooltip_icon_class,
        )