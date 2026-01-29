# 🚀 Processamento Unificado ZPP → MongoDB (v3.0)

Script único que unifica todo o fluxo de processamento de planilhas ZPP.

---

## 📍 **ONDE COLOCAR OS ARQUIVOS?**

### **Opção Recomendada: Pasta Dedicada**

**1. Coloque os arquivos aqui:**
```
E:\Projetos Python\AMG_Data\zpp_input\
```

**2. Execute:**
```bash
python process_zpp_to_mongo.py zpp_input
```

**3. Pronto! Os arquivos processados vão para:**
```
E:\Projetos Python\AMG_Data\analisados\
```

### **Opção Alternativa: Diretório Atual**

**1. Coloque os arquivos na raiz:**
```
E:\Projetos Python\AMG_Data\
```

**2. Execute:**
```bash
python process_zpp_to_mongo.py
```

💡 **Dica**: Use sempre a pasta `zpp_input/` para manter o projeto organizado!

---

## 📋 O Que Faz?

Este script realiza **5 operações em sequência**:

```
1. 🔍 Detecta tipo automaticamente (PRD ou Paradas)
2. 🧹 Limpa dados (remove linhas totalizadoras)
3. ☁️  Faz upload direto ao MongoDB
4. 📊 Cria índices otimizados
5. 📁 Move arquivo processado para "analisados/"
```

### ✨ Diferencial da v3.0

- ✅ **Sem arquivos intermediários** - Não gera `*_cleaned.xlsx`
- ✅ **Upload direto** ao MongoDB (economia de espaço em disco)
- ✅ **Arquivamento automático** - Organiza arquivos processados
- ✅ **Processo único** - Tudo em um só comando

---

## 🎯 Fluxo Visual

```
Diretório de entrada
├── Producao_Jan2025.xlsx       ─┐
└── Paradas_Jan2025.xlsx        ─┤
                                 │
                                 ├─→ Detectar tipo
                                 ├─→ Limpar dados
                                 ├─→ Upload MongoDB
                                 ├─→ Criar índices
                                 │
                                 ↓
Diretório de entrada/analisados/
├── Producao_Jan2025.xlsx       ✓ (arquivo movido)
└── Paradas_Jan2025.xlsx        ✓ (arquivo movido)

MongoDB: Cluster-EasyTek
├── ZPP_Producao_2025           ✓ (22.435 docs + 5 índices)
└── ZPP_Paradas_2025            ✓ (50.954 docs + 6 índices)
```

---

## 🚀 Como Usar

### 1. Teste Sem Upload (Recomendado Primeiro)

```bash
# Testa todo o fluxo SEM conectar ao MongoDB
# Move os arquivos para validar o processo
python test_process_zpp.py caminho/planilhas

# Testar sem mover arquivos
python test_process_zpp.py caminho/planilhas --no-archive
```

**Exemplo de saída:**
```
================================================================================
TESTE DE PROCESSAMENTO ZPP (DRY-RUN v3.0)
================================================================================

Total de arquivos processados: 2
Total de documentos a inserir: 73,389
Total de arquivos arquivados:  2

Arquivos movidos para subdiretório: test_process_zpp/analisados/
  - Paradas_Jan2025.xlsx
  - Producao_Jan2025.xlsx

TESTE CONCLUÍDO
(Nenhum dado foi inserido no MongoDB)
(Arquivos foram movidos para validar o fluxo)
```

### 2. Processamento Real com Upload

```bash
# Processar todos os arquivos Excel do diretório
python process_zpp_to_mongo.py caminho/planilhas

# Processar sem mover arquivos (mantém originais no lugar)
python process_zpp_to_mongo.py caminho/planilhas --no-archive

# Processar diretório atual
python process_zpp_to_mongo.py
```

---

## 📁 Estrutura de Arquivos

### Antes do Processamento

```
planilhas_zpp/
├── Producao_Dezembro.xlsx
├── Paradas_Dezembro.xlsx
├── dados_producao_2025.xlsx
└── relatorio_paradas.xlsx
```

### Depois do Processamento (com `--no-archive`)

```
planilhas_zpp/
├── Producao_Dezembro.xlsx      ← Permanece no lugar
├── Paradas_Dezembro.xlsx       ← Permanece no lugar
├── dados_producao_2025.xlsx    ← Permanece no lugar
└── relatorio_paradas.xlsx      ← Permanece no lugar
```

### Depois do Processamento (SEM `--no-archive`)

```
planilhas_zpp/
├── analisados/                 ← Subdiretório criado automaticamente
│   ├── Producao_Dezembro.xlsx  ← Arquivo movido
│   ├── Paradas_Dezembro.xlsx   ← Arquivo movido
│   ├── dados_producao_2025.xlsx  ← Arquivo movido
│   └── relatorio_paradas.xlsx    ← Arquivo movido
```

---

## ⚙️ Configuração

### Variáveis de Ambiente (`.env`)

```bash
MONGO_URI=mongodb://host.docker.internal:27017
DB_NAME=Cluster-EasyTek
```

O script lê automaticamente essas variáveis do arquivo `.env`.

---

## 📊 Collections Criadas no MongoDB

### Estrutura por Tipo e Ano

```javascript
// Database: Cluster-EasyTek

// Collection: ZPP_Producao_2025
{
  "Pto.Trab.": "LONGI001",
  "Kg.Proc.": 5060,
  "FIniNotif": ISODate("2025-01-09"),
  "Ordem": 9948143,
  "_uploaded_at": ISODate("2026-01-28"),
  "_source_file": "zppprd",
  "_source_filename": "Producao_Jan2025.xlsx",  // ← NOVO!
  "_year": 2025,
  "_processed": true
}

// Collection: ZPP_Paradas_2025
{
  "LINEA": "LONGI001",
  "Ordem": 10071271,
  "MOTIVO": "101N",
  "DURAÇÃO(min)": 136,
  "_uploaded_at": ISODate("2026-01-28"),
  "_source_file": "zppparadas",
  "_source_filename": "Paradas_Jan2025.xlsx",   // ← NOVO!
  "_year": 2025,
  "_processed": true
}
```

### Índices Criados Automaticamente

| Collection | Índices | Total |
|------------|---------|-------|
| `ZPP_Producao_YYYY` | equipamento_data, ordem_unique (UNIQUE), range_datas, year, equipamento_producao | 5 |
| `ZPP_Paradas_YYYY` | linha_data, ordem, motivo, range_datas, year, duracao | 6 |

---

## 🔄 Fluxo de Processamento Detalhado

```
┌─────────────────────────────────────────────────────────┐
│ 1. ENCONTRAR ARQUIVOS                                   │
│    ↓ Busca *.xlsx, *.xls                               │
│    ↓ Ignora: *_cleaned.xlsx, ~$*.xlsx                  │
├─────────────────────────────────────────────────────────┤
│ 2. PARA CADA ARQUIVO:                                   │
│                                                          │
│    A) Detectar Tipo                                     │
│       ↓ zppprd ou zppparadas                           │
│                                                          │
│    B) Limpar Dados                                      │
│       ↓ Remove linhas totalizadoras                    │
│       ↓ 3 critérios de identificação                   │
│                                                          │
│    C) Preparar para MongoDB                             │
│       ↓ Converte NaN/NaT para None                     │
│       ↓ Adiciona metadados (_uploaded_at, etc.)        │
│       ↓ Extrai ano dos dados                           │
│                                                          │
│    D) Upload ao MongoDB                                 │
│       ↓ Collection: ZPP_{Tipo}_{Ano}                   │
│       ↓ Lotes de 1000 documentos                       │
│       ↓ Trata duplicatas (índice único em Ordem)       │
│                                                          │
│    E) Criar/Atualizar Índices                           │
│       ↓ 5-6 índices por collection                      │
│       ↓ Verifica se já existem antes de criar          │
│                                                          │
│    F) Arquivar Arquivo (se --no-archive NÃO usado)     │
│       ↓ Cria subdiretório "analisados/"                │
│       ↓ Move arquivo original                          │
│       ↓ Se existir, adiciona timestamp ao nome         │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ 3. RESUMO FINAL                                         │
│    ↓ Estatísticas consolidadas                         │
│    ↓ Arquivos processados vs erros                     │
│    ↓ Total de documentos carregados                    │
└─────────────────────────────────────────────────────────┘
```

---

## 🎬 Exemplo Prático Completo

### Cenário: Processar Planilhas de Janeiro/2025

```bash
# 1. Organizar planilhas
mkdir planilhas_janeiro_2025
cp relatorio_producao.xlsx planilhas_janeiro_2025/
cp relatorio_paradas.xlsx planilhas_janeiro_2025/

# 2. Testar (sem MongoDB)
python test_process_zpp.py planilhas_janeiro_2025

# Saída:
# ✓ Tipo detectado automaticamente
# ✓ Dados limpos
# ✓ Arquivos movidos para analisados/
# ✓ 73.389 documentos prontos

# 3. Processar de verdade
python process_zpp_to_mongo.py planilhas_janeiro_2025

# Saída:
# ✓ Conectado ao MongoDB: Cluster-EasyTek
# ✓ Tipo detectado: zppprd
# ✓ 22.435 documentos inseridos
# ✓ Collection: ZPP_Producao_2025
# ✓ Arquivo movido para: analisados/relatorio_producao.xlsx
# ... (mesmo para paradas)

# 4. Verificar no MongoDB
mongosh mongodb://host.docker.internal:27017/Cluster-EasyTek
> db.ZPP_Producao_2025.countDocuments()
22435
> db.ZPP_Paradas_2025.countDocuments()
50954
```

### Estrutura Final

```
planilhas_janeiro_2025/
└── analisados/
    ├── relatorio_producao.xlsx
    └── relatorio_paradas.xlsx

MongoDB: Cluster-EasyTek
├── ZPP_Producao_2025 (22.435 docs)
└── ZPP_Paradas_2025 (50.954 docs)
```

---

## 🔒 Segurança e Tratamento de Erros

### Duplicatas

- Índice **ÚNICO** em `Ordem` (Produção)
- Tentativa de inserir ordem duplicada → **ignorada silenciosamente**
- Contador de `failed_rows` mostra quantas foram ignoradas

### Arquivos já Processados

Se um arquivo com mesmo nome já existe em `analisados/`:

```
Timestamp adicionado automaticamente:
  Producao_Jan2025.xlsx → Producao_Jan2025_20260128_153000.xlsx
```

### Erro Durante Upload

Se erro ocorrer durante o upload:
- ✅ Dados já inseridos permanecem no MongoDB
- ❌ Arquivo **NÃO é movido** para analisados
- ℹ️  Permite reprocessamento sem duplicar dados (índice único protege)

---

## 📝 Opções de Linha de Comando

| Argumento | Descrição | Exemplo |
|-----------|-----------|---------|
| `<diretorio>` | Diretório com planilhas | `python process_zpp_to_mongo.py ./planilhas` |
| `--no-archive` | Não move arquivos processados | `python process_zpp_to_mongo.py ./planilhas --no-archive` |
| `--no-move` | Alias para `--no-archive` | `python process_zpp_to_mongo.py ./planilhas --no-move` |
| *(vazio)* | Processa diretório atual | `python process_zpp_to_mongo.py` |

---

## 🆚 Comparação de Scripts

| Script | Função | Gera Arquivos? | Upload MongoDB? | Move Originais? |
|--------|--------|----------------|-----------------|-----------------|
| `clean_zpp_data.py` | Limpa dados | ✅ Sim (`*_cleaned.xlsx`) | ❌ Não | ❌ Não |
| `upload_zpp_to_mongo.py` | Limpa + Upload | ❌ Não | ✅ Sim | ❌ Não |
| **`process_zpp_to_mongo.py`** | **Limpa + Upload + Arquiva** | **❌ Não** | **✅ Sim** | **✅ Sim** |

### Quando Usar Cada Um?

- **`clean_zpp_data.py`**: Apenas limpar dados (sem MongoDB)
- **`upload_zpp_to_mongo.py`**: Upload sem mover arquivos
- **`process_zpp_to_mongo.py`** ⭐: **Fluxo completo e automatizado** (RECOMENDADO)

---

## 🐛 Troubleshooting

### Erro: "Erro ao conectar ao MongoDB"

**Causa**: MongoDB não acessível

**Solução**:
```bash
# 1. Testar conexão
mongosh mongodb://host.docker.internal:27017

# 2. Verificar se está rodando
docker ps | grep mongo

# 3. Usar teste sem MongoDB primeiro
python test_process_zpp.py ./planilhas
```

### Arquivos não foram movidos

**Causa**: Usou `--no-archive` ou erro durante upload

**Verificar**:
1. Logs mostram "Arquivado: Sim"?
2. Usou `--no-archive`?
3. Erro durante upload?

### Duplicatas ignoradas

**Causa**: Normal - já existem documentos com mesma `Ordem`

**Verificar**:
```javascript
// Ver quantas ordens já existem
db.ZPP_Producao_2025.countDocuments({ Ordem: 9948143 })

// Ver última data de upload
db.ZPP_Producao_2025.find().sort({ _uploaded_at: -1 }).limit(5)
```

---

## 💡 Dicas e Boas Práticas

### 1. Sempre Teste Primeiro

```bash
# Teste sem MongoDB (valida detecção e movimentação)
python test_process_zpp.py ./planilhas

# Se OK, processe de verdade
python process_zpp_to_mongo.py ./planilhas
```

### 2. Organize por Período

```bash
planilhas/
├── 2025_01_janeiro/
├── 2025_02_fevereiro/
└── 2025_03_marco/

# Processar mês por mês
python process_zpp_to_mongo.py planilhas/2025_01_janeiro/
```

### 3. Mantenha Backup dos Originais

```bash
# Antes de processar
cp -r planilhas/ planilhas_backup/

# Ou use --no-archive para não mover
python process_zpp_to_mongo.py planilhas/ --no-archive
```

### 4. Monitore o Subdiretório "analisados"

```bash
# Quantos arquivos já foram processados?
ls -l planilhas/analisados/ | wc -l

# Limpar arquivos antigos (se necessário)
find planilhas/analisados/ -name "*.xlsx" -mtime +90 -delete
```

---

## 📚 Arquivos Relacionados

- `process_zpp_to_mongo.py` - Script principal unificado ⭐
- `test_process_zpp.py` - Teste sem MongoDB
- `clean_zpp_data.py` - Módulo de limpeza (usado internamente)
- `README_ZPP_CLEANER.md` - Documentação da limpeza
- `README_UPLOAD_ZPP.md` - Documentação do upload

---

## 🎯 Resumo Executivo

### O que este script faz de diferente?

1. ✅ **Tudo em um só lugar** - Não precisa de múltiplos scripts
2. ✅ **Sem arquivos temporários** - Economia de espaço
3. ✅ **Organização automática** - Move arquivos processados
4. ✅ **Seguro** - Trata duplicatas, valida dados
5. ✅ **Testável** - Modo dry-run disponível

### Quando usar?

- ✅ Processamento regular de planilhas ZPP
- ✅ Carga inicial de dados históricos
- ✅ Automação de ETL
- ✅ Quando precisa organizar arquivos automaticamente

### Quando NÃO usar?

- ❌ Apenas quer limpar dados (use `clean_zpp_data.py`)
- ❌ Não quer mover os arquivos originais (use `upload_zpp_to_mongo.py`)
- ❌ MongoDB não está disponível (use `test_process_zpp.py`)

---

**Versão**: 3.0.0
**Data**: 2026-01-28
**Autor**: Claude Code

🚀 **Pronto para produção!**
