"""Callbacks do Radar Lab (`/lab/radar`) — playground de radar dinâmico.

Desenho do fluxo:

    controles  ──▶  rl-store  ──▶  figura + painéis + tabela

Um único callback escreve no store (`_editar_estado`); todos os demais só leem.
Isso evita o clássico "dois callbacks disputando o mesmo estado" quando o usuário
adiciona um eixo e edita um nome quase ao mesmo tempo.

Como os painéis são re-renderizados a partir do store, os campos de texto voltam
a existir a cada mudança e disparam o callback de novo com o valor que já está
gravado. A comparação final (`novo == atual → PreventUpdate`) corta esse eco.
"""

import logging

from dash import ctx, html, no_update, ALL
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

try:
    from src.pages.lab import radar_lab as rl
except ImportError:  # execução fora do container, sem o pacote `src` na raiz
    from pages.lab import radar_lab as rl

logger = logging.getLogger("radar_lab")


def register_radar_lab_callbacks(app):
    """Registra os callbacks da página Radar Lab."""

    # ---------- ÚNICO ESCRITOR DO ESTADO ----------
    @app.callback(
        Output("rl-store", "data"),
        Output("rl-import-msg", "children"),
        # estrutura
        Input("rl-add-axis", "n_clicks"),
        Input("rl-add-layer", "n_clicks"),
        Input("rl-reset", "n_clicks"),
        Input("rl-import-apply", "n_clicks"),
        Input({"type": "rl-axis-del", "index": ALL}, "n_clicks"),
        Input({"type": "rl-axis-up", "index": ALL}, "n_clicks"),
        Input({"type": "rl-axis-down", "index": ALL}, "n_clicks"),
        Input({"type": "rl-layer-del", "index": ALL}, "n_clicks"),
        # edição de eixos
        Input({"type": "rl-axis-name", "index": ALL}, "value"),
        Input({"type": "rl-axis-desc", "index": ALL}, "value"),
        # edição de camadas
        Input({"type": "rl-layer-name", "index": ALL}, "value"),
        Input({"type": "rl-layer-color", "index": ALL}, "value"),
        Input({"type": "rl-layer-dash", "index": ALL}, "value"),
        Input({"type": "rl-layer-width", "index": ALL}, "value"),
        Input({"type": "rl-layer-opacity", "index": ALL}, "value"),
        Input({"type": "rl-layer-fill", "index": ALL}, "value"),
        Input({"type": "rl-layer-vis", "index": ALL}, "value"),
        # valores e opções
        Input("rl-values-table", "data"),
        Input("rl-title", "value"),
        Input("rl-range-mode", "value"),
        Input("rl-range-max", "value"),
        Input("rl-tick-step", "value"),
        Input("rl-hole", "value"),
        Input("rl-opt-legend", "value"),
        Input("rl-opt-labels", "value"),
        Input("rl-opt-grid", "value"),
        State("rl-import-text", "value"),
        State("rl-store", "data"),
        prevent_initial_call=True,
    )
    def _editar_estado(_add_axis, _add_layer, _reset, _import,
                       _del_axis, _up_axis, _down_axis, _del_layer,
                       _axis_names, _axis_descs,
                       _layer_names, _layer_colors, _layer_dashes,
                       _layer_widths, _layer_opacities, _layer_fills, _layer_vis,
                       table_rows, titulo, range_mode, range_max, tick_step, hole,
                       opt_legend, opt_labels, opt_grid,
                       import_text, atual):
        """Aplica a ação do controle que disparou e devolve o estado novo."""
        gatilho = ctx.triggered_id
        if gatilho is None:
            raise PreventUpdate

        atual = rl.normalize_state(atual)
        mensagem = no_update

        if isinstance(gatilho, dict):
            tipo, alvo = gatilho.get("type"), gatilho.get("index")
            valor = _valor_do_gatilho()

            if tipo == "rl-axis-del":
                novo = rl.remove_axis(atual, alvo)
            elif tipo == "rl-axis-up":
                novo = rl.move_axis(atual, alvo, -1)
            elif tipo == "rl-axis-down":
                novo = rl.move_axis(atual, alvo, +1)
            elif tipo == "rl-layer-del":
                novo = rl.remove_layer(atual, alvo)
            elif tipo == "rl-axis-name":
                novo = rl.update_axis(atual, alvo, "name", valor)
            elif tipo == "rl-axis-desc":
                novo = rl.update_axis(atual, alvo, "desc", valor)
            elif tipo and tipo.startswith("rl-layer-"):
                campo = tipo.replace("rl-layer-", "")
                campo = "visible" if campo == "vis" else campo
                novo = rl.update_layer(atual, alvo, campo, valor)
            else:
                raise PreventUpdate

        elif gatilho == "rl-add-axis":
            novo = rl.add_axis(atual)
        elif gatilho == "rl-add-layer":
            novo = rl.add_layer(atual)
        elif gatilho == "rl-reset":
            novo = rl.default_state()
        elif gatilho == "rl-import-apply":
            novo = rl.state_from_json(import_text, fallback=None)
            if novo is None:
                return no_update, html.Small(
                    "JSON inválido — nada foi alterado.", className="text-danger")
            mensagem = html.Small("Configuração importada.", className="text-success")
        elif gatilho == "rl-values-table":
            novo = rl.set_values_from_table(atual, table_rows)
        elif gatilho == "rl-title":
            novo = rl.set_option(atual, "title", titulo)
        elif gatilho == "rl-range-mode":
            novo = rl.set_option(atual, "range_mode", range_mode)
        elif gatilho == "rl-range-max":
            novo = rl.set_option(atual, "range_max", range_max)
        elif gatilho == "rl-tick-step":
            novo = rl.set_option(atual, "tick_step", tick_step)
        elif gatilho == "rl-hole":
            novo = rl.set_option(atual, "hole", hole)
        elif gatilho == "rl-opt-legend":
            novo = rl.set_option(atual, "legend", opt_legend)
        elif gatilho == "rl-opt-labels":
            novo = rl.set_option(atual, "labels", opt_labels)
        elif gatilho == "rl-opt-grid":
            novo = rl.set_option(atual, "grid", opt_grid)
        else:
            raise PreventUpdate

        if novo == atual and mensagem is no_update:
            # Eco do re-render dos painéis — nada mudou de fato.
            raise PreventUpdate
        return novo, mensagem

    def _valor_do_gatilho():
        """Valor atual do componente que disparou o callback (pattern-matching).

        Necessário porque com `ALL` o callback recebe listas: o índice do disparo
        precisa ser localizado dentro da lista do próprio tipo.
        """
        entrada = (ctx.triggered or [{}])[0]
        return entrada.get("value")

    # ---------- LEITORES ----------
    @app.callback(
        Output("rl-graph", "figure"),
        Input("rl-store", "data"),
        Input("theme-store", "data"),
    )
    def _desenhar(state, tema):
        """Redesenha o radar a cada mudança de estado ou de tema."""
        template = "darkly" if tema == "darkly" else "minty"
        return rl.build_figure(state, template=template)

    @app.callback(
        Output("rl-axes-panel", "children"),
        Output("rl-layers-panel", "children"),
        Output("rl-opts-panel", "children"),
        Output("rl-table-panel", "children"),
        Input("rl-store", "data"),
    )
    def _paineis(state):
        """Reconstrói eixos, camadas, controles de exibição e tabela de valores.

        Os três saem do store por `children` — nunca por `value` — porque
        devolver `value` a um componente que também é Input do escritor fecha
        um ciclo de dependência e o Dash 3 recusa o callback inteiro.
        """
        return (rl.render_axes_panel(state), rl.render_layers_panel(state),
                rl.render_options_panel(state), rl.render_values_table(state))

    @app.callback(
        Output("rl-download", "data"),
        Input("rl-export", "n_clicks"),
        State("rl-store", "data"),
        prevent_initial_call=True,
    )
    def _exportar(_n, state):
        """Baixa o estado atual como JSON — é o que o campo de importar recebe de volta."""
        return dict(content=rl.state_to_json(state), filename="radar-lab.json")

    logger.info("Callbacks do Radar Lab registrados")
