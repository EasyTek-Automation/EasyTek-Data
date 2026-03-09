# Dívida Técnica — Camada de Serviços

**Data:** 2026-03-09
**Prioridade:** ALTA ⚠️
**Impacto:** Testabilidade, manutenibilidade e separação de responsabilidades
**Módulo:** Transversal (manage_users, create_user, energy_config, energy_sidebar)
**Status:** Identificado — aguardando implementação

---

## Contexto

O projeto já tem um exemplo maduro de camada de serviços: `utils/workflow_db.py`.
Lógica de negócio isolada, sem Dash, sem UI — testável por isso (63 testes passando).

Os módulos de **gestão de usuários** e **energia** não seguem esse padrão.
Validações, regras RBAC, operações MongoDB e lógica de cálculo estão embutidas
diretamente dentro dos callbacks, tornando-os impossíveis de testar
sem simular cliques de botão e Dash rodando.

**Nota:** `utils/energy_cost_calculator.py` já existe e vai na direção certa —
as funções de cálculo estão separadas. O que falta é completar a separação
no callback de sidebar, que ainda mistura busca de dados com orquestração de UI.

---

## O Padrão Alvo

```
callbacks_registers/      ← orquestração de UI (Input → Output)
    ├── recebe evento (clique, intervalo)
    ├── chama service → recebe resultado
    └── transforma resultado em componente Dash

services/                 ← lógica de negócio (sem Dash, testável)
    ├── operações MongoDB
    ├── validações de domínio
    └── retorna dados simples (dict, tuple, bool)
```

Referência no projeto:
```python
# Como já funciona no workflow (padrão a seguir)
# workflow_subtask_callbacks.py
resultado = criar_subtarefa(pend_id, descricao, responsavel, horas, ...)
# callback apenas decide o que mostrar com base no resultado

# workflow_db.py
def criar_subtarefa(...):
    # só MongoDB + regras — sem html, sem dbc, sem Dash
```

---

## Serviços a Criar

### 1. `services/user_service.py` 🔴 Alta prioridade

**Problema atual:** A lógica de reset de senha, exclusão, edição e listagem de
usuários está fragmentada em callbacks individuais dentro de
`manage_users_callbacks.py` (591 linhas, 8 callbacks aninhados).
Cada callback importa `get_mongo_connection` diretamente, faz query,
verifica RBAC e monta resposta — tudo junto.

Exemplo do que está no callback hoje:
```python
# manage_users_callbacks.py — reset de senha (dentro do callback)
usuarios = get_mongo_connection("usuarios")
target_user = usuarios.find_one({"_id": ObjectId(user_id)})
if not target_user:
    return dbc.Alert("Usuário não encontrado", color="danger")  # ← UI misturada

blank_password_hash = generate_password_hash("", method='pbkdf2:sha256')
result = usuarios.update_one(
    {"_id": ObjectId(user_id)},
    {"$set": {"password": blank_password_hash, "password_set": False}}
)
if result.modified_count == 1:
    return dbc.Alert("Senha resetada", color="success")  # ← UI misturada
```

**Serviço proposto:** `webapp/src/services/user_service.py`

```python
# services/user_service.py

from bson import ObjectId
from werkzeug.security import generate_password_hash
from src.database.connection import get_mongo_connection
import logging

logger = logging.getLogger(__name__)


def buscar_usuario(user_id: str) -> dict | None:
    """Retorna documento do usuário ou None se não encontrado."""
    usuarios = get_mongo_connection("usuarios")
    if not usuarios:
        return None
    return usuarios.find_one({"_id": ObjectId(user_id)})


def listar_usuarios(filtro_perfil: str = None, search: str = None) -> list[dict]:
    """Retorna lista de usuários com filtros opcionais."""
    usuarios = get_mongo_connection("usuarios")
    if not usuarios:
        return []
    query = {}
    if filtro_perfil and filtro_perfil != "all":
        query["perfil"] = filtro_perfil
    if search:
        query["$or"] = [
            {"username": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    return list(usuarios.find(query))


def resetar_senha(user_id: str, admin_perfil: str) -> tuple[bool, str]:
    """
    Reseta senha do usuário para blank (forçar redefinição no login).

    Returns:
        (success, mensagem)
    """
    usuario = buscar_usuario(user_id)
    if not usuario:
        return False, "Usuário não encontrado."

    if admin_perfil != "admin" and usuario.get("perfil") != admin_perfil:
        logger.warning(f"[PERMISSION_DENIED] '{admin_perfil}' tentou resetar senha de '{usuario.get('username')}'")
        return False, "PERMISSÃO NEGADA: Você só pode resetar senhas do seu departamento."

    usuarios = get_mongo_connection("usuarios")
    blank_hash = generate_password_hash("", method='pbkdf2:sha256')
    result = usuarios.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password": blank_hash, "password_set": False}}
    )
    if result.modified_count == 1:
        logger.info(f"[PASSWORD_RESET] '{admin_perfil}' resetou senha de '{usuario.get('username')}'")
        return True, f"Senha de '{usuario.get('username')}' resetada com sucesso."

    return False, "Erro ao resetar senha."


def deletar_usuario(user_id: str, admin_perfil: str) -> tuple[bool, str]:
    """Deleta usuário. Retorna (success, mensagem)."""
    usuario = buscar_usuario(user_id)
    if not usuario:
        return False, "Usuário não encontrado."

    if admin_perfil != "admin" and usuario.get("perfil") != admin_perfil:
        return False, "PERMISSÃO NEGADA: Você só pode deletar usuários do seu departamento."

    usuarios = get_mongo_connection("usuarios")
    result = usuarios.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 1:
        logger.info(f"[USER_DELETED] '{admin_perfil}' deletou '{usuario.get('username')}'")
        return True, f"Usuário '{usuario.get('username')}' deletado com sucesso."

    return False, "Erro ao deletar usuário."


def editar_usuario(user_id: str, username: str, email: str) -> tuple[bool, str]:
    """Edita username e email do usuário. Retorna (success, mensagem)."""
    usuarios = get_mongo_connection("usuarios")
    if not usuarios:
        return False, "Sem conexão com banco de dados."

    result = usuarios.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"username": username, "email": email}}
    )
    if result.modified_count == 1:
        return True, f"Usuário atualizado com sucesso."

    return False, "Nenhuma alteração realizada."


def criar_usuario(username: str, email: str, password: str,
                  perfil: str, level: int) -> tuple[bool, str]:
    """
    Cria novo usuário no banco. Não faz validação — use user_validator antes.
    Retorna (success, mensagem).
    """
    from src.database.connection import save_user
    sucesso = save_user(username, email, password, level, perfil)
    if sucesso:
        logger.info(f"[USER_CREATED] username='{username}' perfil='{perfil}' level={level}")
        return True, f"Usuário '{username}' criado com sucesso."
    return False, "Erro ao criar usuário no banco de dados."
```

**Como fica o callback depois:**
```python
# manage_users_callbacks.py — após refatoração
def reset_user_password(n_clicks_list, admin_perfil, admin_level):
    ...
    success, mensagem = resetar_senha(user_id, admin_perfil)
    color = "success" if success else "danger"
    return dbc.Alert(mensagem, color=color, dismissable=True)
```

**Arquivos afetados:**
- Criar: `webapp/src/services/user_service.py`
- Refatorar: `webapp/src/callbacks_registers/manage_users_callbacks.py`
- Refatorar: `webapp/src/callbacks_registers/create_user_callbacks.py`

**Estimativa:** 4-6 horas | **Testabilidade:** Alta (sem Dash, mock MongoDB)

---

### 2. `validators/user_validator.py` 🔴 Alta prioridade

**Problema atual:** Validações de username, email, senha e regras RBAC estão
inline dentro de `create_new_user` (callback de 343 linhas). São regras de negócio
disfarçadas de código de UI.

```python
# create_user_callbacks.py — validações dentro do callback hoje
if not all([username, email, target_department, target_level]):
    return dbc.Alert("Todos os campos são obrigatórios", color="danger")

if password and len(password) < 8:
    return dbc.Alert("Senha deve ter no mínimo 8 caracteres", color="danger")

if "@" not in email or "." not in email:
    return dbc.Alert("Formato de e-mail inválido", color="danger")
```

**Validator proposto:** `webapp/src/validators/user_validator.py`

```python
# validators/user_validator.py

from src.database.connection import get_user_by_username, get_user_by_email


def validar_campos_obrigatorios(username, email, perfil, level) -> tuple[bool, str]:
    if not all([username, email, perfil, level]):
        return False, "Todos os campos são obrigatórios (senha pode ficar em branco)."
    return True, ""


def validar_email(email: str) -> tuple[bool, str]:
    if not email or "@" not in email or "." not in email:
        return False, "Formato de e-mail inválido."
    return True, ""


def validar_senha(password: str) -> tuple[bool, str]:
    if password and len(password) < 8:
        return False, "A senha deve ter no mínimo 8 caracteres."
    return True, ""


def validar_unicidade(username: str, email: str) -> tuple[bool, str]:
    if get_user_by_username(username):
        return False, f"O nome de usuário '{username}' já existe."
    if get_user_by_email(email):
        return False, f"O e-mail '{email}' já está em uso."
    return True, ""


def validar_rbac_criacao(target_level: int, target_perfil: str,
                          admin_perfil: str, admin_level: int) -> tuple[bool, str]:
    """Valida regras RBAC para criação de usuário."""
    if target_level == 3 and admin_perfil != "admin":
        return False, "Apenas administradores podem criar usuários Nível 3."
    if admin_perfil != "admin" and target_perfil != admin_perfil:
        return False, "Você só pode criar usuários do seu próprio departamento."
    return True, ""


def validar_novo_usuario(username, email, password, perfil, level,
                          admin_perfil, admin_level) -> tuple[bool, str]:
    """Executa todas as validações em sequência. Retorna (valid, primeiro_erro)."""
    checks = [
        validar_campos_obrigatorios(username, email, perfil, level),
        validar_email(email),
        validar_senha(password),
        validar_unicidade(username, email),
        validar_rbac_criacao(level, perfil, admin_perfil, admin_level),
    ]
    for valid, erro in checks:
        if not valid:
            return False, erro
    return True, ""
```

**Como fica o callback depois:**
```python
# create_user_callbacks.py — após refatoração
def create_new_user(n_clicks, username, email, password, perfil, level, admin_perfil, admin_level):
    valid, erro = validar_novo_usuario(username, email, password, perfil, level, admin_perfil, admin_level)
    if not valid:
        return dbc.Alert(erro, color="danger")

    success, mensagem = criar_usuario(username, email, password, perfil, level)
    return dbc.Alert(mensagem, color="success" if success else "danger")
```

**Arquivos afetados:**
- Criar: `webapp/src/validators/user_validator.py`
- Refatorar: `webapp/src/callbacks_registers/create_user_callbacks.py`

**Estimativa:** 2-3 horas | **Testabilidade:** Muito alta (funções puras, sem I/O)

---

### 3. `services/energy_config_service.py` 🟡 Média prioridade

**Problema atual:** `energy_config_callbacks.py` tem validação de 10 campos,
verificação de valores numéricos e persistência MongoDB dentro do callback `save_config`.

**Serviço proposto:** `webapp/src/services/energy_config_service.py`

```python
# services/energy_config_service.py

from src.database.connection import get_mongo_connection


def carregar_config() -> dict | None:
    """Carrega configuração de tarifas. Retorna dict ou None."""
    col = get_mongo_connection("AMG_EnergyConfig")
    if not col:
        return None
    return col.find_one()


def validar_config(config: dict) -> tuple[bool, list[str]]:
    """
    Valida os campos da configuração de tarifas.
    Retorna (valid, lista_de_erros).
    """
    campos_obrigatorios = [
        ("demanda_ponta", "Custo Demanda Ponta"),
        ("demanda_fora_ponta", "Custo Demanda Fora de Ponta"),
        ("demanda_contratada_ponta", "Demanda Contratada Ponta"),
        ("demanda_contratada_fora_ponta", "Demanda Contratada Fora de Ponta"),
        ("tusd_ponta", "TUSD Ponta"),
        ("tusd_fora_ponta", "TUSD Fora de Ponta"),
        ("energia_ponta", "Energia Ponta"),
        ("energia_fora_ponta", "Energia Fora de Ponta"),
        ("horario_inicio", "Horário Início"),
        ("horario_fim", "Horário Fim"),
    ]
    erros = []
    for campo, label in campos_obrigatorios:
        valor = config.get(campo)
        if valor is None or valor == "":
            erros.append(f"{label} é obrigatório.")
        elif campo not in ("horario_inicio", "horario_fim"):
            try:
                if float(valor) < 0:
                    erros.append(f"{label} não pode ser negativo.")
            except (TypeError, ValueError):
                erros.append(f"{label} deve ser um número válido.")

    return len(erros) == 0, erros


def salvar_config(config: dict) -> tuple[bool, str]:
    """
    Salva configuração de tarifas no MongoDB.
    Retorna (success, mensagem).
    """
    valid, erros = validar_config(config)
    if not valid:
        return False, "\n".join(erros)

    col = get_mongo_connection("AMG_EnergyConfig")
    if not col:
        return False, "Sem conexão com banco de dados."

    col.replace_one({}, config, upsert=True)
    return True, "Configuração salva com sucesso."
```

**Arquivos afetados:**
- Criar: `webapp/src/services/energy_config_service.py`
- Refatorar: `webapp/src/callbacks_registers/energy_config_callbacks.py`

**Estimativa:** 2-3 horas | **Testabilidade:** Alta

---

### 4. Completar separação em `energy_sidebar_callbacks.py` 🟡 Média prioridade

**O que já existe:** `utils/energy_cost_calculator.py` já tem as funções de cálculo
corretas (`calculate_costs_by_groups`, `format_brl`, etc.) e já é importado pelo callback.
O padrão está parcialmente aplicado.

**O que ainda falta:** O callback `calculate_se03_costs_by_groups` ainda contém
a lógica de busca de dados e processamento de timezone (Passos 2, 3, 4 e 5 do callback)
misturada com a orquestração de UI.

**Extrair para `utils/energy_cost_calculator.py`:**

```python
# Adicionar em utils/energy_cost_calculator.py

def buscar_dados_energia(start_date, end_date, start_hour, end_hour,
                          group1_equipment, group2_equipment) -> tuple:
    """
    Busca dados de energia no MongoDB e retorna DataFrames prontos para cálculo.
    Retorna (consumption_df, demand_df, config) ou (None, None, None) em erro.
    """
    from src.database.connection import get_mongo_connection
    import pytz
    from datetime import datetime, timedelta
    import pandas as pd

    config_col = get_mongo_connection("AMG_EnergyConfig")
    config = config_col.find_one() if config_col else None
    if not config:
        return None, None, None

    tz = pytz.timezone('America/Sao_Paulo')
    # ... lógica de conversão de timezone (extraída do callback)
    # ... lógica de query MongoDB (extraída do callback)
    # ... retorna DataFrames limpos

    return consumption_df, demand_df, config
```

**Como fica o callback depois:**
```python
# energy_sidebar_callbacks.py — após refatoração
def calculate_se03_costs_by_groups(active_tab, ...):
    if active_tab != "se03":
        raise PreventUpdate

    consumption_df, demand_df, config = buscar_dados_energia(
        start_date, end_date, start_hour, end_hour,
        group1_equipment, group2_equipment
    )
    if consumption_df is None:
        return ["---"] * 23

    resultado = calculate_costs_by_groups(consumption_df, demand_df, config,
                                          group1_equipment, group2_equipment)
    return _formatar_saida(resultado)  # ← só formatação de UI
```

**Arquivos afetados:**
- Atualizar: `webapp/src/utils/energy_cost_calculator.py`
- Refatorar: `webapp/src/callbacks_registers/energy_sidebar_callbacks.py`

**Estimativa:** 3-4 horas | **Testabilidade:** Alta

---

## Ordem de Execução Recomendada

| # | Serviço | Esforço | ROI | Fazer quando |
|---|---------|---------|-----|--------------|
| 1 | `validators/user_validator.py` | 2-3h | Muito alto | Primeiro — funções puras, sem risco |
| 2 | `services/user_service.py` | 4-6h | Alto | Logo após o validator |
| 3 | `services/energy_config_service.py` | 2-3h | Alto | Independente — pode ser paralelo |
| 4 | Completar `energy_cost_calculator.py` | 3-4h | Médio | Após os anteriores |

Cada item é independente e pode ser feito em qualquer ordem.
Recomenda-se começar pelo validator de usuário — é o mais simples,
sem I/O, resultado imediato e serve de modelo para os demais.

---

## Critérios de Sucesso

Após a refatoração, cada serviço deve ser testável assim:

```python
# Exemplo: test_user_validator.py
def test_email_invalido():
    valid, erro = validar_email("emailsemarroba")
    assert not valid
    assert "inválido" in erro

def test_senha_curta():
    valid, erro = validar_senha("abc")
    assert not valid

def test_rbac_nao_admin_criando_nivel3():
    valid, erro = validar_rbac_criacao(
        target_level=3, target_perfil="manutencao",
        admin_perfil="manutencao", admin_level=2
    )
    assert not valid
    assert "Nível 3" in erro
```

Sem Dash, sem MongoDB, sem mocks complexos.
