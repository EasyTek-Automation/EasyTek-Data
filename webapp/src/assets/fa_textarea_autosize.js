// webapp/src/assets/fa_textarea_autosize.js
//
// Altura dos campos de texto do A3 (Análise de Falhas). Duas coisas ao mesmo tempo:
//
//   1. CRESCER COM O TEXTO — ao abrir a análise e enquanto se digita, a caixa fica
//      do tamanho do conteúdo. Sem isso, um relato de 8 linhas volta espremido em
//      2 linhas toda vez que a página remonta.
//   2. RESPEITAR O ARRASTE — se alguém puxa a alça do canto para deixar a caixa
//      maior que o texto, essa altura vira um piso: a caixa nunca encolhe abaixo
//      dela e continua crescendo se o texto passar disso. A altura arrastada é
//      escrita no store `store-fa-alturas`, o Salvar persiste em `secoes.alturas`
//      e o load a restaura — como fica dentro da análise, vale para TODOS os
//      usuários que abrirem aquela análise.
//
// Substitui o antigo `fa_licoes_resize.js`, que fazia só o item 2 e só para o campo
// "Lições aprendidas".
//
// Distinguir "o usuário arrastou" de "nós ajustamos ao texto": o ResizeObserver
// dispara nos dois casos. Guardamos em `__faAplicada` a altura que nós mesmos
// acabamos de escrever; quando o observer relata algo diferente disso, foi arraste.

(function () {
  // Campos fixos das seções 1, 2 e 5. Os do Plano de Ação (seção 4) são
  // pattern-matching ids do Dash (JSON no atributo id) e entram pelo seletor de
  // sufixo abaixo.
  var IDS_FIXOS = [
    "fa-sec-prob-descricao",
    "fa-sec-prob-obs",
    "fa-sec-cont-acoes",
    "fa-sec-licoes",
  ];
  var SELETOR_ACAO = 'textarea[id*="fa-acao-desc"]';

  var DEBOUNCE_MS = 250;
  var TOLERANCIA_PX = 2;        // ruído de subpixel do layout não conta como arraste
  var JANELA_ARRASTE_MS = 3000; // mudou de tamanho logo após um clique no campo = arraste
  var ALTURA_MIN = 24;
  var ALTURA_MAX = 2000;

  function agora() {
    return new Date().getTime();
  }

  var pendentes = {};      // { chave: px } ainda não escritas no store
  var timer = null;

  /** Chave da altura no mapa salvo. Campo fixo → o próprio id; linha do Plano de
   *  Ação → `acao:<aid>`, porque o id do Dash é um JSON que muda de formatação. */
  function chaveDe(ta) {
    var id = ta.id || "";
    if (id.indexOf("fa-acao-desc") === -1) {
      return id;
    }
    try {
      var aid = JSON.parse(id).aid;
      return aid ? "acao:" + aid : null;
    } catch (e) {
      return null;
    }
  }

  function agenda(chave, px) {
    pendentes[chave] = px;
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(function () {
      timer = null;
      var envio = pendentes;
      pendentes = {};
      if (!window.dash_clientside || !window.dash_clientside.set_props) {
        return;
      }
      var atual = window.__faAlturas || {};
      var mescla = {};
      Object.keys(atual).forEach(function (k) { mescla[k] = atual[k]; });
      Object.keys(envio).forEach(function (k) { mescla[k] = envio[k]; });
      window.__faAlturas = mescla;
      window.dash_clientside.set_props("store-fa-alturas", { data: mescla });
    }, DEBOUNCE_MS);
  }

  function visivel(ta) {
    return !!ta.offsetParent;   // dentro de accordion fechado → mede tudo zero
  }

  /** Ponto ÚNICO por onde passa toda altura que apareceu sem termos sido nós.
   *
   *  São duas origens, e as duas querem dizer a mesma coisa — "o piso agora é X":
   *  o servidor restaurando a altura salva da análise, e o usuário arrastando a
   *  alça. A diferença está no que fazer depois: só o arraste vira altura salva.
   *  Distinguimos pelo clique — arrastar a alça começa por um `pointerdown` no
   *  campo; a restauração do servidor não tem clique nenhum.
   *
   *  Precisa ser um lugar só porque as duas origens chegam por caminhos
   *  diferentes (o `style` inline do Dash e o ResizeObserver) e em ordem não
   *  garantida: quem chegasse primeiro "consumia" a mudança e a outra via um
   *  valor já igual, sem fazer nada. */
  function adotaAltura(ta, px) {
    if (!px || px < ALTURA_MIN || px > ALTURA_MAX) {
      return;
    }
    if (Math.abs(px - (ta.__faAplicada || 0)) < TOLERANCIA_PX) {
      return;   // já é o que temos — nada mudou por fora
    }
    ta.__faPiso = px;
    ta.__faAplicada = px;
    if (agora() - (ta.__faPonteiro || 0) <= JANELA_ARRASTE_MS) {
      var chave = chaveDe(ta);
      if (chave) {
        agenda(chave, px);   // arraste do usuário → vira altura salva da análise
      }
    }
  }

  /** Lê a altura que o servidor escreveu no `style` inline (restauração da altura
   *  salva). O callback do Dash pode chegar DEPOIS do primeiro ajuste — sem isto,
   *  o ajuste encolhia a caixa de volta ao tamanho do texto e desfazia o salvo. */
  function sincronizaPiso(ta) {
    adotaAltura(ta, parseInt(ta.style.height, 10));
  }

  /** Ajusta a caixa ao texto, sem descer abaixo do piso arrastado nem do tamanho
   *  original do campo (o `rows=2` das seções, os 38px do Plano de Ação). */
  function ajusta(ta) {
    if (!visivel(ta)) {
      return;   // medir escondido dá 0 e esmagaria o campo ao reaparecer
    }
    sincronizaPiso(ta);
    // `auto` antes de ler `scrollHeight`: senão o valor fica preso na altura atual
    // e a caixa só sabe crescer, nunca encolher ao apagar texto.
    var anterior = ta.style.height;
    ta.style.height = "auto";
    var conteudo = ta.scrollHeight;
    ta.style.height = anterior;

    var alvo = Math.max(conteudo, ta.__faPiso || 0, ta.__faNatural || 0, ALTURA_MIN);
    alvo = Math.min(alvo, ALTURA_MAX);
    ta.__faValorAjustado = ta.value;
    if (Math.abs(alvo - Math.round(ta.getBoundingClientRect().height)) < 1) {
      ta.__faAplicada = alvo;
      return;
    }
    ta.__faAplicada = alvo;
    ta.style.height = alvo + "px";
  }

  function anexa(ta) {
    if (!ta || ta.__faAutosizeWired) {
      return;
    }
    ta.__faAutosizeWired = true;

    // A altura inline que já veio do servidor (callback de restauração) é a altura
    // salva — vira o piso. Pode ainda não ter chegado: o callback do Dash às vezes
    // roda DEPOIS deste anexo, e aí quem captura é o ResizeObserver abaixo.
    var inline = parseInt(ta.style.height, 10);
    ta.__faPiso = isNaN(inline) ? 0 : inline;
    // Tamanho original do campo, para nunca entregar uma caixa menor do que a que
    // já estava no ar (premissa de preservação da UI).
    ta.__faNatural = visivel(ta) ? Math.round(ta.getBoundingClientRect().height) : 0;
    ajusta(ta);

    ta.addEventListener("input", function () { ajusta(ta); });
    // Arrastar a alça começa por um clique DENTRO do campo. Sem esta marca, uma
    // mudança de altura vinda do servidor (restauração) seria confundida com
    // escolha do usuário e regravada no store como se ele tivesse arrastado.
    ta.addEventListener("pointerdown", function () { ta.__faPonteiro = agora(); });

    var ro = new ResizeObserver(function () {
      if (ta.__faTimer) {
        clearTimeout(ta.__faTimer);
      }
      ta.__faTimer = setTimeout(function () {
        // Mede o elemento em vez de ler o `style`: o arraste da alça mexe no
        // tamanho de fato, e nem todo navegador escreve isso no style inline.
        adotaAltura(ta, Math.round(ta.getBoundingClientRect().height));
      }, DEBOUNCE_MS);
    });
    ro.observe(ta);
  }

  /** Reajusta quem mudou por fora: o Dash preenche o campo escrevendo `.value`
   *  direto, e escrever `.value` por código **não** dispara o evento `input`. Sem
   *  esta revisita, abrir uma análise com um relato de 8 linhas mostrava a caixa
   *  ainda em 2 linhas — que é justamente o "texto espremido" reclamado.
   *
   *  Também cobre o campo que só fica visível depois (seção do accordion fechada
   *  no load): enquanto escondido não dá para medir nada. */
  function revisita(ta) {
    if (!ta || !ta.__faAutosizeWired || !visivel(ta)) {
      return;
    }
    if (!ta.__faNatural) {
      ta.__faNatural = Math.round(ta.getBoundingClientRect().height);
    }
    sincronizaPiso(ta);
    if (ta.value !== ta.__faValorAjustado) {
      ajusta(ta);
    }
  }

  function varre() {
    IDS_FIXOS.forEach(function (id) {
      var ta = document.getElementById(id);
      anexa(ta);
      revisita(ta);
    });
    var acoes = document.querySelectorAll(SELETOR_ACAO);
    for (var i = 0; i < acoes.length; i++) {
      anexa(acoes[i]);
      revisita(acoes[i]);
    }
  }

  // SPA: os campos aparecem/somem conforme a navegação, e as linhas do Plano de
  // Ação são recriadas quando se marca/desmarca uma causa raiz. `anexa` é
  // idempotente (sai cedo se já ligado), então varrer de tempos em tempos basta.
  document.addEventListener("DOMContentLoaded", varre);
  setInterval(varre, 800);
})();
