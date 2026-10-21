# src/callbacks_registers/vendor_routes.py
"""Rotas estáticas das bibliotecas vendorizadas grandes (`src/vendor/`).

Por que não em `assets/`: o Dash varre a pasta de assets e injeta **todo** `.js` e
`.css` que encontra em **todas** as páginas do sistema. O bundle do Excalidraw tem
mais de cem arquivos (o código é dividido em pedaços carregados sob demanda) — em
`assets/` eles virariam uma centena de `<script>` em cada tela, inclusive nas que
não têm diagrama nenhum.

Servindo por rota própria, o navegador baixa só o que a página do diagrama pedir, e
o carregamento das demais telas não muda em nada.
"""
from pathlib import Path

from flask import abort, send_from_directory

# src/callbacks_registers/vendor_routes.py -> src/vendor
_RAIZ = Path(__file__).resolve().parent.parent / "vendor"

# Um ano de cache: o nome dos arquivos do bundle carrega o hash do conteúdo, então
# uma versão nova nunca reaproveita o cache da anterior.
_MAX_AGE = 31_536_000


def register_vendor_routes(server):
    """Registra `/vendor/<biblioteca>/<arquivo>` no servidor Flask."""

    @server.route("/vendor/<path:caminho>")
    def vendor_estatico(caminho):
        destino = (_RAIZ / caminho).resolve()
        # Proteção de caminho: nada fora de src/vendor é servido, mesmo com "..".
        if not str(destino).startswith(str(_RAIZ)) or not destino.is_file():
            abort(404)
        return send_from_directory(_RAIZ, caminho, max_age=_MAX_AGE)
