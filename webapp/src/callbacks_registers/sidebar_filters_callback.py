# callbacks/sidebar_filters_callbacks.py

from dash.dependencies import Input, Output
from dash import html # Ainda útil para o label do switch
from dash_bootstrap_templates import ThemeSwitchAIO

def register_sidebar_filter_callbacks(app):
    @app.callback(
        [
            # dcc.DatePickerRange
            Output('date-picker-range', 'style'),
            Output('date-picker-range', 'className'), # Adicionado className
            Output('date-picker-range', 'start_date_placeholder_text'), # Agora espera string
            Output('date-picker-range', 'end_date_placeholder_text'),   # Agora espera string

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
        # Cores para o tema escuro (Darkly)
        dark_bg = "#303030"
        dark_text = "white"
        dark_border = "#495057"
        dark_placeholder_text = "Data início" # String simples
        dark_placeholder_end = "Data fim"     # String simples

        # Cores para o tema claro (Minty)
        light_bg = "white"
        light_text = "black"
        light_border = "#ced4da"
        light_placeholder_text = "Data início" # String simples
        light_placeholder_end = "Data fim"     # String simples

        # Estilos para DatePickerRange
        date_picker_style = {
            'width': '100%',
            'backgroundColor': light_bg if toggle else  dark_bg,
            'color': light_text if toggle else  dark_text,
            'border': f'1px solid {light_border if toggle else  dark_border}',
            'borderRadius': '5px',
            'font-size': '13px'
        }
        date_picker_class = "date-picker-dark" if toggle else "date-picker-light"


        # Estilos para Dropdowns
        dropdown_style = {
            'width': '150px',
            'backgroundColor': light_bg if toggle else  dark_bg,
            'color': light_text if toggle else  dark_text,
            'border': f'1px solid {light_border if toggle else  dark_border}',
            'borderRadius': '5px',
            'font-size': '13px'
        }
        dropdown_class = "dropdown-dark" if toggle else "dropdown-light"


        # Estilos para Labels
        label_style = {'color': light_text if toggle else  dark_text}

        # Estilos para Switch e Tooltip
        switch_label_content = html.Span(
            "Atualização Automática (a cada 10s)",
            style={'color': light_text if toggle else  dark_text}
        )
        tooltip_icon_class = f"bi bi-info-circle {'text-light' if toggle else 'text-dark'}"


        return (
            date_picker_style,
            date_picker_class, # Retorna a classe
            dark_placeholder_text if toggle else light_placeholder_text, # Retorna string
            dark_placeholder_end if toggle else light_placeholder_end,   # Retorna string

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

