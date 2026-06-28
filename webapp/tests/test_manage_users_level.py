"""
Testes da validação de troca de nível na edição de usuário.

Cobre as regras server-side (defesa em profundidade) que espelham o create_user e os
dois edge cases aprovados: anti-lockout (ninguém altera o próprio nível) e não-admin
não mexe no nível de quem já é nível 3.
"""

import pytest

from src.callbacks_registers.manage_users_callbacks import (
    validate_level_change,
    level_options_for_admin,
)


ADMIN_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"
TARGET_ID = "bbbbbbbbbbbbbbbbbbbbbbbb"


def _target(level, _id=TARGET_ID, perfil="manutencao"):
    return {"_id": _id, "level": level, "perfil": perfil, "username": "alvo"}


# ============================================
# Admin (TI) pode tudo (menos mexer no próprio)
# ============================================

@pytest.mark.parametrize("new_level", [1, 2, 3])
def test_admin_pode_atribuir_qualquer_nivel(new_level):
    ok, err = validate_level_change("admin", ADMIN_ID, _target(1), new_level)
    assert ok is True
    assert err is None


def test_admin_pode_rebaixar_nivel_3_de_outro():
    ok, err = validate_level_change("admin", ADMIN_ID, _target(3), 1)
    assert ok is True


# ============================================
# Não-admin: regras espelhadas do create
# ============================================

def test_nao_admin_nao_promove_a_nivel_3():
    ok, err = validate_level_change("manutencao", ADMIN_ID, _target(1), 3)
    assert ok is False
    assert "nível 3" in err.lower() or "nivel 3" in err.lower()


def test_nao_admin_nao_altera_nivel_de_quem_ja_e_3():
    ok, err = validate_level_change("manutencao", ADMIN_ID, _target(3), 2)
    assert ok is False


def test_nao_admin_edita_usuario_comum_ok():
    ok, err = validate_level_change("manutencao", ADMIN_ID, _target(1), 2)
    assert ok is True
    assert err is None


# ============================================
# Edge case: anti-lockout (próprio nível)
# ============================================

def test_nao_pode_alterar_proprio_nivel():
    alvo = _target(3, _id=ADMIN_ID)  # editando a si mesmo
    ok, err = validate_level_change("admin", ADMIN_ID, alvo, 2)
    assert ok is False
    assert "próprio" in err.lower() or "proprio" in err.lower()


def test_proprio_nivel_sem_mudanca_passa():
    alvo = _target(3, _id=ADMIN_ID)
    ok, err = validate_level_change("admin", ADMIN_ID, alvo, 3)  # mesmo nível, no-op
    assert ok is True


# ============================================
# Nível inválido
# ============================================

@pytest.mark.parametrize("bad", [0, 4, 99, None, "x"])
def test_nivel_invalido_rejeitado(bad):
    ok, err = validate_level_change("admin", ADMIN_ID, _target(1), bad)
    assert ok is False


# ============================================
# Edge case: nível especial (gestor nível 4)
# ============================================

def test_admin_edita_gestor_nivel_4_sem_mudar_nivel_passa():
    # Regressão: editar nome/email de usuário nível 4 não pode ser bloqueado pelo nível
    alvo = _target(4)
    ok, err = validate_level_change("admin", ADMIN_ID, alvo, 4)  # no-op
    assert ok is True
    assert err is None


def test_admin_nao_rebaixa_gestor_nivel_4_por_esta_tela():
    alvo = _target(4)
    ok, err = validate_level_change("admin", ADMIN_ID, alvo, 2)
    assert ok is False
    assert "especial" in err.lower()


# ============================================
# Opções por perfil
# ============================================

def test_opcoes_admin_tem_3_niveis():
    opts = level_options_for_admin("admin")
    assert [o["value"] for o in opts] == [1, 2, 3]


def test_opcoes_nao_admin_tem_2_niveis():
    opts = level_options_for_admin("manutencao")
    assert [o["value"] for o in opts] == [1, 2]
