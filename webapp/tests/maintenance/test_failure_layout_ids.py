"""Todo id usado em callback da Análise de Falhas existe no layout da página.

**Por que este teste existe.** No Dash, um `Input`/`State` que aponta para um id
inexistente não quebra o servidor: o navegador registra
`A nonexistent object was used in an Input` e o **ciclo inteiro de callbacks é
abortado**. O sintoma para quem usa é "a tela pisca 'Updating' e nada acontece" — e
nenhum teste de backend pega isso.

Foi exatamente o que aconteceu ao trocar o diagrama por Excalidraw na POC: os
controles de tempo foram removidos do layout e a marcação de causa raiz parou de
funcionar, sem erro nenhum no servidor. Daí a regra: componente que é entrada de
callback vivo **some da vista, mas continua no DOM**.

**Limitação assumida:** a varredura é do código-fonte (ids literais), não do layout
renderizado — o que cobre a classe de defeito (alguém apaga o componente e esquece o
callback) sem precisar subir o app inteiro com banco.
"""
import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"

# Arquivos que DESENHAM tela (onde os ids nascem). São varridos todos porque um
# callback da Análise de Falhas também fala com componentes de fora da página — o
# `url` do roteador, por exemplo, mora no index.
def _arquivos_de_layout() -> list[Path]:
    arquivos = sorted((_SRC / "pages").rglob("*.py"))
    pasta_componentes = _SRC / "components"
    if pasta_componentes.is_dir():
        arquivos += sorted(pasta_componentes.rglob("*.py"))
    for solto in ("index.py", "header.py", "sidebar.py"):
        caminho = _SRC / solto
        if caminho.is_file():
            arquivos.append(caminho)
    return arquivos


_LAYOUTS = _arquivos_de_layout()
# Arquivos que REAGEM a esses ids.
_CALLBACKS = [
    _SRC / "callbacks_registers/failure_analysis_callbacks.py",
    _SRC / "callbacks_registers/failure_a3_callbacks.py",
    _SRC / "callbacks_registers/failure_photos_callbacks.py",
]


def _ids_do_layout() -> set[str]:
    """Ids que a tela DEFINE (e não os que ela referencia).

    Duas fontes, tratadas de modo diferente de propósito:

    * **Arquivos de layout** — toda string literal conta. Metade dos ids do projeto é
      passada como argumento de helper (`_resumo_item(..., "fa-parada-equip")`), então
      procurar só por `id="..."` deixaria buracos.
    * **Arquivos de callback** — conta **apenas** o que aparece como `id=` na criação
      de um componente (parte da tela nasce dentro de callback, como a tabela de
      paradas). Recolher toda string daqui invalidaria o teste: o id referenciado num
      `Input` está escrito nesse mesmo arquivo, e tudo passaria sempre.
    """
    achados: set[str] = set()

    for arquivo in _LAYOUTS:
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # arquivo de rascunho não derruba o teste
            continue
        for no in ast.walk(arvore):
            if isinstance(no, ast.Constant) and isinstance(no.value, str):
                achados.add(no.value)

    for arquivo in _CALLBACKS:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            for kw in no.keywords:
                if kw.arg == "id" and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    achados.add(kw.value.value)
    return achados


def _ids_usados_em_callbacks() -> dict[str, list[str]]:
    """Ids literais passados a Input/State/Output, com o arquivo onde aparecem."""
    usados: dict[str, list[str]] = {}
    for arquivo in _CALLBACKS:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Name):
                continue
            if no.func.id not in {"Input", "State", "Output"} or not no.args:
                continue
            primeiro = no.args[0]
            if isinstance(primeiro, ast.Constant) and isinstance(primeiro.value, str):
                usados.setdefault(primeiro.value, []).append(arquivo.name)
    return usados


class TestIdsDeCallback:
    def test_todo_id_de_callback_existe_no_layout(self):
        layout = _ids_do_layout()
        faltando = {
            id_: sorted(set(arqs))
            for id_, arqs in _ids_usados_em_callbacks().items()
            if id_ not in layout
        }
        assert not faltando, (
            "Ids usados em callback que não existem no layout — o dash-renderer aborta "
            "o ciclo inteiro quando isso acontece:\n"
            + "\n".join(f"  {i} (usado em {', '.join(a)})" for i, a in sorted(faltando.items()))
        )

    @pytest.mark.parametrize("id_", [
        # O diagrama antigo continua no DOM, oculto, porque estes são entrada de
        # callbacks vivos. Se alguém apagar algum, este teste cai junto.
        "fa-diagrama", "fa-switch-tempos", "fa-btn-reset-tempos",
        "fa-tb-irma", "fa-tb-ramif", "fa-tb-editar", "fa-tb-raiz", "fa-tb-tempo",
        "fa-tb-excluir", "fa-tb-explicativo", "fa-tb-promover", "fa-tb-rebaixar",
        "fa-inline-text", "fa-inline-ok", "fa-tempo-input", "fa-tempo-ok", "fa-tempo-auto",
    ])
    def test_diagrama_antigo_segue_no_layout(self, id_):
        assert id_ in _ids_do_layout(), (
            f"{id_} sumiu do layout. Ele é entrada de callback — esconder é permitido, "
            "remover só depois de tirar os callbacks correspondentes."
        )

    def test_diagrama_antigo_esta_oculto(self):
        """Oculto de verdade: o bloco tem o contêiner com display:none."""
        texto = (_SRC / "pages/maintenance/failure_analysis.py").read_text(encoding="utf-8")
        assert 'id="fa-diagrama-legado"' in texto
        trecho = texto.split('id="fa-diagrama-legado"')[1][:120]
        assert '"display": "none"' in trecho

    def test_canvas_novo_no_layout(self):
        layout = _ids_do_layout()
        for id_ in ("fa-frame", "fa-btn-causa-raiz", "fa-causa-raiz-dica", "fa-ponte-sink"):
            assert id_ in layout, f"{id_} deveria estar no layout do diagrama novo"
