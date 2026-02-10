"""
Script para gerar dados fictícios de pendências e histórico para o Dashboard de Workflow.

Gera dois arquivos CSV:
- workflow_pendencias.csv: 50 pendências principais
- workflow_historico.csv: 3-7 subpendências por pendência (histórico)

Uso:
    python scripts/generate_workflow_csv.py
"""

import csv
import os
from datetime import datetime, timedelta
import random

# Configurações
NUM_PENDENCIAS = 50
MIN_HISTORICO = 3
MAX_HISTORICO = 7

RESPONSAVEIS = [
    "João Silva",
    "Maria Santos",
    "Pedro Costa",
    "Ana Oliveira",
    "Carlos Souza"
]

STATUS = ["Pendente", "Em Andamento", "Bloqueado", "Concluído"]

# Descrições realistas de pendências
DESCRICOES_PENDENCIAS = [
    "Calibração do sensor de temperatura MM03",
    "Revisão do sistema hidráulico da prensa P01",
    "Substituição de correia transportadora Linha 2",
    "Manutenção preventiva motor elétrico SE03",
    "Análise de falha recorrente no equipamento TRANS01",
    "Atualização de firmware do CLP principal",
    "Inspeção de segurança em pontes rolantes",
    "Troca de óleo lubrificante redutor MM05",
    "Limpeza e ajuste de sensores de proximidade",
    "Verificação de folgas em acoplamentos",
    "Reparo de vazamento hidráulico",
    "Substituição de rolamentos desgastados",
    "Ajuste de tensão de correntes de transmissão",
    "Verificação elétrica do painel de controle",
    "Manutenção do sistema de refrigeração",
    "Inspeção de cabos de alimentação",
    "Troca de filtros de ar comprimido",
    "Calibração de manômetros e pressostatos",
    "Reparo de cilindro pneumático",
    "Verificação de alinhamento de eixos",
    "Substituição de válvulas direcionais",
    "Limpeza de trocadores de calor",
    "Ajuste de fins de curso",
    "Inspeção de estruturas metálicas",
    "Verificação de sistemas de segurança",
    "Troca de lâmpadas de sinalização",
    "Manutenção de inversores de frequência",
    "Reparo de esteira transportadora",
    "Ajuste de tensão de correias em V",
    "Inspeção de mangueiras hidráulicas",
    "Troca de vedações e retentores",
    "Verificação de nível de óleo em redutores",
    "Calibração de instrumentos de medição",
    "Manutenção de bombas centrífugas",
    "Inspeção de conexões elétricas",
    "Ajuste de parâmetros do CLP",
    "Troca de fusíveis e disjuntores",
    "Verificação de aterramento elétrico",
    "Limpeza de painéis elétricos",
    "Inspeção de dispositivos de proteção",
    "Manutenção de sistema de exaustão",
    "Reparo de vazamento de ar comprimido",
    "Ajuste de pressão em sistemas pneumáticos",
    "Verificação de encoders e sensores",
    "Troca de baterias de backup",
    "Inspeção de quadros de distribuição",
    "Manutenção de compressores de ar",
    "Verificação de sistemas de ventilação",
    "Ajuste de proteções térmicas",
    "Inspeção final de equipamentos críticos"
]

# Ações de histórico
ACOES_HISTORICO = [
    "Pendência criada",
    "Atribuída para técnico",
    "Iniciada execução",
    "Aguardando peça de reposição",
    "Peça recebida, retomando trabalho",
    "Primeira inspeção concluída",
    "Identificado problema adicional",
    "Solicitado suporte especializado",
    "Teste realizado com sucesso",
    "Ajustes finais em andamento",
    "Aguardando aprovação do supervisor",
    "Documentação atualizada",
    "Treinamento da equipe realizado",
    "Equipamento liberado para operação",
    "Concluída com sucesso"
]


def gerar_data_aleatoria(inicio, fim):
    """Gera uma data aleatória entre inicio e fim."""
    delta = fim - inicio
    dias_aleatorios = random.randint(0, delta.days)
    return inicio + timedelta(days=dias_aleatorios)


def gerar_pendencias():
    """Gera 50 pendências principais."""
    pendencias = []
    data_fim = datetime.now()
    data_inicio = data_fim - timedelta(days=180)  # Últimos 6 meses

    for i in range(1, NUM_PENDENCIAS + 1):
        pendencia_id = f"PEND-{i:03d}"
        descricao = random.choice(DESCRICOES_PENDENCIAS)
        responsavel = random.choice(RESPONSAVEIS)
        status = random.choice(STATUS)

        # Data de criação aleatória nos últimos 6 meses
        data_criacao = gerar_data_aleatoria(data_inicio, data_fim)

        # Última atualização entre criação e hoje
        ultima_atualizacao = gerar_data_aleatoria(data_criacao, data_fim)

        pendencias.append({
            "id": pendencia_id,
            "descricao": descricao,
            "responsavel": responsavel,
            "status": status,
            "data_criacao": data_criacao.strftime("%Y-%m-%d %H:%M:%S"),
            "ultima_atualizacao": ultima_atualizacao.strftime("%Y-%m-%d %H:%M:%S")
        })

    return pendencias


def gerar_historico(pendencias):
    """Gera 3-7 entradas de histórico para cada pendência."""
    historico = []

    for pendencia in pendencias:
        num_entradas = random.randint(MIN_HISTORICO, MAX_HISTORICO)
        data_criacao = datetime.strptime(pendencia["data_criacao"], "%Y-%m-%d %H:%M:%S")
        data_final = datetime.strptime(pendencia["ultima_atualizacao"], "%Y-%m-%d %H:%M:%S")

        # Gerar datas crescentes entre criação e última atualização
        datas = sorted([
            gerar_data_aleatoria(data_criacao, data_final)
            for _ in range(num_entradas)
        ])

        # Primeira entrada sempre "Pendência criada"
        historico.append({
            "pendencia_id": pendencia["id"],
            "descricao": "Pendência criada",
            "data": datas[0].strftime("%Y-%m-%d %H:%M:%S"),
            "responsavel": pendencia["responsavel"]
        })

        # Entradas intermediárias
        for i in range(1, num_entradas - 1):
            acao = random.choice(ACOES_HISTORICO[1:-1])  # Excluir primeira e última
            responsavel = random.choice(RESPONSAVEIS)
            historico.append({
                "pendencia_id": pendencia["id"],
                "descricao": acao,
                "data": datas[i].strftime("%Y-%m-%d %H:%M:%S"),
                "responsavel": responsavel
            })

        # Última entrada baseada no status
        if pendencia["status"] == "Concluído":
            ultima_acao = "Concluída com sucesso"
        else:
            ultima_acao = random.choice(ACOES_HISTORICO[1:-1])

        historico.append({
            "pendencia_id": pendencia["id"],
            "descricao": ultima_acao,
            "data": datas[-1].strftime("%Y-%m-%d %H:%M:%S"),
            "responsavel": random.choice(RESPONSAVEIS)
        })

    return historico


def salvar_csv(dados, caminho, fieldnames):
    """Salva dados em arquivo CSV."""
    os.makedirs(os.path.dirname(caminho), exist_ok=True)

    with open(caminho, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dados)

    print(f"[OK] Arquivo criado: {caminho} ({len(dados)} registros)")


def main():
    """Função principal."""
    print("Gerando dados de workflow...")
    print("-" * 50)

    # Definir caminhos de saída
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "src", "data")

    caminho_pendencias = os.path.join(data_dir, "workflow_pendencias.csv")
    caminho_historico = os.path.join(data_dir, "workflow_historico.csv")

    # Gerar dados
    pendencias = gerar_pendencias()
    historico = gerar_historico(pendencias)

    # Salvar CSVs
    salvar_csv(
        pendencias,
        caminho_pendencias,
        ["id", "descricao", "responsavel", "status", "data_criacao", "ultima_atualizacao"]
    )

    salvar_csv(
        historico,
        caminho_historico,
        ["pendencia_id", "descricao", "data", "responsavel"]
    )

    print("-" * 50)
    print("[OK] Geracao concluida com sucesso!")
    print(f"\nResumo:")
    print(f"  - Pendencias: {len(pendencias)}")
    print(f"  - Entradas de historico: {len(historico)}")
    print(f"  - Media de historico por pendencia: {len(historico)/len(pendencias):.1f}")


if __name__ == "__main__":
    main()
