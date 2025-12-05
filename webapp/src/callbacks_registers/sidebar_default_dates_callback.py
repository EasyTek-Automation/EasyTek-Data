"""Callbacks para atualizar os valores padrão da sidebar a cada refresh."""

from datetime import datetime, timedelta

from dash import Input, Output


def _generate_time_ranges():
    """Cria datas e faixas de horários arredondadas para os últimos 30 minutos."""
    now = datetime.now()
    rounded_minutes = (now.minute + 29) // 30 * 30
    rounded_now = (now + timedelta(minutes=rounded_minutes - now.minute)).replace(
        second=0, microsecond=0
    )
    last_24_hours = [
        (rounded_now - timedelta(minutes=30 * step)).strftime("%H:%M") for step in range(48)
    ]
    options = [{"label": hour, "value": hour} for hour in reversed(last_24_hours)]

    return {
        "start_date": (now - timedelta(hours=24)).date(),
        "end_date": now.date(),
        "start_hour": last_24_hours[-1],
        "end_hour": last_24_hours[0],
        "options": options,
    }


def register_sidebar_default_dates_callback(app):
    @app.callback(
        Output("date-picker-range", "start_date"),
        Output("date-picker-range", "end_date"),
        Output("start-hour", "options"),
        Output("start-hour", "value"),
        Output("end-hour", "options"),
        Output("end-hour", "value"),
        Input("url", "pathname"),
    )
    def update_sidebar_defaults(_):
        ranges = _generate_time_ranges()
        return (
            ranges["start_date"],
            ranges["end_date"],
            ranges["options"],
            ranges["start_hour"],
            ranges["options"],
            ranges["end_hour"],
        )