# callbacks/callbacks.py
from dash.dependencies import Input, Output
from dash_bootstrap_templates import ThemeSwitchAIO # <--- ADICIONE ESTA IMPORTAÇÃ
from dash import callback_context # << Adicione callback_context

def register_storetheme_callbacks(app):
    @app.callback(
            Output('theme-store', 'data'),
            Output(ThemeSwitchAIO.ids.switch("theme"), "value"),
            Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
            Input('theme-store', 'data'),
        )
    def update_theme_store(switch_value, stored_theme):
        """
        Este callback sincroniza o interruptor de tema com o dcc.Store.
        SEMPRE inicia com tema Minty (claro).
        """
        # ctx.triggered_id nos diz qual Input acionou o callback
        triggered_id = callback_context.triggered_id

        # Se o callback foi acionado pelo interruptor (o usuário clicou nele)
        if triggered_id == ThemeSwitchAIO.ids.switch("theme"):
            # Salva o novo valor do interruptor no store e o retorna para o próprio interruptor
            return switch_value, switch_value

        # SEMPRE força tema Minty na inicialização (ignora stored_theme)
        # True = Minty (tema claro)
        return True, True

    # Callback para conectar o tema dinâmico ao Dash