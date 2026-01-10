"""
Script de teste para verificar o sistema de badges de demonstração

Execute este script para testar rapidamente se o sistema de badges
está funcionando corretamente.

Uso:
    python test_demo_badges.py
"""

def test_imports():
    """Testa se todas as importações funcionam"""
    print("🔍 Testando importações...")

    try:
        from src.components.demo_badge import demo_data_badge, demo_data_tooltip_badge, with_demo_badge
        print("  ✅ demo_badge.py - OK")
    except Exception as e:
        print(f"  ❌ demo_badge.py - ERRO: {e}")
        return False

    try:
        from src.config.demo_data_config import (
            ENABLE_DEMO_BADGES,
            DEMO_PAGES,
            should_show_demo_badge,
            get_demo_pages
        )
        print("  ✅ demo_data_config.py - OK")
    except Exception as e:
        print(f"  ❌ demo_data_config.py - ERRO: {e}")
        return False

    try:
        from src.utils.demo_helpers import (
            add_demo_badge_to_card_header,
            create_demo_card,
            add_demo_badge_to_graph,
            create_demo_graph_card,
            add_page_demo_warning
        )
        print("  ✅ demo_helpers.py - OK")
    except Exception as e:
        print(f"  ❌ demo_helpers.py - ERRO: {e}")
        return False

    return True


def test_configuration():
    """Testa se a configuração está correta"""
    print("\n⚙️  Testando configuração...")

    try:
        from src.config.demo_data_config import (
            ENABLE_DEMO_BADGES,
            DEMO_PAGES,
            should_show_demo_badge,
            get_demo_pages
        )

        print(f"  📊 ENABLE_DEMO_BADGES: {ENABLE_DEMO_BADGES}")
        print(f"  📊 Total de páginas configuradas: {len(DEMO_PAGES)}")

        # Listar páginas ativas
        active_pages = get_demo_pages()
        print(f"  📊 Páginas com badges ativos: {len(active_pages)}")

        if active_pages:
            print("  📋 Primeiras 5 páginas ativas:")
            for page in active_pages[:5]:
                print(f"     - {page}")

        # Testar função should_show_demo_badge
        test_page = "/production/oee"
        should_show = should_show_demo_badge(page_path=test_page)
        print(f"  🧪 Teste should_show_demo_badge('{test_page}'): {should_show}")

        return True

    except Exception as e:
        print(f"  ❌ ERRO na configuração: {e}")
        return False


def test_badge_components():
    """Testa se os componentes de badge são criados corretamente"""
    print("\n🎨 Testando componentes de badge...")

    try:
        from src.components.demo_badge import demo_data_badge, demo_data_tooltip_badge

        # Testar badge simples
        badge_sm = demo_data_badge(size="sm")
        badge_md = demo_data_badge(size="md")
        badge_lg = demo_data_badge(size="lg")
        print("  ✅ Badge simples (sm, md, lg) - OK")

        # Testar badge com tooltip
        tooltip_badge = demo_data_tooltip_badge(
            tooltip_id="test-tooltip",
            tooltip_text="Teste"
        )
        print("  ✅ Badge com tooltip - OK")

        return True

    except Exception as e:
        print(f"  ❌ ERRO nos componentes: {e}")
        return False


def test_helper_functions():
    """Testa se as funções helper funcionam"""
    print("\n🔧 Testando funções helper...")

    try:
        from dash import html, dcc
        import dash_bootstrap_components as dbc
        import plotly.graph_objects as go
        from src.utils.demo_helpers import (
            add_demo_badge_to_card_header,
            create_demo_card,
            create_demo_graph_card,
            add_page_demo_warning
        )

        # Testar add_demo_badge_to_card_header
        header = add_demo_badge_to_card_header(
            "Teste",
            page_path="/production/oee"
        )
        print("  ✅ add_demo_badge_to_card_header - OK")

        # Testar create_demo_card
        card = create_demo_card(
            title="Teste",
            content=html.Div("Conteúdo"),
            page_path="/production/oee"
        )
        print("  ✅ create_demo_card - OK")

        # Testar create_demo_graph_card
        fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[4, 5, 6])])
        graph_card = create_demo_graph_card(
            title="Teste",
            figure=fig,
            page_path="/energy/overview"
        )
        print("  ✅ create_demo_graph_card - OK")

        # Testar add_page_demo_warning
        warning = add_page_demo_warning("/production/oee")
        print("  ✅ add_page_demo_warning - OK")

        return True

    except Exception as e:
        print(f"  ❌ ERRO nas funções helper: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_css_file():
    """Verifica se o arquivo CSS existe"""
    print("\n🎨 Verificando arquivo CSS...")

    import os

    css_path = os.path.join("src", "assets", "demo_badge.css")

    if os.path.exists(css_path):
        print(f"  ✅ Arquivo CSS encontrado: {css_path}")
        return True
    else:
        print(f"  ❌ Arquivo CSS não encontrado: {css_path}")
        return False


def run_all_tests():
    """Executa todos os testes"""
    print("=" * 60)
    print("🧪 TESTE DO SISTEMA DE BADGES DE DEMONSTRAÇÃO")
    print("=" * 60)

    results = []

    results.append(("Importações", test_imports()))
    results.append(("Configuração", test_configuration()))
    results.append(("Componentes de Badge", test_badge_components()))
    results.append(("Funções Helper", test_helper_functions()))
    results.append(("Arquivo CSS", test_css_file()))

    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)

    all_passed = True
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"  {test_name}: {status}")
        if not result:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("\n✅ O sistema de badges está pronto para uso.")
        print("\n📚 Próximos passos:")
        print("  1. Leia DEMO_BADGES_README.md para início rápido")
        print("  2. Consulte DEMO_BADGES_GUIDE.md para exemplos detalhados")
        print("  3. Veja DEMO_BADGES_EXAMPLE.py para código de exemplo")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM")
        print("\nVerifique os erros acima e corrija os problemas.")

    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
