# ⚠️ DOCUMENTAÇÃO DESCONTINUADA

**Status**: DEPRECATED - Este guia está **desatualizado**

---

## 🔄 Sistema Migrado

O processamento de planilhas ZPP foi **completamente migrado** para um **serviço containerizado** com interface web.

Esta documentação antiga está mantida apenas para **referência histórica**.

---

## ✅ Nova Documentação

**Acesse a documentação atual**:
- **Serviço**: `../zpp-processor/README.md`
- **Interface Web**: http://localhost:8050/maintenance/zpp-processor
- **Scripts Antigos**: `../deprecated/README.md`
- **Testes**: `../zpp-processor/tests/README.md`

---

## 🚀 Como Usar o Novo Sistema

### Processamento Manual

**1. Colocar arquivos**:
```
Localização: AMG_Infra/volumes/zpp/input/
```

**2. Processar via interface web**:
```
URL: http://localhost:8050/maintenance/zpp-processor
Ação: Clicar em "Processar Agora"
```

**3. Arquivos processados vão para**:
```
Localização: AMG_Infra/volumes/zpp/output/
```

---

### Processamento Automático

**Configurar**:
```
1. Acessar: /maintenance/zpp-processor
2. Abrir painel "Configurações"
3. Ativar switch "Processamento Automático"
4. Definir intervalo (ex: 60 minutos)
5. Salvar
```

**Resultado**:
- Sistema processa automaticamente arquivos em `input/` no intervalo configurado
- Logs persistidos em MongoDB
- Histórico visível na interface web

---

## 📊 Comparação: Antigo vs Novo

| Aspecto | Sistema Antigo | Sistema Novo |
|---------|----------------|--------------|
| **Interface** | CLI apenas | Web + API REST |
| **Local dos arquivos** | `zpp_input/` (código) | `volumes/zpp/input/` (externo) |
| **Comando** | `python process_zpp_to_mongo.py` | Botão "Processar Agora" |
| **Agendamento** | Cron manual | Automático configurável |
| **Monitoramento** | Logs console | Dashboard web + histórico |
| **Arquivamento** | `analisados/` local | `volumes/zpp/output/` |
| **Deploy** | Python local | Container Docker |

---

## 🗑️ Scripts Descontinuados

Os seguintes scripts **NÃO DEVEM** mais ser usados:

- ❌ `process_zpp_quick.py`
- ❌ `process_zpp_to_mongo.py`
- ❌ `clean_zpp_data.py`
- ❌ `test_detect.py`

**Localização atual**: `../deprecated/`

**Motivo**: Migrados para o serviço `zpp-processor`

---

## 📚 Migração de Workflows

### Se você usava CLI:

**Antes**:
```bash
python process_zpp_to_mongo.py zpp_input/
```

**Agora**:
1. Mover arquivos para `AMG_Infra/volumes/zpp/input/`
2. Acessar interface web
3. Clicar em "Processar Agora"

---

### Se você usava Cron:

**Antes**:
```bash
# crontab -e
0 */1 * * * cd /path/AMG_Data && python process_zpp_to_mongo.py zpp_input/
```

**Agora**:
1. Remover entrada do cron
2. Configurar processamento automático via interface web
3. Sistema processa automaticamente

---

## 🆘 Suporte

**Dúvidas sobre migração?**

- Ler guia completo: `../deprecated/README.md`
- Documentação do serviço: `../zpp-processor/README.md`
- Testes: `../zpp-processor/tests/README.md`

---

**Última atualização**: 2026-02-12
**Versão**: 4.0 (serviço containerizado)
**Substituído por**: ZPP Processor Service
