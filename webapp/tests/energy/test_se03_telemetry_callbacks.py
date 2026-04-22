"""Smoke tests para os callbacks de telemetria da SE03.

Cobre:
- Registro dos callbacks sem erro de configuração Dash.
- Criação do índice composto (DateTime, IDMaq) no startup.
- Robustez quando a coleção é None ou create_index falha.
"""
import pytest
from unittest.mock import MagicMock


def _make_app():
    """Cria Dash app mínimo para registro de callbacks em testes."""
    import dash
    import dash_bootstrap_components as dbc
    return dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
    )


class TestRegistroCallbacksSE03Telemetry:
    """Garante que register_se03_telemetry_callbacks() registra sem erro."""

    def test_register_com_collection_nao_levanta_excecao(self):
        from src.callbacks_registers.se03_telemetry_callbacks import (
            register_se03_telemetry_callbacks,
        )
        app = _make_app()
        collection = MagicMock()

        try:
            register_se03_telemetry_callbacks(app, collection)
        except Exception as e:
            pytest.fail(f"register_se03_telemetry_callbacks() falhou: {type(e).__name__}: {e}")

    def test_register_com_collection_none_nao_levanta_excecao(self):
        """Quando MongoDB está offline (collection=None), o registro ainda deve completar."""
        from src.callbacks_registers.se03_telemetry_callbacks import (
            register_se03_telemetry_callbacks,
        )
        app = _make_app()

        try:
            register_se03_telemetry_callbacks(app, None)
        except Exception as e:
            pytest.fail(f"Registro com collection=None falhou: {type(e).__name__}: {e}")


class TestCriacaoIndiceTelemetria:
    """Verifica que o índice (DateTime, IDMaq) é criado no startup."""

    def test_cria_indice_composto_quando_collection_disponivel(self):
        from src.callbacks_registers.se03_telemetry_callbacks import (
            register_se03_telemetry_callbacks,
        )
        app = _make_app()
        collection = MagicMock()

        register_se03_telemetry_callbacks(app, collection)

        collection.create_index.assert_called_once()
        args, kwargs = collection.create_index.call_args
        assert args[0] == [("DateTime", -1), ("IDMaq", 1)]
        assert kwargs.get("name") == "idx_telemetry_datetime_idmaq"
        assert kwargs.get("background") is True

    def test_nao_cria_indice_quando_collection_none(self):
        """Evita AttributeError quando MongoDB está offline."""
        from src.callbacks_registers.se03_telemetry_callbacks import (
            register_se03_telemetry_callbacks,
        )
        app = _make_app()
        register_se03_telemetry_callbacks(app, None)

    def test_falha_em_create_index_nao_quebra_registro(self):
        """Se create_index lançar (ex: permissão), os callbacks ainda devem registrar."""
        from src.callbacks_registers.se03_telemetry_callbacks import (
            register_se03_telemetry_callbacks,
        )
        app = _make_app()
        collection = MagicMock()
        collection.create_index.side_effect = RuntimeError("sem permissão")

        try:
            register_se03_telemetry_callbacks(app, collection)
        except Exception as e:
            pytest.fail(f"Falha em create_index propagou: {type(e).__name__}: {e}")
