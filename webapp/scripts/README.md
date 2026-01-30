# Scripts de Manutenção - AMG_Data

## Visão Geral

Esta pasta contém scripts utilitários para manutenção da aplicação AMG_Data, incluindo gerenciamento de recursos offline.

## Scripts Disponíveis

### download_offline_resources.py

**Propósito**: Baixa recursos externos (Bootstrap themes e Font Awesome) e os armazena localmente para permitir operação offline completa.

**Uso**:
```bash
cd webapp
python scripts/download_offline_resources.py
```

**O que faz**:
1. Baixa 2 temas Bootstrap (Minty e Darkly) do Bootswatch 5.3.6
2. Baixa Font Awesome 5.10.2 (CSS + 3 webfonts)
3. **Ajusta automaticamente** URLs dentro do CSS do Font Awesome para caminhos relativos locais
4. Cria estrutura de diretórios em `src/assets/vendor/`

**Recursos baixados** (~670 KB total):
- `assets/vendor/bootstrap/minty/bootstrap.min.css` (229 KB)
- `assets/vendor/bootstrap/darkly/bootstrap.min.css` (227 KB)
- `assets/vendor/fontawesome/css/all.min.css` (55 KB)
- `assets/vendor/fontawesome/webfonts/fa-brands-400.woff2` (73 KB)
- `assets/vendor/fontawesome/webfonts/fa-regular-400.woff2` (13 KB)
- `assets/vendor/fontawesome/webfonts/fa-solid-900.woff2` (74 KB)

**Quando usar**:
- Primeira configuração da aplicação
- Atualização de versões de Bootstrap ou Font Awesome
- Reinstalação após limpeza do repositório

---

### validate_offline.py

**Propósito**: Valida que a aplicação está completamente configurada para modo offline, sem dependências de CDNs externos.

**Uso**:
```bash
cd webapp
python scripts/validate_offline.py
```

**O que verifica**:
1. **Recursos Locais**: Confirma que todos os 6 arquivos foram baixados
2. **URLs Externas**: Escaneia código em busca de referências a CDNs (Font Awesome, jsDelivr)
3. **Configuração App**: Verifica `app.py` para caminhos locais
4. **Configuração Temas**: Verifica `theme_config.py` para temas locais

**Saída esperada**:
```
[OK] Recursos Locais
[OK] Urls Externas
[OK] Configuracao App
[OK] Configuracao Theme

>>> SUCESSO! Aplicacao configurada para modo offline completo.
```

**Quando usar**:
- Após executar `download_offline_resources.py`
- Após modificar `app.py` ou `theme_config.py`
- Antes de fazer deploy da aplicação
- Para troubleshooting de problemas de carregamento

---

## Fluxo de Trabalho Típico

### Configuração Inicial para Modo Offline

```bash
# 1. Baixar recursos
python scripts/download_offline_resources.py

# 2. Validar configuração
python scripts/validate_offline.py

# 3. Testar aplicação
cd src
python run.py
```

### Atualização de Versões

Para atualizar Bootstrap ou Font Awesome para versões mais recentes:

1. **Editar** `scripts/download_offline_resources.py`:
   ```python
   RESOURCES = {
       'bootstrap_minty': {
           'url': 'https://cdn.jsdelivr.net/npm/bootswatch@5.4.0/dist/minty/bootstrap.min.css',  # Nova versão
           ...
       }
   }
   ```

2. **Executar download**:
   ```bash
   python scripts/download_offline_resources.py
   ```

3. **Validar**:
   ```bash
   python scripts/validate_offline.py
   ```

4. **Testar aplicação** para garantir compatibilidade

---

## Troubleshooting

### Erro: "UnicodeEncodeError" ao executar scripts

**Causa**: Console do Windows não está configurado para UTF-8.

**Solução**: Os scripts já usam caracteres ASCII seguros. Se o erro persistir, execute:
```bash
chcp 65001  # Muda codificação para UTF-8
python scripts/download_offline_resources.py
```

### Erro: "RequestException" ao baixar recursos

**Causa**: Sem conexão com internet ou CDN indisponível.

**Solução**:
1. Verificar conexão com internet
2. Testar acesso manual aos CDNs:
   - https://cdn.jsdelivr.net
   - https://use.fontawesome.com
3. Verificar firewall/proxy corporativo

### Validação falha: "Referências externas encontradas"

**Causa**: Código ainda possui URLs de CDNs.

**Solução**:
1. Revisar arquivos listados pelo script
2. Substituir URLs CDN por caminhos locais:
   - `dbc.themes.MINTY` → `'/assets/vendor/bootstrap/minty/bootstrap.min.css'`
   - `https://use.fontawesome.com/...` → `'/assets/vendor/fontawesome/css/all.min.css'`
3. Executar validação novamente

### Arquivos faltando após download

**Causa**: Download foi interrompido ou falhou.

**Solução**:
1. Executar `download_offline_resources.py` novamente (é idempotente)
2. Verificar logs para identificar qual recurso falhou
3. Verificar permissões de escrita em `webapp/src/assets/`

---

## Dependências

Ambos os scripts requerem:
- **Python 3.8+**
- **requests** (para download)
- **pathlib** (incluído no Python padrão)
- **re** (incluído no Python padrão)

Instalar dependências:
```bash
pip install requests
```

---

## Notas Técnicas

### Ajuste de URLs no CSS

O script `download_offline_resources.py` usa regex para modificar o CSS do Font Awesome:

**Original** (CDN):
```css
@font-face {
  src: url(https://use.fontawesome.com/releases/v5.10.2/webfonts/fa-solid-900.woff2);
}
```

**Modificado** (local):
```css
@font-face {
  src: url(../webfonts/fa-solid-900.woff2);
}
```

Isso é **crítico** para que as webfonts carreguem corretamente, pois a estrutura de diretórios é:
```
assets/vendor/fontawesome/
├── css/all.min.css          # Referencia ../webfonts/
└── webfonts/
    └── fa-solid-900.woff2   # Acessível via caminho relativo
```

### Idempotência

Ambos os scripts podem ser executados múltiplas vezes sem efeitos colaterais:
- `download_offline_resources.py` sobrescreve arquivos existentes
- `validate_offline.py` apenas lê, nunca modifica

---

## Manutenção dos Scripts

### Adicionar novo recurso para download

Editar `download_offline_resources.py`:

```python
RESOURCES = {
    # ... recursos existentes ...
    'novo_recurso': {
        'url': 'https://cdn.example.com/resource.css',
        'path': 'assets/vendor/example/resource.css'
    }
}
```

### Adicionar nova validação

Editar `validate_offline.py`:

```python
def check_novo_recurso():
    """Verifica novo recurso."""
    # Implementar verificação
    return True

# Adicionar ao main():
results = {
    # ... checks existentes ...
    'novo_recurso': check_novo_recurso(),
}
```

---

## Histórico de Versões

- **v1.0** (2026-01-30): Versão inicial
  - Download de Bootstrap 5.3.6 (Minty/Darkly)
  - Download de Font Awesome 5.10.2
  - Validação completa de modo offline
