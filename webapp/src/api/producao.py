# src/api/producao.py
"""
Endpoints de dados de produção (OEE, estados, alarmes)
"""

from flask import jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from src.database.connection import get_mongo_connection
from . import api_bp


@api_bp.route('/producao/oee', methods=['GET'])
@login_required
def get_oee_data():
    """
    Retorna dados de OEE de uma linha de produção.

    Query params:
    - linha: Nome da linha (padrão: LCT08)
    - data_inicio: ISO format (padrão: 7 dias atrás)
    - data_fim: ISO format (padrão: hoje)
    """
    try:
        # Parâmetros da requisição
        linha = request.args.get('linha', 'LCT08')

        # Datas padrão (últimos 7 dias)
        data_fim = request.args.get('data_fim')
        data_inicio = request.args.get('data_inicio')

        if not data_fim:
            data_fim = datetime.now()
        else:
            data_fim = datetime.fromisoformat(data_fim)

        if not data_inicio:
            data_inicio = data_fim - timedelta(days=7)
        else:
            data_inicio = datetime.fromisoformat(data_inicio)

        # Buscar dados no MongoDB
        collection = get_mongo_connection('DecapadoPerformance')

        if collection is None:
            return jsonify({
                'status': 'error',
                'message': 'Banco de dados offline'
            }), 503

        # Query MongoDB
        query = {
            'linha': linha,
            'timestamp': {
                '$gte': data_inicio,
                '$lte': data_fim
            }
        }

        # Buscar documentos
        documentos = list(collection.find(query).sort('timestamp', -1).limit(100))

        # Calcular médias de OEE
        if documentos:
            oee_valores = [doc.get('OEE', 0) for doc in documentos if 'OEE' in doc]
            disp_valores = [doc.get('Disponibilidade', 0) for doc in documentos if 'Disponibilidade' in doc]
            perf_valores = [doc.get('Performance', 0) for doc in documentos if 'Performance' in doc]
            qual_valores = [doc.get('Qualidade', 0) for doc in documentos if 'Qualidade' in doc]

            oee_medio = sum(oee_valores) / len(oee_valores) if oee_valores else 0
            disp_media = sum(disp_valores) / len(disp_valores) if disp_valores else 0
            perf_media = sum(perf_valores) / len(perf_valores) if perf_valores else 0
            qual_media = sum(qual_valores) / len(qual_valores) if qual_valores else 0
        else:
            oee_medio = disp_media = perf_media = qual_media = 0

        # Preparar série temporal para gráfico
        serie_temporal = []
        for doc in documentos:
            serie_temporal.append({
                'timestamp': doc.get('timestamp').isoformat() if 'timestamp' in doc else None,
                'oee': doc.get('OEE', 0),
                'disponibilidade': doc.get('Disponibilidade', 0),
                'performance': doc.get('Performance', 0),
                'qualidade': doc.get('Qualidade', 0)
            })

        return jsonify({
            'status': 'success',
            'data': {
                'linha': linha,
                'periodo': {
                    'inicio': data_inicio.isoformat(),
                    'fim': data_fim.isoformat()
                },
                'resumo': {
                    'oee': round(oee_medio, 2),
                    'disponibilidade': round(disp_media, 2),
                    'performance': round(perf_media, 2),
                    'qualidade': round(qual_media, 2)
                },
                'serie_temporal': serie_temporal,
                'total_registros': len(documentos)
            }
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
