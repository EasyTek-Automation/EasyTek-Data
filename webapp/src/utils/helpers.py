from datetime import datetime

def validate_time_format(time_str):
    try:
        return datetime.strptime(time_str, '%H:%M').strftime('%H:%M')
    except ValueError:
        return None