# 🔧 Melhorias - Sistema ZPP Processing

Detalhamento técnico das melhorias identificadas no sistema de processamento de planilhas ZPP.

**Status Atual**: Sistema funcional e em produção ✅
**Nota Geral**: 8.5/10

---

## 📊 Resumo da Revisão

### ✅ Pontos Fortes

- **Arquitetura bem planejada** - Separação clara de responsabilidades
- **Código limpo** - Docstrings, type hints, nomes descritivos
- **Robustez** - Tratamento de duplicatas, detecção automática de tipo
- **Documentação excelente** - README completo com exemplos práticos
- **Normalização de colunas** - MongoDB-friendly, remove acentos

### ⚠️ Áreas de Melhoria

- Validação de dados de entrada
- Exceções genéricas (`except:`)
- Código duplicado (índices, duplicatas)
- Performance em grandes volumes
- Usabilidade (argumentos CLI)

---

## 🔴 Alta Prioridade

### 1. Validação de Schema

**Arquivo**: `process_zpp_to_mongo.py`

#### Problema Atual

```python
# Linha 118-170: prepare_dataframe
# Não valida se DataFrame tem todas as colunas obrigatórias
# Só descobre erro ao tentar acessar coluna inexistente
```

Consequências:
- ❌ Erro só aparece durante processamento
- ❌ Arquivo pode ser parcialmente processado
- ❌ Mensagem de erro pouco clara

#### Solução Proposta

```python
def validate_schema(self, df: pd.DataFrame, file_type: str) -> tuple[bool, list]:
    """
    Valida se DataFrame tem todas as colunas obrigatórias

    Args:
        df: DataFrame a validar
        file_type: 'zppprd' ou 'zppparadas'

    Returns:
        (is_valid, missing_columns)
    """
    from clean_zpp_data import ZPPCleaner

    required = ZPPCleaner.CRITICAL_COLUMNS[file_type]['required']
    missing = [col for col in required if col not in df.columns]

    if missing:
        logger.error(f"❌ Colunas obrigatórias faltando: {missing}")
        logger.error(f"   Colunas encontradas: {list(df.columns)[:10]}")
        return False, missing

    logger.info(f"✓ Schema validado: todas as colunas obrigatórias presentes")
    return True, []

# Uso em process_file (após limpeza, antes de preparar):
is_valid, missing = self.validate_schema(df_clean, file_type)
if not is_valid:
    return {
        'file': file_name,
        'success': False,
        'error': f'Schema inválido: colunas faltando {missing}'
    }
```

#### Benefícios

- ✅ Falha rápida (fail-fast)
- ✅ Mensagem de erro clara
- ✅ Evita processamento parcial
- ✅ Facilita debug

#### Estimativa

- **Esforço**: 1-2 horas
- **Complexidade**: Baixa
- **Impacto**: Alto

---

### 2. Exceções Específicas

**Arquivo**: `process_zpp_to_mongo.py`, `clean_zpp_data.py`

#### Problema Atual

```python
# process_zpp_to_mongo.py:104
def extract_year_from_data(self, df: pd.DataFrame, file_type: str) -> int:
    try:
        # ...
        return first_date.year
    except:  # ❌ PROBLEMA: captura TODOS os erros
        return datetime.now().year
```

Consequências:
- ❌ Esconde erros reais (ex: bug de código)
- ❌ Pode retornar ano errado silenciosamente
- ❌ Dificulta debug

#### Solução Proposta

```python
def extract_year_from_data(self, df: pd.DataFrame, file_type: str) -> int:
    """Extrai o ano dos dados baseado nas colunas de data"""
    try:
        if file_type == 'zppprd':
            date_col = 'FIniNotif'
        else:
            date_col = 'DATA INICIO'

        # Verificar se coluna existe
        if date_col not in df.columns:
            logger.warning(f"Coluna de data '{date_col}' não encontrada")
            return datetime.now().year

        first_date = df[date_col].dropna().iloc[0]

        if isinstance(first_date, pd.Timestamp):
            return first_date.year
        else:
            logger.warning(f"Tipo inesperado para data: {type(first_date)}")
            return datetime.now().year

    except (KeyError, IndexError, AttributeError) as e:
        logger.warning(f"Não foi possível extrair ano dos dados: {e}")
        logger.warning(f"Usando ano atual: {datetime.now().year}")
        return datetime.now().year
    except Exception as e:
        # Apenas erros verdadeiramente inesperados chegam aqui
        logger.error(f"Erro inesperado ao extrair ano: {e}")
        raise  # Re-raise para não esconder bugs
```

#### Outras Ocorrências

**clean_zpp_data.py:244**:
```python
except Exception as e:  # ✅ OK: captura específica e loga
    logger.error(f"✗ Erro ao carregar arquivo: {e}")
    raise
```

**process_zpp_to_mongo.py:139**:
```python
def convert_time_types(x):
    # ...
    elif isinstance(x, timedelta):
        return str(x)
    # ❌ PROBLEMA: sem else, retorna None para tipos inesperados
    else:
        return x  # ✅ ADICIONAR: retorna valor original
```

#### Benefícios

- ✅ Erros claros e localizados
- ✅ Logs informativos
- ✅ Facilita manutenção
- ✅ Não esconde bugs

#### Estimativa

- **Esforço**: 2-3 horas (múltiplos arquivos)
- **Complexidade**: Baixa
- **Impacto**: Alto

---

### 3. Limite de Tamanho

**Arquivo**: `clean_zpp_data.py:236`

#### Problema Atual

```python
def load_data(self) -> pd.DataFrame:
    # ...
    self.df = pd.read_excel(self.file_path, sheet_name=0)
    # ❌ Carrega arquivo inteiro na memória
    # ❌ Nenhum limite ou aviso
```

Consequências:
- ❌ Arquivos gigantes (>500MB) podem estourar memória
- ❌ Sistema trava sem aviso prévio
- ❌ Não há indicação de progresso

#### Solução Proposta

```python
import os

def load_data(self) -> pd.DataFrame:
    """Carrega os dados do arquivo Excel com verificação de tamanho"""
    logger.info(f"Carregando arquivo: {self.file_path}")

    # Verificar tamanho do arquivo
    file_size_mb = os.path.getsize(self.file_path) / (1024 * 1024)
    logger.info(f"Tamanho do arquivo: {file_size_mb:.1f} MB")

    # Avisos baseados em tamanho
    if file_size_mb > 200:
        logger.error(f"❌ Arquivo muito grande ({file_size_mb:.1f} MB)")
        logger.error(f"   Limite recomendado: 200 MB")
        logger.error(f"   Considere dividir o arquivo ou usar processamento em chunks")
        raise ValueError(f"Arquivo excede limite de 200 MB")
    elif file_size_mb > 100:
        logger.warning(f"⚠️  Arquivo grande ({file_size_mb:.1f} MB)")
        logger.warning(f"   O processamento pode demorar...")

    try:
        self.df = pd.read_excel(self.file_path, sheet_name=0)
        self.original_rows = len(self.df)

        logger.info(f"✓ Arquivo carregado: {self.original_rows:,} linhas x {len(self.df.columns)} colunas")
        logger.info(f"  Tipo: {self.config['description']}")
        logger.info(f"  Memória usada: {self.df.memory_usage(deep=True).sum() / (1024**2):.1f} MB")

        return self.df

    except MemoryError:
        logger.error(f"❌ Memória insuficiente para carregar arquivo")
        logger.error(f"   Tamanho: {file_size_mb:.1f} MB")
        logger.error(f"   Solução: Use processamento em chunks ou aumente memória")
        raise
    except Exception as e:
        logger.error(f"✗ Erro ao carregar arquivo: {e}")
        raise
```

#### Benefícios

- ✅ Previne travamentos por falta de memória
- ✅ Feedback claro sobre arquivos grandes
- ✅ Informações úteis para debug
- ✅ Experiência do usuário melhorada

#### Estimativa

- **Esforço**: 1 hora
- **Complexidade**: Baixa
- **Impacto**: Médio-Alto

---

## 🟡 Média Prioridade

### 4. Refatoração - Duplicação

**Arquivo**: `process_zpp_to_mongo.py:172-215, 336-376`

#### Problema Atual

Código quase idêntico para Produção vs Paradas:

```python
def create_indexes_producao(self, collection):
    # ... código similar ...
    indexes = [...]
    for keys, name, options in indexes:
        try:
            collection.create_index(keys, name=name, **options)
        except Exception as e:
            logger.warning(f"...")

def create_indexes_paradas(self, collection):
    # ... código quase idêntico ...
```

#### Solução Proposta

```python
# Constantes de configuração
INDEX_CONFIGS = {
    'zppprd': [
        ([('pto_trab', ASCENDING), ('fininotif', DESCENDING)], 'idx_equipamento_data', {}),
        ([('ordem', ASCENDING)], 'idx_ordem_unique', {'unique': True, 'sparse': True}),
        ([('fininotif', ASCENDING), ('ffinnotif', ASCENDING)], 'idx_range_datas', {}),
        ([('_year', ASCENDING)], 'idx_year', {}),
        ([('pto_trab', ASCENDING), ('kg_proc', DESCENDING)], 'idx_equipamento_producao', {})
    ],
    'zppparadas': [
        ([('linea', ASCENDING), ('data_inicio', DESCENDING)], 'idx_linha_data', {}),
        ([('ordem', ASCENDING)], 'idx_ordem', {'sparse': True}),
        ([('linea', ASCENDING), ('data_inicio', ASCENDING), ('hora_inicio', ASCENDING), ('ordem', ASCENDING)],
         'idx_parada_unique', {'unique': True, 'sparse': True}),
        ([('motivo', ASCENDING)], 'idx_motivo', {}),
        ([('data_inicio', ASCENDING), ('data_fim', ASCENDING)], 'idx_range_datas', {}),
        ([('_year', ASCENDING)], 'idx_year', {}),
        ([('duracao_min', DESCENDING)], 'idx_duracao', {})
    ]
}

def create_indexes(self, collection, file_type: str):
    """Cria índices otimizados baseado no tipo de arquivo"""
    logger.info(f"  Criando índices para {file_type.upper()}...")

    indexes = INDEX_CONFIGS.get(file_type, [])

    for keys, name, options in indexes:
        try:
            collection.create_index(keys, name=name, **options)
        except Exception as e:
            logger.warning(f"  [!] Índice {name} já existe ou erro: {e}")

    logger.info(f"  [OK] {len(indexes)} índices configurados")

# Uso simplificado:
if file_type == 'zppprd':
    self.create_indexes(collection, 'zppprd')
else:
    self.create_indexes(collection, 'zppparadas')
```

#### Benefícios

- ✅ DRY (Don't Repeat Yourself)
- ✅ Mais fácil adicionar novos tipos
- ✅ Configuração centralizada
- ✅ Menos código para manter

#### Estimativa

- **Esforço**: 2-3 horas
- **Complexidade**: Média
- **Impacto**: Médio (manutenibilidade)

---

### 5. Cache de Duplicatas

**Arquivo**: `process_zpp_to_mongo.py:336-376`

#### Problema Atual

```python
# A cada lote, faz query no MongoDB
for i in range(0, total_records, batch_size):
    batch = records[i:i + batch_size]

    # ❌ Query para cada lote (se 100k registros, 100 queries)
    existing = set(doc['ordem'] for doc in collection.find(
        {'ordem': {'$in': ordens_to_check}},
        {'ordem': 1}
    ))
```

Consequências:
- ⚠️ Lento em redes lentas
- ⚠️ Muitas queries ao MongoDB
- ⚠️ Não escala bem para arquivos grandes

#### Solução Proposta

```python
def build_existing_keys_cache(self, collection, file_type: str) -> set:
    """
    Constrói cache local de chaves já existentes

    Args:
        collection: Collection MongoDB
        file_type: 'zppprd' ou 'zppparadas'

    Returns:
        Set com chaves existentes
    """
    logger.info("  Construindo cache de duplicatas...")

    if file_type == 'zppprd':
        # Cache apenas ordens (não-null)
        cursor = collection.find({'ordem': {'$ne': None}}, {'ordem': 1})
        cache = {doc['ordem'] for doc in cursor}
    else:
        # Cache chaves compostas para paradas
        cursor = collection.find({}, {
            'linea': 1, 'data_inicio': 1, 'hora_inicio': 1, 'ordem': 1
        })
        cache = {
            f"{doc.get('linea')}|{doc.get('data_inicio')}|{doc.get('hora_inicio')}|{doc.get('ordem')}"
            for doc in cursor
        }

    logger.info(f"  [OK] Cache construído: {len(cache):,} chaves")
    return cache

# No início do upload (antes do loop de lotes):
existing_cache = self.build_existing_keys_cache(collection, file_type)

# No loop de lotes:
if file_type == 'zppprd':
    batch = [r for r in batch if r.get('ordem') is None or r['ordem'] not in existing_cache]
else:
    batch = [r for r in batch if
             f"{r.get('linea')}|{r.get('data_inicio')}|{r.get('hora_inicio')}|{r.get('ordem')}"
             not in existing_cache]
```

#### Alternativa A: Usar Upsert

```python
# Opção mais simples: usar bulk_write com upsert
from pymongo import UpdateOne

operations = []
for record in records:
    if file_type == 'zppprd':
        filter_query = {'ordem': record['ordem']} if record.get('ordem') else {'_id': record['_id']}
    else:
        filter_query = {
            'linea': record['linea'],
            'data_inicio': record['data_inicio'],
            'hora_inicio': record['hora_inicio'],
            'ordem': record['ordem']
        }

    operations.append(UpdateOne(
        filter_query,
        {'$setOnInsert': record},
        upsert=True
    ))

result = collection.bulk_write(operations, ordered=False)
logger.info(f"Inseridos: {result.upserted_count}, Duplicatas: {len(operations) - result.upserted_count}")
```

#### Alternativa B: Delete + Reinsert (preferida para correções/extornos)

**Contexto**: Quando uma planilha é re-enviada com valores corrigidos (ex: extornos mensais no ZPP),
o comportamento atual ignora os registros duplicados. A estratégia delete+reinsert resolve isso
mantendo a performance de `insert_many` e sem a complexidade de update campo a campo.

**Funcionamento**:
1. Identifica quais registros do arquivo já existem no MongoDB (pela chave natural)
2. **Deleta** esses registros existentes (em lote)
3. **Reinsere** todos os registros do arquivo normalmente via `insert_many`

```python
def _replace_duplicates(self, collection, records: list, file_type: str) -> tuple[int, int]:
    """
    Para registros duplicados: deleta os existentes e reinsere os novos.
    Registros novos (sem duplicata) são inseridos normalmente.

    Returns:
        (inserted_count, replaced_count)
    """
    if file_type == 'zppprd':
        ordens = [r['ordem'] for r in records if r.get('ordem') is not None]
        existing_ordens = set(
            doc['ordem'] for doc in collection.find(
                {'ordem': {'$in': ordens}}, {'ordem': 1}
            )
        )
        duplicates = [r for r in records if r.get('ordem') in existing_ordens]
        new_records = [r for r in records if r.get('ordem') not in existing_ordens]

        if duplicates:
            # Salvar backup em memória para rollback
            backup = list(collection.find({'ordem': {'$in': list(existing_ordens)}}))
            try:
                collection.delete_many({'ordem': {'$in': list(existing_ordens)}})
                collection.insert_many(duplicates, ordered=False)
            except Exception as e:
                logger.error(f"Erro ao substituir duplicatas, revertendo: {e}")
                collection.insert_many(backup, ordered=False)
                raise

    else:  # paradas
        keys_to_check = [
            {
                'centro_de_trabalho': r['centro_de_trabalho'],
                'inicio_execucao': r['inicio_execucao'],
                'inicio_real_hora': r['inicio_real_hora'],
                'ordem': r['ordem']
            }
            for r in records
            if all(k in r for k in ['centro_de_trabalho', 'inicio_execucao', 'inicio_real_hora', 'ordem'])
        ]
        existing_keys = set()
        for doc in collection.find({'$or': keys_to_check}, {
            'centro_de_trabalho': 1, 'inicio_execucao': 1, 'inicio_real_hora': 1, 'ordem': 1
        }):
            existing_keys.add(
                f"{doc.get('centro_de_trabalho')}|{doc.get('inicio_execucao')}|"
                f"{doc.get('inicio_real_hora')}|{doc.get('ordem')}"
            )

        def record_key(r):
            return f"{r.get('centro_de_trabalho')}|{r.get('inicio_execucao')}|{r.get('inicio_real_hora')}|{r.get('ordem')}"

        duplicates = [r for r in records if record_key(r) in existing_keys]
        new_records = [r for r in records if record_key(r) not in existing_keys]

        if duplicates:
            backup = list(collection.find({'$or': keys_to_check}))
            try:
                collection.delete_many({'$or': keys_to_check})
                collection.insert_many(duplicates, ordered=False)
            except Exception as e:
                logger.error(f"Erro ao substituir duplicatas, revertendo: {e}")
                collection.insert_many(backup, ordered=False)
                raise

    replaced = len(duplicates) if 'duplicates' in dir() else 0
    if new_records:
        collection.insert_many(new_records, ordered=False)

    return len(new_records), replaced
```

**Comparação das estratégias de duplicata**:

| Cenário | Skip (atual) | Upsert | Delete+Reinsert |
|---|---|---|---|
| Primeiro upload | Insere tudo | Insere tudo | Insere tudo |
| Re-upload sem mudanças | Skip (no-op) | Atualiza (no-op efetivo) | Deleta+reinsere |
| Re-upload com extorno | **Ignora — bug** | Atualiza campos | Deleta+reinsere corretamente |
| Performance | Mais rápido | Mais lento (1 op/registro) | Rápido (delete em lote + insert_many) |
| Atomicidade | Segura | Segura por registro | Risco: delete ok → insert falha → usa backup em memória |
| Sem mudanças em arquivo parcial | Insert novos apenas | Update existentes + insert novos | Deleta afetados + reinsere |

**Trade-off principal**: delete+reinsert não é atômico nativamente. A mitigação via backup em memória
cobre falhas de insert, mas o backup pode ser grande se o arquivo tiver muitos duplicados. Para
volumes típicos do ZPP (< 5.000 registros/planilha), isso é aceitável.

**Estimativa de implementação**: 3-4 horas
**Recomendação**: Substituir a lógica de skip atual por `_replace_duplicates` no loop de lotes em `processor.py`.

#### Benefícios

- ✅ Menos queries ao MongoDB (1 vs 100)
- ✅ Mais rápido em redes lentas
- ✅ Melhor escalabilidade
- ⚠️ Usa mais memória (trade-off)

#### Estimativa

- **Esforço**: 3-4 horas
- **Complexidade**: Média
- **Impacto**: Alto (performance)

---

### 6. Argumentos CLI

**Arquivo**: `process_zpp_quick.py`

#### Problema Atual

```python
# Hardcoded
INPUT_DIR = "zpp_input"
SCRIPT = "process_zpp_to_mongo.py"
```

Consequências:
- ❌ Não aceita argumentos personalizados
- ❌ Usuário não pode mudar diretório facilmente
- ❌ Não suporta --no-archive

#### Solução Proposta

```python
import argparse
import sys

def parse_args():
    """Parse argumentos de linha de comando"""
    parser = argparse.ArgumentParser(
        description='Processamento rápido de planilhas ZPP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Exemplos:
  python process_zpp_quick.py                      # Usa zpp_input/
  python process_zpp_quick.py --input meu_dir      # Diretório customizado
  python process_zpp_quick.py --no-archive         # Não move arquivos
  python process_zpp_quick.py --help               # Mostra esta ajuda
        '''
    )

    parser.add_argument(
        '--input',
        default='zpp_input',
        help='Diretório de entrada com planilhas Excel (default: zpp_input)'
    )

    parser.add_argument(
        '--no-archive',
        action='store_true',
        help='Não mover arquivos processados para analisados/'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Tamanho do lote para upload (default: 1000)'
    )

    return parser.parse_args()

def main():
    args = parse_args()

    print("\n" + "="*80)
    print("PROCESSAMENTO RÁPIDO ZPP")
    print("="*80)

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"\n[!] Pasta '{args.input}' não encontrada!")
        print(f"[!] Criando pasta...")
        input_path.mkdir(exist_ok=True)
        print(f"[OK] Pasta criada: {input_path.absolute()}")
        print(f"\n[!] Coloque os arquivos Excel na pasta '{args.input}' e execute novamente.")
        return

    # Construir comando
    cmd = [sys.executable, SCRIPT, str(input_path)]

    if args.no_archive:
        cmd.append('--no-archive')

    # Executar
    result = subprocess.run(cmd)
    # ... resto do código
```

#### Benefícios

- ✅ Flexibilidade para usuário
- ✅ Help integrado (`--help`)
- ✅ Suporte a flags (--no-archive)
- ✅ Mais profissional

#### Estimativa

- **Esforço**: 1-2 horas
- **Complexidade**: Baixa
- **Impacto**: Baixo-Médio (usabilidade)

---

## 🟢 Baixa Prioridade

### 7. Processamento em Chunks

**Arquivo**: `clean_zpp_data.py`

Para arquivos **muito grandes** (>200MB), processar em pedaços.

```python
def load_data_chunked(self, chunk_size: int = 50000) -> pd.DataFrame:
    """Carrega dados em chunks para economizar memória"""
    chunks = []

    for chunk in pd.read_excel(self.file_path, sheet_name=0, chunksize=chunk_size):
        # Processar chunk individualmente
        chunks.append(chunk)

    self.df = pd.concat(chunks, ignore_index=True)
    # ... resto
```

**Estimativa**: 4-6 horas | **Complexidade**: Alta

---

### 8. Relatório de Saúde

Adicionar relatório de qualidade dos dados:

```python
def generate_health_report(self, df: pd.DataFrame) -> dict:
    """Gera relatório de saúde dos dados"""
    return {
        'total_rows': len(df),
        'null_counts': df.isnull().sum().to_dict(),
        'duplicates': df.duplicated().sum(),
        'memory_mb': df.memory_usage(deep=True).sum() / (1024**2)
    }
```

**Estimativa**: 2-3 horas | **Complexidade**: Baixa

---

### 9. Dry-run Integrado

Adicionar modo teste ao script principal:

```bash
python process_zpp_to_mongo.py --dry-run
```

**Estimativa**: 2-3 horas | **Complexidade**: Baixa

---

## 📈 Impacto Estimado

| Prioridade | Esforço Total | Impacto |
|------------|---------------|---------|
| 🔴 Alta | 4-6 horas | ⭐⭐⭐⭐⭐ |
| 🟡 Média | 8-12 horas | ⭐⭐⭐⭐ |
| 🟢 Baixa | 8-12 horas | ⭐⭐⭐ |

---

**Data da Revisão**: 2026-01-28
**Revisado por**: Claude Code (Análise de Código)
**Nota Atual**: 8.5/10 → **Meta**: 9.5/10 (após Alta Prioridade)
