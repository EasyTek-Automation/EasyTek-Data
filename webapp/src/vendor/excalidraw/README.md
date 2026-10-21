# Excalidraw vendorizado — 0.18.0

Bundle local usado pelo diagrama da Análise de Falhas
(`/maintenance/analise-de-falhas/ishikawa`). **A fábrica não tem internet**: servido de
CDN, o quadro de desenho abriria em branco.

| | |
|---|---|
| **Versão** | `@excalidraw/excalidraw` **0.18.0** + `react`/`react-dom` **18.2.0** |
| **Gerado em** | 2026-09-15; regerado em 2026-10-15 para expor `exportToSvg`/`exportToBlob` (imagem do diagrama no slide) |
| **Servido em** | `/vendor/excalidraw/…` (rota Flask `src/callbacks_registers/vendor_routes.py`) |
| **Quem usa** | `src/assets/fa_excalidraw.html` e `src/assets/fa_excalidraw_mount.js` |

## Por que não está em `assets/`

O Dash varre a pasta de assets e injeta **todo** `.js` e `.css` que encontra em **todas**
as páginas. O bundle tem mais de cem arquivos (o Excalidraw divide o código em pedaços
carregados sob demanda: idiomas, mermaid, katex). Em `assets/`, cada tela do sistema
carregaria uma centena de `<script>`. Pela rota própria, só a página do diagrama baixa o
que precisa.

## O que tem aqui

| Arquivo | O que é |
|---|---|
| `entry.js` | ponto de entrada; exporta `React`, `createRoot`, `Excalidraw`, `convertToExcalidrawElements`, `exportToSvg`, `exportToBlob` |
| `chunk-*.js`, `*-*.js` | pedaços carregados sob demanda (o navegador pede sozinho) |
| `index.css` | estilos do Excalidraw |
| `fonts/` | fontes do quadro |

**A família de fontes `Xiaolai` (chinês, 13 MB) foi deixada de fora** — sozinha, era mais
pesada que todo o resto somado. Texto em chinês cai na fonte do sistema.

## Como regerar (ou atualizar de versão)

Não há build de front no AMG: o resultado entra pronto no repositório, como os demais
vendors. Para refazer, com Docker:

```bash
mkdir -p /tmp/exbuild && cd /tmp/exbuild
cat > entry.mjs <<'JS'
import React from "react";
import { createRoot } from "react-dom/client";
export { Excalidraw, convertToExcalidrawElements, exportToSvg, exportToBlob } from "@excalidraw/excalidraw";
export { React, createRoot };
JS
echo '{ "name": "amg-excalidraw-vendor", "private": true, "type": "module" }' > package.json

docker run --rm -v "$PWD":/w -w /w node:20-alpine sh -c "\
  npm i --silent @excalidraw/excalidraw@0.18.0 react@18.2.0 react-dom@18.2.0 esbuild@0.25.0 && \
  npx esbuild entry.mjs --bundle --format=esm --splitting --outdir=dist --minify \
    --define:process.env.NODE_ENV='\"production\"'"

# copiar para cá: dist/*.js, node_modules/@excalidraw/excalidraw/dist/prod/index.css
# e as pastas de node_modules/@excalidraw/excalidraw/dist/prod/fonts/ EXCETO Xiaolai
```

**Depois de regerar, troque o `?v=` do import em `src/assets/fa_excalidraw.html`.** A rota
serve tudo com cache de 1 ano; os pedaços têm hash no nome, mas o `entry.js` não — sem
trocar o `v`, quem tem o `entry.js` antigo em cache pede pedaços que não existem mais e o
quadro abre em branco.

`--splitting` é o que mantém idiomas, mermaid e katex fora do carregamento inicial.
Sem ele, sai um único arquivo de 8,4 MB baixado sempre.

## Tamanhos (2026-09-15)

| | |
|---|---|
| Carregamento inicial | `entry.js` 716 KB (224 KB comprimido) + o pedaço principal 1,8 MB (727 KB comprimido) |
| Sob demanda | idiomas 1,7 MB · mermaid/elk ~2,3 MB · katex 264 KB |
| Fontes (sem Xiaolai) | ~510 KB |
| Total no repositório | ~8,8 MB |
