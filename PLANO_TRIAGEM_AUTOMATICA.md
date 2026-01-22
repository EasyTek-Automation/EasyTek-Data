# 🔧 PLANO DE IMPLEMENTAÇÃO — Sistema de Triagem Automática de Chamados de Manutenção

## 📋 Sumário Executivo

Este documento detalha o plano de implementação de um sistema de triagem automática de chamados de manutenção para o projeto **AMG_Data**. O sistema utilizará técnicas de processamento de linguagem natural (NLP) e machine learning para:

- **Classificar automaticamente** chamados de manutenção
- **Identificar subequipamentos** afetados
- **Sugerir categorias** de falha
- **Agrupar chamados similares** para análise de recorrência
- **Rotear chamados** para as equipes adequadas

O sistema será **100% local (offline)** e integrado à infraestrutura existente do AMG_Data (MongoDB, Dash, Node-RED).

---

## 🎯 Contexto e Integração com AMG_Data

### Infraestrutura Existente

O projeto AMG_Data já possui:

✅ **MongoDB** com coleção `DecapadoFalhas` para alarmes
✅ **Sistema de autenticação** com perfis (incluindo `manutencao`)
✅ **Módulo de manutenção** com páginas de alarmes e procedimentos
✅ **Node-RED** para coleta de dados em tempo real
✅ **Event Gateway** para comunicação MQTT
✅ **Padrão de callbacks** bem definido para Dash
✅ **Sistema de controle de acesso** por perfil e nível

### Pontos de Integração

O sistema de triagem será integrado em:

1. **Backend**: Nova coleção MongoDB `maintenance_tickets`
2. **Frontend**: Nova rota `/maintenance/work-orders`
3. **Processamento**: Scripts Python para análise e classificação
4. **Automação**: Triggers Node-RED para triagem em tempo real

---

## ✅ Viabilidade no Projeto AMG_Data

### 🟢 Pontos Favoráveis (PROS)

#### 1. **Infraestrutura Pronta**
- MongoDB já configurado e em uso
- Sistema de autenticação funcional
- Padrão de desenvolvimento bem estabelecido
- Callbacks e componentes reutilizáveis (`msgtable_callback.py`, `sidebar.py`)

#### 2. **Dados Disponíveis**
- Coleção `DecapadoFalhas` com histórico de alarmes
- Estrutura de dados já definida (`qualMaquinaDesc`, `categoriaFalhaDesc`, `descricaoFalhaDesc`)
- Sistema de coleta contínua via Node-RED

#### 3. **Perfis de Usuário Adequados**
- Perfil `manutencao` já existe no sistema de controle de acesso
- Modelo bi-dimensional (level + perfil) permite controle granular
- Suporte para múltiplas equipes de manutenção

#### 4. **Padrão de Desenvolvimento Estabelecido**
- Estrutura modular de páginas em `pages/maintenance/`
- Sistema de callbacks em `callbacks_registers/`
- Componentes reutilizáveis em `components/`
- Rotas já definidas em `access_control.py` (apenas não implementadas)

#### 5. **Processamento Local**
- Todo o stack roda localmente (Flask, MongoDB, Node-RED)
- Não depende de APIs externas
- Ideal para ambiente industrial

#### 6. **Documentação Integrada**
- Sistema de procedimentos Markdown já funcional
- Possibilidade de vincular chamados a procedimentos existentes
- Estrutura `docs.yml` para organização hierárquica

### 🔴 Desafios e Limitações (CONTRAS)

#### 1. **Qualidade dos Dados de Entrada**
- Textos livres podem ser genéricos ou incompletos
- Possível inconsistência em descrições de alarmes
- Necessidade de limpeza e normalização extensiva

#### 2. **Complexidade de Classificação**
- Vocabulário técnico específico da planta
- Gírias e abreviações locais
- Termos compartilhados entre subequipamentos diferentes

#### 3. **Requisitos de Processamento**
- Vetorização TF-IDF pode ser custosa em datasets grandes
- Clustering requer ajuste fino de parâmetros
- Necessidade de otimização para execução em tempo real

#### 4. **Manutenção do Sistema**
- Dicionários técnicos precisam ser atualizados constantemente
- Glossários de subequipamentos requerem validação com operação
- Sistema de feedback para melhorias contínuas

#### 5. **Curva de Aprendizado**
- Equipe precisa entender conceitos de NLP
- Ajuste de parâmetros requer conhecimento técnico
- Interface humana precisa ser intuitiva para adoção

#### 6. **Dados Históricos Limitados**
- Possível falta de dados rotulados para treinamento supervisionado
- Histórico pode ter inconsistências ou categorização incorreta
- Necessidade de validação manual inicial

### ⚖️ Conclusão de Viabilidade

**VIÁVEL E RECOMENDADO**, mas com implementação **GRADUAL E ITERATIVA**.

**Recomendações**:
- Começar com um **piloto** em um subequipamento específico
- Validar com a equipe de manutenção antes de expandir
- Implementar **human-in-the-loop** para validação inicial
- Focar primeiro em **identificação de subequipamento** (maior impacto)
- Deixar clustering e ML supervisionado para **Fase 2**

---

## 📐 Arquitetura do Sistema

### Visão Geral

```
┌───────────────────────────────────────────────────────────────────┐
│                   SISTEMA DE TRIAGEM AUTOMÁTICA                  │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  CAMADA DE ENTRADA (Node-RED)                              │ │
│  │  ┌─────────────┐     ┌─────────────┐                       │ │
│  │  │ Alarmes     │────▶│ MongoDB     │                       │ │
│  │  │ (MQTT/OPC)  │     │DecapadoFalhas│                      │ │
│  │  └─────────────┘     └──────┬──────┘                       │ │
│  └────────────────────────────┼────────────────────────────────┘ │
│                                │                                  │
│  ┌────────────────────────────▼────────────────────────────────┐ │
│  │  CAMADA DE PROCESSAMENTO (Python)                          │ │
│  │  ┌──────────────────┐   ┌───────────────────┐             │ │
│  │  │ Normalização     │──▶│ Identificação     │             │ │
│  │  │ de Texto         │   │ Subequipamento    │             │ │
│  │  └──────────────────┘   └─────────┬─────────┘             │ │
│  │                                    │                        │ │
│  │  ┌──────────────────┐   ┌─────────▼─────────┐             │ │
│  │  │ Vetorização      │──▶│ Sugestão          │             │ │
│  │  │ TF-IDF           │   │ Categoria         │             │ │
│  │  └──────────────────┘   └─────────┬─────────┘             │ │
│  │                                    │                        │ │
│  │  ┌──────────────────┐             │                        │ │
│  │  │ Clustering       │◀────────────┘                        │ │
│  │  │ HDBSCAN          │                                      │ │
│  │  └──────────────────┘                                      │ │
│  └────────────────────────────┬────────────────────────────────┘ │
│                                │                                  │
│  ┌────────────────────────────▼────────────────────────────────┐ │
│  │  CAMADA DE DADOS (MongoDB)                                 │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ maintenance_tickets (Nova Coleção)                   │  │ │
│  │  │  - ticket_number, machine, failure_category          │  │ │
│  │  │  - description, priority, status                     │  │ │
│  │  │  - suggested_subequipment, confidence_score          │  │ │
│  │  │  - assigned_to, created_date, updated_date           │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────┬────────────────────────────────┘ │
│                                │                                  │
│  ┌────────────────────────────▼────────────────────────────────┐ │
│  │  CAMADA DE APRESENTAÇÃO (Dash)                             │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ /maintenance/work-orders                             │  │ │
│  │  │  - Tabela de chamados                                │  │ │
│  │  │  - Filtros (status, prioridade, subequipamento)      │  │ │
│  │  │  - Aprovação/rejeição de sugestões                   │  │ │
│  │  │  - Atribuição de técnicos                            │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Coleção MongoDB Proposta

```javascript
// Coleção: maintenance_tickets
{
  "_id": ObjectId("..."),

  // Informações Básicas
  "ticket_number": "MNT-2026-0001",
  "source": "alarm",  // "alarm", "manual", "scheduled"
  "source_alarm_id": ObjectId("..."),  // Referência para DecapadoFalhas

  // Dados do Problema
  "machine": "Decapado",
  "machine_code": "DCP01",
  "description_operator": "Máquina parou, erro no painel",
  "description_technical": "Falha em sensor de temperatura K3",

  // Classificação Automática
  "suggested_subequipment": "Aplanadora 17/63",
  "subequipment_confidence": 0.87,
  "suggested_category": "Elétrica - Sensores",
  "category_confidence": 0.92,
  "priority": 3,  // 1=baixa, 2=média, 3=alta, 4=crítica
  "urgency_score": 78.5,

  // Roteamento
  "suggested_team": "manutencao_eletrica",
  "assigned_to": null,
  "assigned_date": null,

  // Status
  "status": "novo",  // "novo", "triado", "atribuído", "em_progresso", "aguardando_pecas", "concluído", "cancelado"
  "approval_status": "pending",  // "pending", "approved", "corrected"

  // Histórico
  "created_date": ISODate("2026-01-18T10:30:00Z"),
  "updated_date": ISODate("2026-01-18T10:30:00Z"),
  "completed_date": null,

  // Resolução
  "resolution": null,
  "parts_used": [],
  "time_spent_minutes": null,
  "root_cause": null,

  // Clustering e Análise
  "cluster_id": 42,
  "similar_tickets": [ObjectId("..."), ObjectId("...")],
  "recurrence_count": 3,  // Quantas vezes similar ocorreu

  // Documentação
  "procedure_reference": "/docs/procedures/eletrica/sensores.md",
  "comments": [
    {
      "user": "joao.silva",
      "date": ISODate("2026-01-18T11:00:00Z"),
      "text": "Verificado sensor K3, está com mau contato"
    }
  ],

  // Feedback para Machine Learning
  "user_corrections": {
    "subequipment_corrected": false,
    "category_corrected": false,
    "original_suggestions": {}
  }
}
```

### Estrutura de Arquivos Novos

```
E:\Projetos Python\AMG_Data\
│
├── webapp/src/
│   ├── pages/maintenance/
│   │   ├── alarms.py                    # Existente
│   │   ├── procedures.py                # Existente
│   │   ├── work_orders.py               # 🆕 Nova página de triagem
│   │   ├── work_order_detail.py         # 🆕 Detalhes de chamado
│   │   └── maintenance_analytics.py     # 🆕 Analytics de manutenção
│   │
│   ├── callbacks_registers/
│   │   ├── work_orders_callbacks.py     # 🆕 Callbacks da tabela
│   │   ├── triagem_approval_callbacks.py # 🆕 Aprovação de sugestões
│   │   └── maintenance_stats_callbacks.py # 🆕 Estatísticas
│   │
│   ├── components/
│   │   ├── sidebars/
│   │   │   └── work_orders_sidebar.py   # 🆕 Sidebar com filtros
│   │   └── work_order_card.py           # 🆕 Card de chamado
│   │
│   └── utils/
│       └── triagem/                      # 🆕 Módulo de triagem
│           ├── __init__.py
│           ├── text_normalizer.py       # Normalização de texto
│           ├── subequipment_classifier.py # Identificação de subequip.
│           ├── category_suggester.py    # Sugestão de categoria
│           ├── clustering.py            # Clustering HDBSCAN
│           ├── vectorization.py         # TF-IDF
│           └── config/
│               ├── subequipamentos.yml  # Glossário de subequipamentos
│               ├── categorias.yml       # Categorias de falha
│               └── synonyms.yml         # Sinônimos técnicos
│
├── scripts/                              # 🆕 Scripts auxiliares
│   ├── batch_processing/
│   │   ├── process_historical_alarms.py  # Processar histórico
│   │   └── retrain_clustering.py         # Retreinar clusters
│   └── analysis/
│       ├── analyze_recurrence.py         # Análise de recorrência
│       └── export_reports.py             # Exportar relatórios
│
└── docs/
    └── triagem/                          # 🆕 Documentação do sistema
        ├── README.md                     # Visão geral
        ├── architecture.md               # Arquitetura detalhada
        ├── glossary.md                   # Glossário técnico
        └── user_guide.md                 # Guia do usuário
```

---

## 🗺️ Passo a Passo de Implementação

### 🟢 FASE 0 — Preparação e Análise de Dados (3 dias)

#### Objetivo
Entender a qualidade e estrutura real dos dados de alarmes existentes na coleção `DecapadoFalhas`.

#### Atividades

1. **Extração de Amostra de Dados**
   - Conectar ao MongoDB e extrair últimos 6 meses de alarmes
   - Script: `scripts/analysis/extract_sample_data.py`
   - Exportar para CSV para análise manual

2. **Análise Estatística**
   - Contagem de registros por máquina
   - Distribuição de categorias existentes
   - Análise de completude (campos vazios)
   - Tamanho médio de descrições
   - Identificação de termos mais frequentes

3. **Mapeamento de Estrutura**
   - Documentar campos disponíveis em `DecapadoFalhas`
   - Identificar chave única (ou criar se necessário)
   - Mapear relação com outras coleções (se houver)

4. **Identificação de Padrões**
   - Listar todos os valores únicos de `qualMaquinaDesc`
   - Listar todos os valores únicos de `categoriaFalhaDesc`
   - Identificar inconsistências (ex: "Cisalha" vs "cisalha" vs "CISALHA")
   - Listar termos técnicos recorrentes

5. **Validação com Usuário**
   - Apresentar amostra para equipe de manutenção
   - Validar se categorias existentes fazem sentido
   - Identificar subequipamentos reais da planta
   - Coletar vocabulário técnico específico

#### Entregáveis
- ✅ CSV com amostra de dados
- ✅ Relatório estatístico (Jupyter Notebook)
- ✅ Documento de mapeamento de campos
- ✅ Lista oficial de subequipamentos
- ✅ Lista oficial de categorias de falha

#### Scripts a Criar
```python
# scripts/analysis/extract_sample_data.py
from src.database.connection import get_mongo_connection
import pandas as pd

collection = get_mongo_connection("DecapadoFalhas")
data = list(collection.find().limit(5000).sort("date_time", -1))
df = pd.DataFrame(data)
df.to_csv("data_sample.csv", index=False)
```

---

### 🟢 FASE 1 — Normalização e Padronização de Texto (4 dias)

#### Objetivo
Criar pipeline de pré-processamento de texto robusto e específico para vocabulário técnico da planta.

#### Atividades

1. **Implementar Funções Básicas de Limpeza**
   - Lowercase
   - Remoção de acentos (considerar manter para português técnico)
   - Remoção de pontuação (proteger códigos técnicos)
   - Padronização de espaços múltiplos
   - Remoção de stopwords customizadas

2. **Criar Sistema de Proteção de Tokens Técnicos**
   - Regex para proteger códigos (ex: K1, F3, MTR01, 24V)
   - Regex para proteger números de peças
   - Lista de termos técnicos que não devem ser alterados

3. **Dicionário de Sinônimos e Abreviações**
   - Criar `synonyms.yml` com mapeamento
   - Exemplos:
     ```yaml
     # Equipamentos
     "aplan": "aplanadora"
     "cizalha": "cisalha"
     "desenrol": "desenrolador"

     # Componentes
     "temp": "temperatura"
     "sens": "sensor"
     "mot": "motor"

     # Ações
     "parou": "parada"
     "travou": "travamento"
     ```

4. **Implementar Normalização Customizada**
   - Função `normalize_text(text, protect_codes=True)`
   - Suporte a múltiplos idiomas (português + inglês técnico)
   - Preservar unidades de medida (°C, kW, bar, etc.)

5. **Pipeline de Validação**
   - Testes unitários com casos reais
   - Validação com amostra de 100 textos
   - Ajustes iterativos baseados em feedback

6. **Criar Relatório Antes/Depois**
   - Comparar textos originais com normalizados
   - Verificar se não está removendo informação relevante
   - Ajustar regras conforme necessário

#### Entregáveis
- ✅ `webapp/src/utils/triagem/text_normalizer.py`
- ✅ `webapp/src/utils/triagem/config/synonyms.yml`
- ✅ Testes unitários (`tests/test_text_normalizer.py`)
- ✅ Notebook de validação (`notebooks/text_normalization_validation.ipynb`)

#### Exemplo de Código
```python
# webapp/src/utils/triagem/text_normalizer.py

import re
import yaml
from unidecode import unidecode

class TextNormalizer:
    def __init__(self, synonyms_file='config/synonyms.yml'):
        with open(synonyms_file, 'r', encoding='utf-8') as f:
            self.synonyms = yaml.safe_load(f)

        # Regex para proteger códigos técnicos
        self.code_patterns = [
            r'\b[A-Z]\d+\b',           # K1, F3, M2
            r'\b[A-Z]{2,}\d+\b',       # MTR01, SEN24
            r'\b\d+V\b',               # 24V, 220V
            r'\b\d+°C\b',              # 80°C
        ]

    def normalize(self, text, preserve_codes=True):
        """Normaliza texto preservando códigos técnicos"""

        if not text or not isinstance(text, str):
            return ""

        # 1. Proteger códigos técnicos temporariamente
        protected = {}
        if preserve_codes:
            for i, pattern in enumerate(self.code_patterns):
                for match in re.finditer(pattern, text):
                    placeholder = f"__PROTECTED_{i}_{len(protected)}__"
                    protected[placeholder] = match.group()
                    text = text.replace(match.group(), placeholder)

        # 2. Lowercase
        text = text.lower()

        # 3. Remover acentos (opcional)
        # text = unidecode(text)

        # 4. Aplicar sinônimos
        for synonym, canonical in self.synonyms.items():
            text = re.sub(r'\b' + synonym + r'\b', canonical, text)

        # 5. Remover pontuação (exceto em números)
        text = re.sub(r'[^\w\s\.]', ' ', text)

        # 6. Normalizar espaços
        text = re.sub(r'\s+', ' ', text).strip()

        # 7. Restaurar códigos protegidos
        for placeholder, original in protected.items():
            text = text.replace(placeholder, original)

        return text

# Uso
normalizer = TextNormalizer()
normalized = normalizer.normalize("Temp. do motor MTR01 travou em 85°C")
# Output: "temperatura do motor MTR01 travou em 85°C"
```

---

### 🟡 FASE 2 — Identificação de Subequipamento (6,5 dias)

#### Objetivo
Implementar sistema híbrido para identificar automaticamente qual subequipamento da linha está relacionado ao chamado.

#### Estratégia
Sistema de **pontuação por palavras-chave ponderadas** com fallback para **similaridade TF-IDF**.

#### Atividades

1. **Definir Lista Oficial de Subequipamentos**
   - Trabalhar com equipe de operação/manutenção
   - Criar hierarquia: Máquina > Subequipamento > Componente
   - Exemplo:
     ```yaml
     # subequipamentos.yml
     subequipamentos:
       - id: "aplanadora_17_63"
         nome: "Aplanadora 17/63"
         machine: "Decapado"
         keywords:
           - palavra: "aplanadora"
             peso: 10
           - palavra: "aplan"
             peso: 8
           - palavra: "17/63"
             peso: 10
           - palavra: "cilindro"
             peso: 5
           - palavra: "rolo"
             peso: 5

       - id: "desenrolador"
         nome: "Desenrolador"
         machine: "Decapado"
         keywords:
           - palavra: "desenrolador"
             peso: 10
           - palavra: "desenrol"
             peso: 8
           - palavra: "bobina"
             peso: 7
           - palavra: "mandril"
             peso: 8
     ```

2. **Criar Glossário Técnico por Subequipamento**
   - Para cada subequipamento, listar:
     - Termos principais (peso 10)
     - Termos secundários (peso 5-8)
     - Componentes específicos (peso 3-5)
     - Códigos de peças relacionadas (peso 7)

3. **Implementar Algoritmo de Score**
   - Calcular score para cada subequipamento
   - Score = Σ(peso × ocorrências)
   - Normalizar por tamanho do texto
   - Aplicar threshold mínimo de confiança

4. **Regras de Desempate**
   - Se múltiplos subequipamentos com score similar:
     - Priorizar termos com maior peso
     - Considerar contexto (categoria de falha)
     - Verificar histórico de chamados similares
   - Se nenhum subequipamento atingir threshold:
     - Marcar como "Não Identificado"
     - Score de confiança = 0

5. **Implementar Fallback por Similaridade**
   - Buscar chamados históricos já rotulados
   - Calcular similaridade TF-IDF
   - Usar subequipamento do chamado mais similar
   - Ajustar score de confiança proporcionalmente

6. **Sistema de Multi-Equipamento**
   - Permitir identificar múltiplos subequipamentos
   - Exemplo: "Problema entre aplanadora e cisalha"
   - Retornar lista ordenada por score

7. **Calibração e Validação**
   - Testar com amostra de 200 chamados reais
   - Comparar com rotulação manual
   - Calcular acurácia, precisão, recall
   - Ajustar pesos iterativamente

#### Entregáveis
- ✅ `webapp/src/utils/triagem/config/subequipamentos.yml`
- ✅ `webapp/src/utils/triagem/subequipment_classifier.py`
- ✅ Função `classify_subequipment(text) -> (subequip, confidence)`
- ✅ Relatório de acurácia (`reports/subequipment_accuracy.md`)

#### Exemplo de Código
```python
# webapp/src/utils/triagem/subequipment_classifier.py

import yaml
import re
from typing import Tuple, List, Dict

class SubequipmentClassifier:
    def __init__(self, config_file='config/subequipamentos.yml'):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            self.subequipamentos = config['subequipamentos']

        self.confidence_threshold = 0.3  # Score mínimo para considerar

    def classify(self, text: str, top_n: int = 3) -> List[Tuple[str, float]]:
        """
        Classifica subequipamento(s) no texto.

        Returns:
            Lista de tuplas (subequipamento_id, confidence_score)
        """
        text_normalized = text.lower()
        scores = {}

        for subequip in self.subequipamentos:
            score = 0
            total_weight = 0

            for keyword_config in subequip['keywords']:
                keyword = keyword_config['palavra']
                peso = keyword_config['peso']

                # Contar ocorrências da palavra no texto
                pattern = r'\b' + re.escape(keyword) + r'\b'
                occurrences = len(re.findall(pattern, text_normalized))

                if occurrences > 0:
                    score += peso * occurrences
                    total_weight += peso

            # Normalizar score pelo tamanho do texto (evitar viés)
            text_length = len(text_normalized.split())
            normalized_score = score / max(text_length, 1)

            # Ajustar por total de keywords encontrados (mais keywords = mais confiança)
            if total_weight > 0:
                confidence = min(normalized_score * (total_weight / 10), 1.0)
            else:
                confidence = 0.0

            scores[subequip['id']] = confidence

        # Ordenar por score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Filtrar por threshold e retornar top_n
        filtered = [(id, score) for id, score in sorted_scores
                    if score >= self.confidence_threshold]

        return filtered[:top_n]

    def get_subequipment_name(self, subequip_id: str) -> str:
        """Retorna nome legível do subequipamento"""
        for subequip in self.subequipamentos:
            if subequip['id'] == subequip_id:
                return subequip['nome']
        return "Desconhecido"

# Uso
classifier = SubequipmentClassifier()
results = classifier.classify("Problema na aplanadora, cilindro travado")
# Output: [('aplanadora_17_63', 0.85), ...]

for subequip_id, confidence in results:
    nome = classifier.get_subequipment_name(subequip_id)
    print(f"{nome}: {confidence:.2%}")
```

---

### 🟡 FASE 3 — Vetorização TF-IDF e Similaridade (4,25 dias)

#### Objetivo
Criar representação vetorial de textos para permitir comparação matemática entre chamados.

#### Atividades

1. **Implementar Vetorização Word N-grams**
   - TF-IDF com unigramas e bigramas
   - Vocabulário mínimo: termos que aparecem em >= 3 documentos
   - Vocabulário máximo: ignorar termos em > 80% dos documentos
   - Normalização L2

2. **Implementar Vetorização Char N-grams**
   - TF-IDF com 3-gramas e 4-gramas de caracteres
   - Tolerância a erros de digitação
   - Captura variações morfológicas

3. **Combinação Ponderada**
   - Combinar vetores word e char
   - Peso word: 0.7
   - Peso char: 0.3
   - Experimentar diferentes proporções

4. **Função de Similaridade**
   - Similaridade cosseno entre vetores
   - Threshold de similaridade: 0.6
   - Retornar top-k documentos similares

5. **Otimização de Performance**
   - Vetorizar corpus completo uma vez
   - Salvar vetores em cache (pickle ou HDF5)
   - Índice ANN (Approximate Nearest Neighbors) para busca rápida
   - Considerar usar `scikit-learn` ou `scipy.sparse`

6. **Sistema de Cache**
   - Armazenar vetores pré-computados
   - Invalidar cache quando corpus atualizar
   - Incremental: adicionar novos vetores sem reprocessar tudo

7. **Validação e Tuning**
   - Testar diferentes parâmetros (max_features, ngram_range)
   - Avaliar qualidade de agrupamento
   - Comparar com similaridade humana (amostra)

#### Entregáveis
- ✅ `webapp/src/utils/triagem/vectorization.py`
- ✅ `webapp/src/utils/triagem/similarity.py`
- ✅ Scripts de cache (`scripts/batch_processing/build_tfidf_cache.py`)
- ✅ Notebook de tuning (`notebooks/tfidf_parameter_tuning.ipynb`)

#### Exemplo de Código
```python
# webapp/src/utils/triagem/vectorization.py

from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import pickle
from typing import List, Tuple

class TextVectorizer:
    def __init__(self):
        # Vetorizador word-based
        self.word_vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=3,
            max_df=0.8,
            max_features=5000,
            norm='l2',
            sublinear_tf=True
        )

        # Vetorizador char-based
        self.char_vectorizer = TfidfVectorizer(
            analyzer='char',
            ngram_range=(3, 4),
            min_df=3,
            max_df=0.8,
            max_features=3000,
            norm='l2'
        )

        self.word_weight = 0.7
        self.char_weight = 0.3
        self.is_fitted = False

    def fit(self, texts: List[str]):
        """Treina vetorizadores com corpus"""
        self.word_vectorizer.fit(texts)
        self.char_vectorizer.fit(texts)
        self.is_fitted = True

    def transform(self, texts: List[str]) -> np.ndarray:
        """Transforma textos em vetores combinados"""
        if not self.is_fitted:
            raise ValueError("Vectorizer not fitted. Call fit() first.")

        # Vetorizar
        word_vectors = self.word_vectorizer.transform(texts)
        char_vectors = self.char_vectorizer.transform(texts)

        # Combinar com pesos
        combined = (self.word_weight * word_vectors.toarray() +
                    self.char_weight * char_vectors.toarray())

        # Renormalizar
        norms = np.linalg.norm(combined, axis=1, keepdims=True)
        combined = combined / (norms + 1e-10)

        return combined

    def fit_transform(self, texts: List[str]) -> np.ndarray:
        """Treina e transforma em uma chamada"""
        self.fit(texts)
        return self.transform(texts)

    def save(self, filepath: str):
        """Salva vetorizadores treinados"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'word_vectorizer': self.word_vectorizer,
                'char_vectorizer': self.char_vectorizer,
                'word_weight': self.word_weight,
                'char_weight': self.char_weight
            }, f)

    def load(self, filepath: str):
        """Carrega vetorizadores treinados"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.word_vectorizer = data['word_vectorizer']
            self.char_vectorizer = data['char_vectorizer']
            self.word_weight = data['word_weight']
            self.char_weight = data['char_weight']
            self.is_fitted = True


# webapp/src/utils/triagem/similarity.py

from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Tuple

class SimilaritySearch:
    def __init__(self, vectorizer: TextVectorizer):
        self.vectorizer = vectorizer
        self.corpus_vectors = None
        self.corpus_ids = None

    def index_corpus(self, texts: List[str], ids: List[str]):
        """Indexa corpus para busca rápida"""
        self.corpus_vectors = self.vectorizer.transform(texts)
        self.corpus_ids = np.array(ids)

    def find_similar(self, query_text: str, top_k: int = 5,
                     threshold: float = 0.6) -> List[Tuple[str, float]]:
        """
        Encontra documentos similares.

        Returns:
            Lista de tuplas (document_id, similarity_score)
        """
        # Vetorizar query
        query_vector = self.vectorizer.transform([query_text])

        # Calcular similaridade com corpus
        similarities = cosine_similarity(query_vector, self.corpus_vectors)[0]

        # Ordenar por similaridade
        sorted_indices = np.argsort(similarities)[::-1]

        # Filtrar por threshold e retornar top_k
        results = []
        for idx in sorted_indices[:top_k]:
            score = similarities[idx]
            if score >= threshold:
                results.append((self.corpus_ids[idx], float(score)))

        return results

# Uso
vectorizer = TextVectorizer()
vectorizer.fit(corpus_texts)
vectorizer.save('models/tfidf_vectorizer.pkl')

search = SimilaritySearch(vectorizer)
search.index_corpus(corpus_texts, corpus_ids)

similar = search.find_similar("Motor travado na cisalha", top_k=5)
# Output: [('ticket_123', 0.87), ('ticket_456', 0.75), ...]
```

---

### 🟡 FASE 4 — Clustering de Chamados (5,25 dias)

#### Objetivo
Identificar famílias de falhas recorrentes usando clustering não-supervisionado.

#### Estratégia
- **HDBSCAN** (Hierarchical Density-Based Spatial Clustering)
- Clustering global + clustering por subequipamento

#### Atividades

1. **Setup de HDBSCAN**
   - Instalar biblioteca: `pip install hdbscan`
   - Configurar parâmetros iniciais:
     - `min_cluster_size`: 5-10 (mínimo de chamados para formar cluster)
     - `min_samples`: 3-5 (densidade mínima)
     - `metric`: 'euclidean' ou 'cosine'

2. **Clustering Global**
   - Aplicar HDBSCAN em todo o corpus vetorizado
   - Identificar clusters principais
   - Analisar outliers (ruído)
   - Gerar relatórios por cluster

3. **Clustering por Subequipamento**
   - Filtrar chamados por subequipamento
   - Aplicar HDBSCAN separadamente
   - Melhor granularidade (menos ruído)
   - Identificar problemas recorrentes específicos

4. **Ajuste de Parâmetros**
   - Experimentar diferentes valores de `min_cluster_size`
   - Avaliar silhouette score
   - Avaliar pureza dos clusters (se tiver rótulos)
   - Validação visual (t-SNE ou UMAP)

5. **Análise de Clusters**
   - Extrair termos mais representativos (TF-IDF por cluster)
   - Identificar categoria majoritária
   - Contar recorrências
   - Gerar relatório explicável

6. **Integração com MongoDB**
   - Adicionar campo `cluster_id` em `maintenance_tickets`
   - Permitir busca por cluster
   - Dashboard de clusters no frontend

7. **Atualização Incremental**
   - Script para reclustering periódico
   - Atualizar clusters quando corpus crescer significativamente
   - Manter histórico de versões de clustering

#### Entregáveis
- ✅ `webapp/src/utils/triagem/clustering.py`
- ✅ Script de batch: `scripts/batch_processing/run_clustering.py`
- ✅ Relatórios de clusters: `reports/clusters/cluster_analysis.html`
- ✅ Notebook de validação: `notebooks/clustering_validation.ipynb`

#### Exemplo de Código
```python
# webapp/src/utils/triagem/clustering.py

import hdbscan
import numpy as np
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
from collections import Counter
from typing import List, Dict

class TicketClusterer:
    def __init__(self, min_cluster_size=5, min_samples=3):
        self.clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric='euclidean',
            cluster_selection_method='eom'
        )
        self.labels = None
        self.probabilities = None

    def fit(self, vectors: np.ndarray):
        """Aplica clustering nos vetores"""
        self.clusterer.fit(vectors)
        self.labels = self.clusterer.labels_
        self.probabilities = self.clusterer.probabilities_
        return self.labels

    def get_cluster_stats(self) -> Dict:
        """Retorna estatísticas dos clusters"""
        unique, counts = np.unique(self.labels, return_counts=True)

        stats = {
            'num_clusters': len(unique) - (1 if -1 in unique else 0),
            'num_noise': counts[unique == -1][0] if -1 in unique else 0,
            'cluster_sizes': dict(zip(unique.tolist(), counts.tolist()))
        }
        return stats

    def visualize(self, vectors: np.ndarray, save_path: str = None):
        """Visualiza clusters com t-SNE"""
        # Reduzir dimensionalidade para 2D
        tsne = TSNE(n_components=2, random_state=42)
        vectors_2d = tsne.fit_transform(vectors)

        # Plot
        plt.figure(figsize=(12, 8))
        scatter = plt.scatter(
            vectors_2d[:, 0],
            vectors_2d[:, 1],
            c=self.labels,
            cmap='tab20',
            s=50,
            alpha=0.6
        )
        plt.colorbar(scatter, label='Cluster ID')
        plt.title('Clusters de Chamados de Manutenção (t-SNE)')
        plt.xlabel('Dimensão 1')
        plt.ylabel('Dimensão 2')

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        else:
            plt.show()

    def get_cluster_keywords(self, texts: List[str], vectorizer,
                             top_n: int = 10) -> Dict[int, List[str]]:
        """Extrai palavras-chave mais representativas por cluster"""
        from sklearn.feature_extraction.text import TfidfVectorizer

        cluster_keywords = {}
        unique_clusters = set(self.labels)

        for cluster_id in unique_clusters:
            if cluster_id == -1:  # Ignorar ruído
                continue

            # Textos do cluster
            cluster_texts = [texts[i] for i, label in enumerate(self.labels)
                             if label == cluster_id]

            if len(cluster_texts) == 0:
                continue

            # TF-IDF específico do cluster
            tfidf = TfidfVectorizer(max_features=top_n, ngram_range=(1, 2))
            tfidf.fit(cluster_texts)

            # Extrair top termos
            keywords = tfidf.get_feature_names_out().tolist()
            cluster_keywords[cluster_id] = keywords

        return cluster_keywords

# Uso
clusterer = TicketClusterer(min_cluster_size=5, min_samples=3)
labels = clusterer.fit(corpus_vectors)

stats = clusterer.get_cluster_stats()
print(f"Clusters encontrados: {stats['num_clusters']}")
print(f"Outliers: {stats['num_noise']}")

clusterer.visualize(corpus_vectors, save_path='reports/clusters/visualization.png')

keywords = clusterer.get_cluster_keywords(corpus_texts, vectorizer)
for cluster_id, kw_list in keywords.items():
    print(f"Cluster {cluster_id}: {', '.join(kw_list)}")
```

---

### 🟠 FASE 5 — Sugestão Automática de Categoria (4,5 dias)

#### Objetivo
Gerar sugestão automática de categoria de falha com score de confiança.

#### Estratégias
1. Categoria majoritária por cluster
2. Reuso de histórico similar
3. Regras técnicas específicas

#### Atividades

1. **Definir Taxonomia de Categorias**
   - Trabalhar com equipe de manutenção
   - Criar hierarquia: Categoria > Subcategoria
   - Exemplo:
     ```yaml
     # categorias.yml
     categorias:
       - id: "eletrica_sensores"
         nome: "Elétrica - Sensores"
         keywords:
           - "sensor"
           - "temperatura"
           - "pressão"
           - "nível"
         subequipamentos_comuns:
           - "aplanadora_17_63"
           - "desenrolador"

       - id: "mecanica_cilindros"
         nome: "Mecânica - Cilindros"
         keywords:
           - "cilindro"
           - "rolo"
           - "eixo"
           - "mancal"
         subequipamentos_comuns:
           - "aplanadora_17_63"

       - id: "hidraulica_vazamento"
         nome: "Hidráulica - Vazamento"
         keywords:
           - "vazamento"
           - "óleo"
           - "hidráulico"
           - "mangueira"
     ```

2. **Implementar Sugestão por Cluster**
   - Buscar categoria mais comum no cluster
   - Calcular percentual de ocorrência
   - Confidence = (count_categoria / total_cluster)

3. **Implementar Sugestão por Histórico**
   - Buscar top-3 chamados mais similares (TF-IDF)
   - Verificar categorias desses chamados
   - Usar voto majoritário
   - Confidence = (votos_categoria / 3)

4. **Implementar Regras Técnicas**
   - Regras if-then baseadas em keywords
   - Exemplo: SE "sensor" E "temperatura" ENTÃO "Elétrica - Sensores"
   - Maior prioridade que outros métodos
   - Confidence = 0.95 (fixo para regras)

5. **Sistema de Combinação**
   - Combinar sugestões dos 3 métodos
   - Pesos: Regras (0.5), Cluster (0.3), Histórico (0.2)
   - Score final = weighted average
   - Retornar categoria com maior score

6. **Definir Limiares**
   - Threshold de automação total: confidence >= 0.85
   - Threshold de sugestão: confidence >= 0.60
   - Abaixo de 0.60: marcar como "Requer Revisão Manual"

7. **Geração de CSV para Importação**
   - Formato compatível com sistema alvo
   - Campos: ticket_id, categoria_sugerida, confidence, método_usado
   - Separar em 3 arquivos:
     - `auto_approved.csv`: confidence >= 0.85
     - `review_needed.csv`: 0.60 <= confidence < 0.85
     - `manual_required.csv`: confidence < 0.60

8. **Validação com Casos Reais**
   - Testar com 100 chamados rotulados manualmente
   - Calcular acurácia, precisão, recall
   - Matriz de confusão
   - Ajustar pesos e thresholds

#### Entregáveis
- ✅ `webapp/src/utils/triagem/config/categorias.yml`
- ✅ `webapp/src/utils/triagem/category_suggester.py`
- ✅ Script de export: `scripts/analysis/export_suggestions_csv.py`
- ✅ Relatório de acurácia: `reports/category_accuracy.md`

#### Exemplo de Código
```python
# webapp/src/utils/triagem/category_suggester.py

import yaml
from typing import Tuple, List, Dict
from collections import Counter

class CategorySuggester:
    def __init__(self,
                 config_file='config/categorias.yml',
                 clusterer=None,
                 similarity_search=None):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            self.categorias = config['categorias']

        self.clusterer = clusterer
        self.similarity_search = similarity_search

        # Pesos dos métodos
        self.weights = {
            'rules': 0.5,
            'cluster': 0.3,
            'history': 0.2
        }

    def suggest_by_rules(self, text: str,
                        subequipment: str = None) -> Tuple[str, float]:
        """Sugestão baseada em regras técnicas"""
        text_lower = text.lower()
        scores = {}

        for categoria in self.categorias:
            score = 0
            keywords = categoria.get('keywords', [])

            # Contar keywords presentes
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1

            # Bonus se subequipamento é comum para essa categoria
            if subequipment and subequipment in categoria.get('subequipamentos_comuns', []):
                score += 0.5

            if score > 0:
                # Normalizar pelo número total de keywords
                confidence = min(score / len(keywords), 1.0)
                scores[categoria['id']] = confidence

        if not scores:
            return (None, 0.0)

        # Retornar categoria com maior score
        best_category = max(scores, key=scores.get)
        confidence = scores[best_category] * 0.95  # Confidence fixo alto para regras

        return (best_category, confidence)

    def suggest_by_cluster(self, cluster_id: int,
                          historical_tickets: List[Dict]) -> Tuple[str, float]:
        """Sugestão baseada em categoria majoritária do cluster"""
        if cluster_id == -1:  # Ruído
            return (None, 0.0)

        # Filtrar tickets do mesmo cluster
        cluster_tickets = [t for t in historical_tickets
                           if t.get('cluster_id') == cluster_id]

        if not cluster_tickets:
            return (None, 0.0)

        # Contar categorias
        categories = [t.get('category') for t in cluster_tickets
                      if t.get('category')]

        if not categories:
            return (None, 0.0)

        counter = Counter(categories)
        most_common_category, count = counter.most_common(1)[0]
        confidence = count / len(cluster_tickets)

        return (most_common_category, confidence)

    def suggest_by_history(self, text: str,
                          historical_tickets: List[Dict],
                          top_k: int = 3) -> Tuple[str, float]:
        """Sugestão baseada em chamados similares"""
        if not self.similarity_search:
            return (None, 0.0)

        # Buscar similares
        similar = self.similarity_search.find_similar(text, top_k=top_k, threshold=0.6)

        if not similar:
            return (None, 0.0)

        # Buscar categorias dos similares
        categories = []
        for ticket_id, similarity_score in similar:
            ticket = next((t for t in historical_tickets if t['_id'] == ticket_id), None)
            if ticket and ticket.get('category'):
                categories.append(ticket['category'])

        if not categories:
            return (None, 0.0)

        # Voto majoritário
        counter = Counter(categories)
        most_common_category, count = counter.most_common(1)[0]
        confidence = count / len(categories)

        return (most_common_category, confidence)

    def suggest(self, text: str, cluster_id: int = None,
                subequipment: str = None,
                historical_tickets: List[Dict] = None) -> Dict:
        """
        Sugestão combinada de múltiplos métodos.

        Returns:
            {
                'category': str,
                'confidence': float,
                'method': str,
                'details': dict
            }
        """
        suggestions = {}

        # 1. Regras técnicas
        cat_rules, conf_rules = self.suggest_by_rules(text, subequipment)
        if cat_rules:
            suggestions['rules'] = {'category': cat_rules, 'confidence': conf_rules}

        # 2. Cluster
        if cluster_id is not None and historical_tickets:
            cat_cluster, conf_cluster = self.suggest_by_cluster(cluster_id, historical_tickets)
            if cat_cluster:
                suggestions['cluster'] = {'category': cat_cluster, 'confidence': conf_cluster}

        # 3. Histórico
        if historical_tickets:
            cat_history, conf_history = self.suggest_by_history(text, historical_tickets)
            if cat_history:
                suggestions['history'] = {'category': cat_history, 'confidence': conf_history}

        # Combinar sugestões
        if not suggestions:
            return {
                'category': None,
                'confidence': 0.0,
                'method': 'none',
                'details': {}
            }

        # Calcular score ponderado para cada categoria
        category_scores = {}
        for method, data in suggestions.items():
            category = data['category']
            confidence = data['confidence']
            weight = self.weights.get(method, 0)

            if category not in category_scores:
                category_scores[category] = 0
            category_scores[category] += confidence * weight

        # Melhor categoria
        best_category = max(category_scores, key=category_scores.get)
        best_confidence = category_scores[best_category]

        # Identificar método dominante
        dominant_method = max(suggestions.keys(),
                             key=lambda m: suggestions[m]['confidence'] * self.weights[m])

        return {
            'category': best_category,
            'confidence': float(best_confidence),
            'method': dominant_method,
            'details': suggestions
        }

    def get_category_name(self, category_id: str) -> str:
        """Retorna nome legível da categoria"""
        for cat in self.categorias:
            if cat['id'] == category_id:
                return cat['nome']
        return "Desconhecido"

# Uso
suggester = CategorySuggester(clusterer=clusterer, similarity_search=search)

result = suggester.suggest(
    text="Sensor de temperatura K3 com falha",
    cluster_id=5,
    subequipment="aplanadora_17_63",
    historical_tickets=historical_data
)

print(f"Categoria sugerida: {suggester.get_category_name(result['category'])}")
print(f"Confiança: {result['confidence']:.2%}")
print(f"Método: {result['method']}")
```

---

### 🔵 FASE 6 — Interface de Triagem (Human-in-the-Loop) (5,25 dias)

#### Objetivo
Criar dashboard interativo para revisão e aprovação de sugestões automáticas.

#### Funcionalidades
- Visualização de chamados pendentes
- Filtros por subequipamento, categoria, confiança
- Aprovação/rejeição em lote
- Correção manual de sugestões
- Registro de feedback para ML futuro

#### Atividades

1. **Criar Nova Página: `/maintenance/work-orders`**
   - Arquivo: `webapp/src/pages/maintenance/work_orders.py`
   - Layout principal com:
     - Estatísticas rápidas (cards no topo)
     - Tabela de chamados
     - Modal de detalhes

2. **Componente de Tabela**
   - Reutilizar `msgtable01.py` como base
   - Colunas:
     - Ticket Number
     - Data/Hora
     - Máquina
     - Subequipamento Sugerido (badge com confidence)
     - Categoria Sugerida (badge com confidence)
     - Status
     - Ações (Aprovar, Rejeitar, Editar)
   - Paginação
   - Ordenação por colunas

3. **Sidebar com Filtros**
   - Arquivo: `webapp/src/components/sidebars/work_orders_sidebar.py`
   - Filtros:
     - Status (Pendente, Aprovado, Rejeitado)
     - Confiança (Alta >= 0.85, Média >= 0.60, Baixa < 0.60)
     - Subequipamento (dropdown)
     - Categoria (dropdown)
     - Período (date pickers)
   - Quick Actions:
     - "Aprovar todos com confiança alta"
     - "Exportar selecionados"

4. **Cards de Estatísticas**
   - Total de Chamados Pendentes
   - Confiança Alta (verde)
   - Requer Revisão (amarelo)
   - Manual (vermelho)
   - Taxa de Aceitação Automática (%)

5. **Modal de Detalhes**
   - Visualizar chamado completo
   - Histórico de alarmes relacionados
   - Chamados similares (top-5)
   - Gráfico de cluster (se aplicável)
   - Campos editáveis:
     - Subequipamento
     - Categoria
     - Prioridade
     - Técnico Atribuído
   - Botões: Aprovar, Rejeitar, Salvar Correções

6. **Sistema de Aprovação em Lote**
   - Checkbox para selecionar múltiplos chamados
   - Botão "Aprovar Selecionados"
   - Confirmação com resumo
   - Atualização em batch no MongoDB

7. **Registro de Feedback**
   - Quando usuário corrige:
     - Salvar sugestão original em `user_corrections.original_suggestions`
     - Marcar flags: `subequipment_corrected`, `category_corrected`
     - Incrementar contador de correções para futuro treinamento

8. **Callbacks**
   - `work_orders_callbacks.py`:
     - Carregar dados da tabela
     - Filtrar por critérios
     - Atualizar estatísticas
   - `triagem_approval_callbacks.py`:
     - Aprovar/rejeitar chamados
     - Salvar correções
     - Atualizar status em MongoDB

9. **Integração com Sistema de Permissões**
   - Adicionar rotas em `access_control.py`:
     ```python
     "/maintenance/work-orders": {
         "shared": False,
         "perfis": ["manutencao", "admin"],
         "min_level": 2,  # Supervisores e acima
     }
     ```

10. **Testes com Usuários**
    - Beta testing com 2-3 usuários da manutenção
    - Coletar feedback sobre UX
    - Ajustar fluxo conforme necessário

#### Entregáveis
- ✅ `webapp/src/pages/maintenance/work_orders.py`
- ✅ `webapp/src/components/sidebars/work_orders_sidebar.py`
- ✅ `webapp/src/callbacks_registers/work_orders_callbacks.py`
- ✅ `webapp/src/callbacks_registers/triagem_approval_callbacks.py`
- ✅ Documentação de usuário: `docs/triagem/user_guide.md`

#### Exemplo de Código - Layout da Página
```python
# webapp/src/pages/maintenance/work_orders.py

import dash_bootstrap_components as dbc
from dash import html, dcc
from src.components.icons import get_icon

def layout():
    return dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.H2([
                    get_icon("clipboard-check", size=32),
                    " Triagem de Chamados"
                ], className="mb-4")
            ])
        ]),

        # Cards de Estatísticas
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("24", className="text-primary mb-0", id="stat-total"),
                        html.Small("Total Pendentes", className="text-muted")
                    ])
                ])
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("18", className="text-success mb-0", id="stat-high-conf"),
                        html.Small("Confiança Alta (≥85%)", className="text-muted")
                    ])
                ])
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("4", className="text-warning mb-0", id="stat-medium-conf"),
                        html.Small("Requer Revisão", className="text-muted")
                    ])
                ])
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("2", className="text-danger mb-0", id="stat-low-conf"),
                        html.Small("Manual", className="text-muted")
                    ])
                ])
            ], width=3),
        ], className="mb-4"),

        # Toolbar
        dbc.Row([
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button([
                        get_icon("check-all"),
                        " Aprovar Selecionados"
                    ], color="success", id="btn-approve-selected"),
                    dbc.Button([
                        get_icon("x-circle"),
                        " Rejeitar Selecionados"
                    ], color="danger", outline=True, id="btn-reject-selected"),
                    dbc.Button([
                        get_icon("download"),
                        " Exportar CSV"
                    ], color="primary", outline=True, id="btn-export-csv"),
                ])
            ], width=8),
            dbc.Col([
                dbc.Input(
                    type="search",
                    placeholder="Buscar...",
                    id="search-input"
                )
            ], width=4)
        ], className="mb-3"),

        # Tabela
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div(id="work-orders-table-container")
                    ])
                ])
            ])
        ]),

        # Modal de Detalhes
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Detalhes do Chamado")),
            dbc.ModalBody(id="modal-work-order-details"),
            dbc.ModalFooter([
                dbc.Button("Aprovar", id="modal-btn-approve", color="success"),
                dbc.Button("Salvar Correções", id="modal-btn-save", color="primary"),
                dbc.Button("Fechar", id="modal-btn-close", color="secondary")
            ])
        ], id="modal-work-order", size="xl", is_open=False),

        # Stores
        dcc.Store(id="work-orders-data"),
        dcc.Store(id="selected-ticket-id")

    ], fluid=True)
```

#### Exemplo de Código - Callback de Aprovação
```python
# webapp/src/callbacks_registers/triagem_approval_callbacks.py

from dash import Input, Output, State, callback_context
from src.database.connection import get_mongo_connection
from datetime import datetime

def register_triagem_approval_callbacks(app):

    @app.callback(
        Output("work-orders-data", "data"),
        Output("notification", "children"),
        Input("btn-approve-selected", "n_clicks"),
        Input("btn-reject-selected", "n_clicks"),
        State("work-orders-table", "selected_rows"),
        State("work-orders-data", "data"),
        prevent_initial_call=True
    )
    def handle_batch_approval(approve_clicks, reject_clicks, selected_rows, data):
        if not callback_context.triggered:
            return data, None

        trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]

        if not selected_rows:
            return data, dbc.Alert("Nenhum chamado selecionado", color="warning")

        collection = get_mongo_connection("maintenance_tickets")
        selected_tickets = [data[i] for i in selected_rows]
        ticket_ids = [t["_id"] for t in selected_tickets]

        if trigger_id == "btn-approve-selected":
            # Aprovar em lote
            collection.update_many(
                {"_id": {"$in": ticket_ids}},
                {
                    "$set": {
                        "approval_status": "approved",
                        "status": "triado",
                        "updated_date": datetime.utcnow()
                    }
                }
            )
            message = f"{len(ticket_ids)} chamados aprovados com sucesso!"
            color = "success"

        elif trigger_id == "btn-reject-selected":
            # Rejeitar em lote
            collection.update_many(
                {"_id": {"$in": ticket_ids}},
                {
                    "$set": {
                        "approval_status": "rejected",
                        "status": "requer_revisao",
                        "updated_date": datetime.utcnow()
                    }
                }
            )
            message = f"{len(ticket_ids)} chamados marcados para revisão"
            color = "warning"

        # Recarregar dados
        updated_data = list(collection.find({"status": {"$in": ["novo", "requer_revisao"]}}))

        return updated_data, dbc.Alert(message, color=color, duration=3000)


    @app.callback(
        Output("modal-work-order", "is_open"),
        Output("work-orders-data", "data", allow_duplicate=True),
        Input("modal-btn-approve", "n_clicks"),
        Input("modal-btn-save", "n_clicks"),
        State("selected-ticket-id", "data"),
        State("modal-input-subequipment", "value"),
        State("modal-input-category", "value"),
        prevent_initial_call=True
    )
    def handle_modal_actions(approve_clicks, save_clicks, ticket_id,
                            corrected_subequip, corrected_category):
        if not callback_context.triggered or not ticket_id:
            return False, []

        trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        collection = get_mongo_connection("maintenance_tickets")

        if trigger_id == "modal-btn-approve":
            # Aprovar sem correções
            collection.update_one(
                {"_id": ticket_id},
                {
                    "$set": {
                        "approval_status": "approved",
                        "status": "triado",
                        "updated_date": datetime.utcnow()
                    }
                }
            )

        elif trigger_id == "modal-btn-save":
            # Salvar correções
            ticket = collection.find_one({"_id": ticket_id})
            original_subequip = ticket.get("suggested_subequipment")
            original_category = ticket.get("suggested_category")

            corrections = {
                "subequipment_corrected": corrected_subequip != original_subequip,
                "category_corrected": corrected_category != original_category,
                "original_suggestions": {
                    "subequipment": original_subequip,
                    "category": original_category
                }
            }

            collection.update_one(
                {"_id": ticket_id},
                {
                    "$set": {
                        "suggested_subequipment": corrected_subequip,
                        "suggested_category": corrected_category,
                        "approval_status": "corrected",
                        "status": "triado",
                        "user_corrections": corrections,
                        "updated_date": datetime.utcnow()
                    }
                }
            )

        # Fechar modal e recarregar dados
        updated_data = list(collection.find({"status": {"$in": ["novo", "requer_revisao"]}}))
        return False, updated_data
```

---

### 🔵 FASE 7 (OPCIONAL) — Aprendizado Incremental com ML Supervisionado (4 dias)

#### Objetivo
Treinar modelo supervisionado para melhorar automaticamente com feedback humano.

**NOTA**: Esta fase é **OPCIONAL** e deve ser implementada apenas após as fases anteriores estarem **consolidadas e validadas**.

#### Pré-requisitos
- Mínimo de 500 chamados rotulados manualmente
- Sistema de feedback funcionando (Fase 6)
- Dados de correções humanas coletados

#### Atividades

1. **Preparação do Dataset Rotulado**
   - Extrair chamados com `approval_status == "approved"` ou `"corrected"`
   - Usar categorias finais (após correção humana)
   - Balanceamento de classes (se necessário)
   - Split: 80% treino, 20% teste

2. **Escolha de Modelo**
   - **Opção 1**: Logistic Regression (baseline)
   - **Opção 2**: Random Forest
   - **Opção 3**: SVM com kernel RBF
   - **Opção 4**: Naive Bayes (rápido, bom para texto)

3. **Feature Engineering**
   - Usar vetores TF-IDF já criados (Fase 3)
   - Features adicionais:
     - One-hot encoding de subequipamento
     - Hora do dia (madrugada, manhã, tarde, noite)
     - Dia da semana
     - Comprimento do texto

4. **Treinamento**
   - Cross-validation 5-fold
   - Grid search para hiperparâmetros
   - Avaliar múltiplas métricas (accuracy, precision, recall, F1)

5. **Integração no Pipeline**
   - Adicionar método `suggest_by_ml()` no `CategorySuggester`
   - Combinar com métodos existentes (regras, cluster, histórico)
   - Peso do ML: 0.3 (ajustar conforme acurácia)

6. **Sistema de Retreinamento**
   - Script para retreinar periodicamente (mensal)
   - Incremental: adicionar novos dados sem descartar antigos
   - Versionamento de modelos
   - A/B testing: comparar modelo novo vs antigo

7. **Validação Estatística**
   - Comparar acurácia ML vs sistema de regras
   - Análise de erros (confusion matrix)
   - Identificar categorias difíceis
   - Validação com holdout set

#### Entregáveis
- ✅ `webapp/src/utils/triagem/ml_classifier.py`
- ✅ Modelo treinado: `models/category_classifier.pkl`
- ✅ Script de retreinamento: `scripts/batch_processing/retrain_ml_model.py`
- ✅ Relatório de comparação: `reports/ml_vs_rules_comparison.md`

#### Exemplo de Código
```python
# webapp/src/utils/triagem/ml_classifier.py

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.metrics import classification_report, confusion_matrix
import numpy as np
import pickle

class MLCategoryClassifier:
    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        )
        self.is_fitted = False
        self.label_encoder = {}

    def prepare_features(self, tfidf_vectors, subequipments, timestamps):
        """Combina TF-IDF com features adicionais"""
        # One-hot encode subequipments
        unique_subequips = list(set(subequipments))
        subequip_features = np.array([
            [1 if s == subequip else 0 for subequip in unique_subequips]
            for s in subequipments
        ])

        # Temporal features (hora do dia)
        hours = [ts.hour for ts in timestamps]
        hour_features = np.array([
            [
                1 if 0 <= h < 6 else 0,   # madrugada
                1 if 6 <= h < 12 else 0,  # manhã
                1 if 12 <= h < 18 else 0, # tarde
                1 if 18 <= h < 24 else 0  # noite
            ]
            for h in hours
        ])

        # Combinar todas as features
        combined = np.hstack([
            tfidf_vectors.toarray(),
            subequip_features,
            hour_features
        ])

        return combined

    def fit(self, X, y):
        """Treina o modelo"""
        # Encode labels
        unique_labels = list(set(y))
        self.label_encoder = {label: i for i, label in enumerate(unique_labels)}
        self.inverse_label_encoder = {i: label for label, i in self.label_encoder.items()}

        y_encoded = [self.label_encoder[label] for label in y]

        # Treinar
        self.model.fit(X, y_encoded)
        self.is_fitted = True

    def predict_proba(self, X):
        """Retorna probabilidades de cada classe"""
        if not self.is_fitted:
            raise ValueError("Model not fitted")

        probas = self.model.predict_proba(X)
        return probas

    def predict(self, X, return_confidence=True):
        """Predição com confiança"""
        probas = self.predict_proba(X)

        # Classe com maior probabilidade
        predicted_indices = np.argmax(probas, axis=1)
        predicted_labels = [self.inverse_label_encoder[idx] for idx in predicted_indices]

        if return_confidence:
            confidences = [probas[i, idx] for i, idx in enumerate(predicted_indices)]
            return list(zip(predicted_labels, confidences))
        else:
            return predicted_labels

    def evaluate(self, X_test, y_test):
        """Avalia o modelo"""
        y_test_encoded = [self.label_encoder[label] for label in y_test]
        y_pred = self.model.predict(X_test)

        print("Classification Report:")
        print(classification_report(y_test_encoded, y_pred,
                                    target_names=list(self.label_encoder.keys())))

        print("\nConfusion Matrix:")
        print(confusion_matrix(y_test_encoded, y_pred))

    def save(self, filepath):
        """Salva modelo"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'label_encoder': self.label_encoder,
                'inverse_label_encoder': self.inverse_label_encoder
            }, f)

    def load(self, filepath):
        """Carrega modelo"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.label_encoder = data['label_encoder']
            self.inverse_label_encoder = data['inverse_label_encoder']
            self.is_fitted = True

# Uso
classifier = MLCategoryClassifier()

# Treinar
X_train = prepare_features(tfidf_vectors_train, subequips_train, timestamps_train)
classifier.fit(X_train, categories_train)

# Avaliar
X_test = prepare_features(tfidf_vectors_test, subequips_test, timestamps_test)
classifier.evaluate(X_test, categories_test)

# Predizer novo
X_new = prepare_features(new_tfidf, new_subequip, new_timestamp)
predictions = classifier.predict(X_new, return_confidence=True)
for category, confidence in predictions:
    print(f"{category}: {confidence:.2%}")

# Salvar
classifier.save('models/category_classifier.pkl')
```

---

## ⏱ Resumo de Prazo e Esforço

| Fase | Tempo (h) | Tempo (dias úteis) | Complexidade | Prioridade |
|------|-----------|-------------------|--------------|------------|
| Fase 0 — Análise de Dados | 24h | 3 dias | 🟢 Baixa | CRÍTICA |
| Fase 1 — Normalização | 32h | 4 dias | 🟢 Média | CRÍTICA |
| Fase 2 — Subequipamento | 52h | 6,5 dias | 🟡 Média-Alta | CRÍTICA |
| Fase 3 — Vetorização | 34h | 4,25 dias | 🟡 Média-Alta | ALTA |
| Fase 4 — Clustering | 42h | 5,25 dias | 🟠 Alta | MÉDIA |
| Fase 5 — Categorização | 36h | 4,5 dias | 🟡 Média-Alta | ALTA |
| Fase 6 — Interface | 42h | 5,25 dias | 🟡 Média-Alta | CRÍTICA |
| Fase 7 — ML (opcional) | 32h | 4 dias | 🔴 Alta | BAIXA |
| **Total (sem Fase 7)** | **262h** | **32,75 dias** | **ALTO ESFORÇO** | — |
| **Total (com Fase 7)** | **294h** | **36,75 dias** | **MUITO ALTO** | — |

### Conversão para Calendário (considerando 8h/dia útil)
- **Sem Fase 7**: ~33 dias úteis = **~7 semanas** (1,75 mês)
- **Com Fase 7**: ~37 dias úteis = **~8 semanas** (2 meses)

### Observações Importantes
- Tempos consideram **1 desenvolvedor em tempo integral**
- Não incluem: revisões, reuniões, validações com usuário
- Buffer recomendado: **+30%** para ajustes e imprevistos
- Estimativa realista: **2-3 meses** para MVP completo

---

## 🎯 Resultados Esperados

### 📊 Métricas de Sucesso

#### 1. **Redução de Tempo Administrativo**
- **Antes**: ~15 minutos por chamado (classificação manual)
- **Depois**: ~2 minutos (apenas revisão de sugestões)
- **Ganho**: ~87% de redução de tempo
- **ROI**: Com 50 chamados/dia = **economiza ~10 horas/dia**

#### 2. **Acurácia de Classificação**
- **Subequipamento**: 80-85% de acurácia esperada
- **Categoria**: 70-75% de acurácia esperada
- **Confiança Alta (>=0.85)**: 60-70% dos chamados aprovados automaticamente

#### 3. **Padronização de Dados**
- 100% dos chamados com estrutura uniforme
- Eliminação de inconsistências de nomenclatura
- Base sólida para análises futuras

#### 4. **Visibilidade de Recorrências**
- Identificação automática de problemas repetitivos
- Agrupamento de falhas similares
- Priorização baseada em frequência

### 📈 Benefícios de Negócio

#### 1. **Gestão de Manutenção**
- Rastreamento completo de chamados
- Histórico confiável de intervenções
- Análise de performance por subequipamento
- Identificação de equipamentos críticos

#### 2. **Análise de Confiabilidade**
- Base para cálculo de MTBF (Mean Time Between Failures)
- Análise de Pareto automatizada
- Identificação de modos de falha dominantes
- Suporte a RCM (Reliability-Centered Maintenance)

#### 3. **Tomada de Decisão**
- Dados estruturados para planejamento de manutenção
- Identificação de necessidade de treinamento
- Justificativa para investimentos em equipamentos
- Análise de custo de falhas

#### 4. **Melhoria Contínua**
- Feedback loop com aprendizado de máquina
- Refinamento contínuo de classificações
- Evolução do glossário técnico
- Melhoria da qualidade de abertura de chamados

### 🔮 Expansões Futuras Possíveis

#### 1. **Manutenção Preditiva**
- Correlação de alarmes com chamados
- Detecção de padrões pré-falha
- Alertas preventivos

#### 2. **Integração com ERP/SAP**
- Exportação automática de ordens de serviço
- Sincronização de estoque de peças
- Gestão de custos de manutenção

#### 3. **Mobile App**
- Abertura de chamados via smartphone
- Foto da falha anexada automaticamente
- Notificações push para técnicos

#### 4. **Analytics Avançado**
- Dashboard executivo com KPIs
- Previsão de demanda de manutenção
- Otimização de alocação de equipe
- Análise de sazonalidade de falhas

#### 5. **Assistente Virtual**
- Chatbot para abertura de chamados
- Sugestões de troubleshooting em tempo real
- Busca inteligente de procedimentos

---

## 🚀 Recomendações de Implementação

### Estratégia Sugerida: **MVP Incremental**

#### Sprint 1 (4 semanas) - **FUNDAÇÃO**
- ✅ Fase 0: Análise de Dados
- ✅ Fase 1: Normalização
- ✅ Fase 2: Identificação de Subequipamento
- **Entrega**: Sistema que identifica subequipamento com confiança

#### Sprint 2 (3 semanas) - **SIMILARIDADE**
- ✅ Fase 3: Vetorização TF-IDF
- ✅ Fase 5: Sugestão de Categoria (sem clustering)
- **Entrega**: Sistema que sugere categoria baseado em regras + histórico

#### Sprint 3 (3 semanas) - **INTERFACE**
- ✅ Fase 6: Interface de Triagem
- **Entrega**: Dashboard funcional para revisão humana

#### Sprint 4 (2 semanas) - **REFINAMENTO**
- ✅ Fase 4: Clustering
- ✅ Ajustes e otimizações
- **Entrega**: Sistema completo com clustering

#### Sprint 5 (FUTURO) - **MACHINE LEARNING**
- ✅ Fase 7: Aprendizado Supervisionado (opcional)
- **Entrega**: Modelo ML em produção

### Equipe Recomendada
- **1 Desenvolvedor Python/Data Science** (tempo integral)
- **1 Engenheiro de Manutenção** (consultoria 20%)
- **1 Product Owner** (validações semanais)

### Ferramentas e Tecnologias
- **Backend**: Python 3.9+, scikit-learn, hdbscan, pandas, numpy
- **Frontend**: Dash 3.1.1, Dash Bootstrap Components
- **Database**: MongoDB (já em uso)
- **Versionamento**: Git
- **Documentação**: Markdown, Jupyter Notebooks

---

## 📚 Documentação a Produzir

1. **Documentação Técnica**
   - `docs/triagem/architecture.md`: Arquitetura detalhada
   - `docs/triagem/api_reference.md`: Referência de APIs
   - `docs/triagem/database_schema.md`: Schema do MongoDB

2. **Documentação de Usuário**
   - `docs/triagem/user_guide.md`: Guia do usuário final
   - `docs/triagem/admin_guide.md`: Guia para administradores
   - `docs/triagem/faq.md`: Perguntas frequentes

3. **Documentação de Processos**
   - `docs/triagem/glossary.md`: Glossário técnico
   - `docs/triagem/maintenance_procedures.md`: Procedimentos de manutenção do sistema
   - `docs/triagem/troubleshooting.md`: Solução de problemas

---

## ⚠️ Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Dados históricos de baixa qualidade | Alta | Alto | Começar com normalização extensiva e validação manual |
| Resistência da equipe ao novo sistema | Média | Alto | Envolver usuários desde o início, treinamento adequado |
| Glossário técnico incompleto | Alta | Médio | Processo iterativo de refinamento, feedback contínuo |
| Performance ruim em produção | Baixa | Médio | Testes de carga, otimização de queries, cache |
| Modelo ML com baixa acurácia | Média | Médio | Não depender exclusivamente de ML, manter sistema híbrido |
| Complexidade de manutenção | Média | Médio | Documentação extensiva, código limpo e testado |

---

## ✅ Critérios de Aceitação do MVP

Para considerar o MVP bem-sucedido:

1. ✅ Sistema identifica subequipamento com **>=80% de acurácia**
2. ✅ Sistema sugere categoria com **>=70% de acurácia**
3. ✅ **>=60%** dos chamados são classificados com confiança alta (>=0.85)
4. ✅ Interface permite revisão em lote de **>=50 chamados em <10 minutos**
5. ✅ Tempo médio de triagem reduzido em **>=80%**
6. ✅ Sistema roda **100% local** sem dependências externas
7. ✅ Integração com MongoDB sem impacto em performance existente
8. ✅ Documentação completa e glossários atualizados
9. ✅ Aprovação da equipe de manutenção após 2 semanas de testes

---

## 📞 Próximos Passos

### Imediatos (Antes de Começar)
1. ✅ **Validar viabilidade** com stakeholders (manutenção, TI, gestão)
2. ✅ **Aprovar orçamento** de tempo e recursos
3. ✅ **Definir equipe** responsável
4. ✅ **Acessar dados históricos** (coleção `DecapadoFalhas`)
5. ✅ **Preparar ambiente** de desenvolvimento

### Primeira Semana
1. ✅ **Executar Fase 0**: Extrair e analisar amostra de dados
2. ✅ **Workshop** com equipe de manutenção para definir glossários
3. ✅ **Documentar** subequipamentos oficiais da planta
4. ✅ **Criar** estrutura de pastas e arquivos base

---

## 📄 Conclusão

Este plano de implementação adapta o sistema de triagem automática de chamados ao contexto específico do **projeto AMG_Data**. A arquitetura proposta aproveita a infraestrutura existente (MongoDB, Dash, Node-RED) e segue os padrões já estabelecidos no projeto.

**Viabilidade**: ALTA - O projeto possui todas as bases necessárias.

**Recomendação**: Implementação gradual começando pelas Fases 0-2 para validação de valor antes de investir em features avançadas.

**ROI Esperado**: Com 50 chamados/dia, economiza ~10 horas/dia de trabalho administrativo, liberando a equipe para atividades de maior valor.

---

**Documento criado em**: 2026-01-18
**Versão**: 1.0
**Autor**: Claude Code
**Projeto**: AMG_Data - Sistema de Triagem Automática
