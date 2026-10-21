"""
Testes de completude dos três idiomas da página Análise de Falhas.

Por que existe: a página tem português, espanhol e inglês, e o texto que ficar de fora
de um dicionário **não quebra nada** — ele simplesmente aparece em português para quem
trocou o idioma. Nenhum outro teste percebe isso, e olhar a tela em espanhol a cada
alteração não é realista.

Estes testes falham no lugar certo: na hora de escrever a chave nova.
"""

import pytest

from src.pages.maintenance.analise_de_falhas import TRANS

IDIOMAS = ("pt", "es", "en")


class TestCompletudeDosIdiomas:

    def test_os_tres_idiomas_existem(self):
        assert set(TRANS) == set(IDIOMAS)

    @pytest.mark.parametrize("idioma", ("es", "en"))
    def test_nenhuma_chave_do_portugues_falta_nos_outros(self, idioma):
        faltando = sorted(set(TRANS["pt"]) - set(TRANS[idioma]))
        assert not faltando, (
            f"{len(faltando)} chave(s) sem tradução em '{idioma}': {faltando}. "
            "Texto sem tradução aparece em português na tela traduzida.")

    @pytest.mark.parametrize("idioma", ("es", "en"))
    def test_nenhuma_chave_sobrando_nos_outros(self, idioma):
        # Sobra costuma ser chave renomeada em português e esquecida aqui — some da
        # tela sem ninguém notar.
        sobrando = sorted(set(TRANS[idioma]) - set(TRANS["pt"]))
        assert not sobrando, f"chave(s) em '{idioma}' que não existem em 'pt': {sobrando}"

    @pytest.mark.parametrize("idioma", IDIOMAS)
    def test_nenhum_texto_vazio(self, idioma):
        vazias = sorted(k for k, v in TRANS[idioma].items()
                        if isinstance(v, str) and not v.strip())
        assert not vazias, f"texto vazio em '{idioma}': {vazias}"

    def test_placeholder_de_numero_igual_nos_tres(self):
        # "{n} dias" precisa do mesmo marcador nos três; sem ele, o número some da
        # frase traduzida em vez de dar erro.
        com_marcador = {k for k, v in TRANS["pt"].items()
                        if isinstance(v, str) and "{n}" in v}
        for idioma in ("es", "en"):
            sem = sorted(k for k in com_marcador if "{n}" not in TRANS[idioma].get(k, ""))
            assert not sem, f"'{idioma}' perdeu o marcador {{n}} em: {sem}"

    def test_aba_nova_traduzida_nos_tres(self):
        for idioma in IDIOMAS:
            assert TRANS[idioma].get("tab_gestao"), f"aba sem nome em '{idioma}'"


class TestTextosLigadosAoTrocadorDeIdioma:
    """O outro esquecimento possível: a chave existe nos três idiomas, mas o texto na
    tela **não está ligado** ao trocador — e continua em português para sempre.

    Aconteceu no bloco B: as traduções estavam completas, o teste de completude
    passava, e a aba seguia em português ao trocar o idioma. Comparar dicionários não
    basta; é preciso comparar o layout com a lista de saídas do callback.
    """

    def _ids_do_layout(self):
        from src.pages.maintenance.analise_de_falhas import layout

        achados, pilha = set(), [layout()]
        while pilha:
            no = pilha.pop()
            if isinstance(no, (list, tuple)):
                pilha.extend(no)
                continue
            cid = getattr(no, "id", None)
            if isinstance(cid, str) and cid.startswith("af-i18n-"):
                achados.add(cid)
            filhos = getattr(no, "children", None)
            if filhos is not None:
                pilha.append(filhos if isinstance(filhos, (list, tuple)) else [filhos])
        return achados

    def test_todo_span_de_traducao_do_layout_esta_na_lista_de_saidas(self):
        from src.callbacks_registers.analise_falhas_callbacks import I18N_OUTPUTS

        ligados = {i for i, _ in I18N_OUTPUTS}
        soltos = sorted(self._ids_do_layout() - ligados)
        assert not soltos, (
            f"{len(soltos)} texto(s) no layout sem ligação com o trocador de idioma: "
            f"{soltos}. Eles ficam em português mesmo com a página traduzida.")

    def test_toda_saida_aponta_para_chave_que_existe(self):
        from src.callbacks_registers.analise_falhas_callbacks import I18N_OUTPUTS
        from src.pages.maintenance.analise_de_falhas import TRANS

        orfas = sorted(k for _, k in I18N_OUTPUTS if k not in TRANS["pt"])
        assert not orfas, f"saída apontando para chave inexistente: {orfas}"
