/* hh-management — drag-and-drop do quadro semanal (HTML5 nativo, offline, sem lib).
 *
 * Arrasta um card de ordem (.hh-card[draggable=true], data-hh-ordem) para um slot
 * técnico×dia (.hh-slot, data-hh-tecnico/data-hh-dia). No drop, grava o evento no store
 * Dash `hh-drop-event` via window.dash_clientside.set_props — o callback server persiste
 * a atribuição (hh_planejamento). A semana corrente vem do #hh-semana-dom (clientside cb).
 *
 * Delegação no document → sobrevive ao re-render do quadro (não precisa re-bind).
 */
(function () {
  "use strict";

  var dragOrdem = null;
  var dragDisc = null;   // disciplina da ordem arrastada

  function _classificada(d) { return d === "Mecanica" || d === "Eletrica"; }

  // Um slot ACEITA a ordem se: mesma disciplina, OU Terceiros (coringa B15), OU disciplina cruzada
  // (ambas classificadas Mec/Elé — B33: vira aviso confirmável no servidor, não bloqueio).
  // NaoClassificado (ordem sem disciplina) nunca dropa (BR-07: reclassificar no SAP).
  function _aceita(slotDisc) {
    if (dragDisc === "Terceiros") { return true; }
    if (slotDisc === dragDisc) { return true; }
    return _classificada(dragDisc) && _classificada(slotDisc);   // cruzada Mec↔Elé
  }
  // True se é cruzada (aceita, mas com aviso visual amarelo — disciplinas diferentes classificadas).
  function _cruzada(slotDisc) {
    return _classificada(dragDisc) && _classificada(slotDisc) && slotDisc !== dragDisc;
  }

  function semanaCorrente() {
    var el = document.getElementById("hh-semana-dom");
    return el ? (el.textContent || "").trim() : "";
  }

  // colapsar/expandir 100% client-side (sem round-trip / re-render do board).
  // Clique no cabeçalho (data-hh-collapse-key) → esconde/mostra o corpo (data-hh-collapse-body),
  // vira o chevron, e persiste o estado no store hh-collapsed (sessionStorage via set_props).
  document.addEventListener("click", function (ev) {
    var head = ev.target.closest && ev.target.closest("[data-hh-collapse-key]");
    if (!head) { return; }
    var key = head.getAttribute("data-hh-collapse-key");
    var body = document.querySelector('[data-hh-collapse-body="' + key + '"]');
    if (!body) { return; }
    var colap = body.style.display !== "none";   // estava aberto → vai recolher
    body.style.display = colap ? "none" : "";
    var chev = head.querySelector(".hh-chev");
    if (chev) {
      chev.classList.toggle("bi-chevron-down", !colap);
      chev.classList.toggle("bi-chevron-right", colap);
    }
    // reconstrói o dict {key: recolhido} a partir do DOM e persiste
    var estado = {};
    document.querySelectorAll("[data-hh-collapse-body]").forEach(function (b) {
      estado[b.getAttribute("data-hh-collapse-body")] = (b.style.display === "none");
    });
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props("hh-collapsed", { data: estado });
    }
  });

  // clique simples num card → abre detalhe (set_props no store hh-card-click).
  // Ignora clique no botão remover (×) e cliques logo após um arraste (< 300ms).
  var lastDragEnd = 0;
  document.addEventListener("click", function (ev) {
    if (ev.target.closest && ev.target.closest(".hh-card-rm")) { return; }  // × tem seu callback
    if (ev.target.closest && ev.target.closest(".hh-card-split")) { return; }  // ✂ tem seu callback
    var card = ev.target.closest && ev.target.closest(".hh-card");
    if (!card) { return; }
    if (Date.now() - lastDragEnd < 300) { return; }   // foi arraste, não clique
    var ordem = card.getAttribute("data-hh-ordem");
    if (!ordem) { return; }
    if (!(window.dash_clientside && window.dash_clientside.set_props)) { return; }
    window.dash_clientside.set_props("hh-card-click", { data: { ordem: ordem, ts: Date.now() } });
  });

  // botão direito num slot → abre o modal de associação (busca a ordem e atribui ao slot).
  document.addEventListener("contextmenu", function (ev) {
    var slot = ev.target.closest && ev.target.closest(".hh-slot[data-hh-tecnico]");
    if (!slot) { return; }
    ev.preventDefault();   // suprime o menu nativo do navegador
    if (!(window.dash_clientside && window.dash_clientside.set_props)) { return; }
    window.dash_clientside.set_props("hh-slot-context", { data: {
      tecnico: slot.getAttribute("data-hh-tecnico"),
      dia: parseInt(slot.getAttribute("data-hh-dia"), 10),
      disc: slot.getAttribute("data-hh-disc"),
      semana: semanaCorrente(),
      ts: Date.now()
    }});
  });

  document.addEventListener("dragstart", function (ev) {
    var card = ev.target.closest && ev.target.closest(".hh-card[draggable='true']");
    if (!card) { return; }
    dragOrdem = card.getAttribute("data-hh-ordem");
    dragDisc = card.getAttribute("data-hh-disc");
    try { ev.dataTransfer.setData("text/plain", dragOrdem); } catch (e) {}
    ev.dataTransfer.effectAllowed = "move";
    card.classList.add("hh-dragging-card");
    // acende só as dropzones da MESMA disciplina (classe no body marca a disciplina arrastada)
    document.body.classList.add("hh-dragging", "hh-drag-" + (dragDisc || "x"));
  });

  function _fimArraste(ev) {
    var card = ev.target.closest && ev.target.closest(".hh-card");
    if (card) { card.classList.remove("hh-dragging-card"); }
    document.body.classList.remove("hh-dragging", "hh-drag-Mecanica", "hh-drag-Eletrica",
                                   "hh-drag-Terceiros", "hh-drag-NaoClassificado", "hh-drag-x");
    lastDragEnd = Date.now();          // suprime o clique-fantasma pós-arraste
    dragOrdem = null; dragDisc = null;
  }
  document.addEventListener("dragend", _fimArraste);

  document.addEventListener("dragover", function (ev) {
    var slot = ev.target.closest && ev.target.closest(".hh-slot");
    if (!slot) { return; }
    var slotDisc = slot.getAttribute("data-hh-disc");
    if (_aceita(slotDisc)) {
      ev.preventDefault();               // habilita o drop
      ev.dataTransfer.dropEffect = "move";
      // cruzada Mec↔Elé: destaque AMARELO (aceita com aviso); demais: destaque normal
      slot.classList.add(_cruzada(slotDisc) ? "hh-slot-cross" : "hh-slot-over");
    } else {
      // NaoClassificado: NÃO habilita o drop (cursor no-drop) + marca visual de bloqueio
      ev.dataTransfer.dropEffect = "none";
      slot.classList.add("hh-slot-block");
    }
  });

  document.addEventListener("dragleave", function (ev) {
    var slot = ev.target.closest && ev.target.closest(".hh-slot");
    if (slot) { slot.classList.remove("hh-slot-over", "hh-slot-cross", "hh-slot-block"); }
  });

  document.addEventListener("drop", function (ev) {
    var slot = ev.target.closest && ev.target.closest(".hh-slot");
    if (!slot) { return; }
    slot.classList.remove("hh-slot-over", "hh-slot-cross", "hh-slot-block");
    document.body.classList.remove("hh-dragging");
    lastDragEnd = Date.now();
    // dispara o evento se o slot aceita a ordem (mesma disciplina, Terceiros coringa, ou cruzada
    // Mec↔Elé — B33: o servidor confirma). NaoClassificado não aceita → volta pra fila.
    var slotDisc = slot.getAttribute("data-hh-disc");
    if (!_aceita(slotDisc)) { dragOrdem = null; dragDisc = null; return; }
    ev.preventDefault();
    var ordem = dragOrdem || (ev.dataTransfer && ev.dataTransfer.getData("text/plain"));
    if (!ordem) { return; }
    var tecnico = slot.getAttribute("data-hh-tecnico");
    var dia = slot.getAttribute("data-hh-dia");
    if (!tecnico || dia === null) { return; }
    if (!(window.dash_clientside && window.dash_clientside.set_props)) { return; }
    window.dash_clientside.set_props("hh-drop-event", {
      data: {
        ordem: ordem,
        funcionario_id: tecnico,
        dia: parseInt(dia, 10),
        disc: slotDisc,                  // quadro-destino (Terceiros precisa; Mec/Elé = a própria)
        semana: semanaCorrente(),
        ts: Date.now()
      }
    });
    dragOrdem = null; dragDisc = null;
  });
})();
