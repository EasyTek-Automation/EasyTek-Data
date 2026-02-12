# ⚠️ Diretório Descontinuado

**Status**: DEPRECATED - Não usar

Este diretório era usado pelos scripts antigos de processamento ZPP que foram **descontinuados**.

---

## 🚫 Não Use Este Diretório

Os arquivos colocados aqui **NÃO SERÃO PROCESSADOS** automaticamente.

---

## ✅ Novo Local Correto

**Coloque os arquivos ZPP em**:
```
AMG_Infra/volumes/zpp/input/
```

**Caminho completo**:
```
E:\Projetos Python\AMG_Infra\volumes\zpp\input\
```

---

## 📋 Migração

### Passos para Migrar

1. **Mover arquivos pendentes**:
   ```bash
   mv E:/Projetos\ Python/AMG_Data/zpp_input/*.xlsx \
      E:/Projetos\ Python/AMG_Infra/volumes/zpp/input/
   ```

2. **Processar via interface web**:
   ```
   http://localhost:8050/maintenance/zpp-processor
   ```

3. **Ou aguardar processamento automático** (se configurado)

---

## 🗑️ Limpeza

Este diretório será **removido em 60 dias** (2026-04-12).

**Ação recomendada**:
- Mover arquivos pendentes para o novo local
- Deletar este diretório manualmente se estiver vazio

---

## 📚 Documentação

- **Serviço novo**: `../zpp-processor/README.md`
- **Scripts antigos**: `../deprecated/README.md`
- **Interface web**: `/maintenance/zpp-processor`

---

**Última atualização**: 2026-02-12
