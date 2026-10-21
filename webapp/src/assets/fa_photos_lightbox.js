// webapp/src/assets/fa_photos_lightbox.js
//
// Lightbox das fotos da Análise de Falhas (SDD analise-falhas-fotos) + manipulação:
// zoom (roda), PAN (arrastar quando ampliado), GIRAR ↺ ↻ (view) e SALVAR a rotação
// (persiste no arquivo via rota Flask). JS puro, sem lib (CSP offline).

(function () {
  var E = { imgs: [], idx: 0, zoom: 1, rot: 0, px: 0, py: 0,
            drag: false, x0: 0, y0: 0, p0x: 0, p0y: 0 };
  var _bump = 0;

  function overlay() { return document.getElementById("fa-fotos-lightbox"); }
  function img() { var o = overlay(); return o ? o.querySelector(".fa-lb-img") : null; }
  function podeEditar() {
    var a = document.getElementById("fa-fotos-upload-area");
    return a && getComputedStyle(a).display !== "none";
  }

  function coletar() {
    return Array.prototype.slice
      .call(document.querySelectorAll("#fa-fotos-grid img.fa-foto-thumb"))
      .map(function (i) {
        return { full: i.getAttribute("data-full"), legenda: i.getAttribute("data-legenda") || "",
                 id: i.getAttribute("data-id"), aid: i.getAttribute("data-aid") };
      });
  }

  function transformar() {
    var im = img();
    if (im) { im.style.transform = "translate(" + E.px + "px," + E.py + "px) scale(" + E.zoom + ") rotate(" + E.rot + "deg)"; }
    var btnSalvar = overlay() && overlay().querySelector('[data-lb="salvar"]');
    if (btnSalvar) { btnSalvar.style.display = (E.rot % 360 !== 0 && podeEditar()) ? "" : "none"; }
  }

  function render() {
    var o = overlay();
    if (!o) { return; }
    var cur = E.imgs[E.idx];
    if (!cur) { fechar(); return; }
    var nav = E.imgs.length > 1;
    o.innerHTML =
      '<button class="fa-lb-close" data-lb="close" title="Fechar">&times;</button>' +
      (nav ? '<button class="fa-lb-nav fa-lb-prev" data-lb="prev">&#8249;</button>' : "") +
      '<div class="fa-lb-stage"><img class="fa-lb-img" src="' + cur.full + '"></div>' +
      (nav ? '<button class="fa-lb-nav fa-lb-next" data-lb="next">&#8250;</button>' : "") +
      (cur.legenda ? '<div class="fa-lb-legenda">' + cur.legenda + "</div>" : "") +
      '<div class="fa-lb-toolbar">' +
      '  <button class="fa-lb-btn" data-lb="rot-esq" title="Girar à esquerda">&#8634;</button>' +
      '  <button class="fa-lb-btn" data-lb="rot-dir" title="Girar à direita">&#8635;</button>' +
      '  <button class="fa-lb-btn" data-lb="reset" title="Restaurar (1×, 0°)">&#10226; reset</button>' +
      '  <button class="fa-lb-btn fa-lb-salvar" data-lb="salvar" title="Salvar rotação" style="display:none">&#128190; salvar giro</button>' +
      "</div>";
    o.style.display = "flex";
    transformar();
  }

  function abrir(idx) {
    E.imgs = coletar();
    if (!E.imgs.length) { return; }
    E.idx = Math.max(0, Math.min(idx, E.imgs.length - 1));
    E.zoom = 1; E.rot = 0; E.px = 0; E.py = 0;
    render();
  }

  function fechar() { var o = overlay(); if (o) { o.style.display = "none"; o.innerHTML = ""; } }

  function nav(d) {
    if (!E.imgs.length) { return; }
    E.idx = (E.idx + d + E.imgs.length) % E.imgs.length;
    E.zoom = 1; E.rot = 0; E.px = 0; E.py = 0;
    render();
  }

  function girar(d) { E.rot = (E.rot + d) % 360; transformar(); }
  function reset() { E.zoom = 1; E.rot = 0; E.px = 0; E.py = 0; transformar(); }

  function salvar() {
    var cur = E.imgs[E.idx];
    var g = ((E.rot % 360) + 360) % 360;
    if (!cur || !g) { return; }
    fetch("/api/failure-analysis/" + cur.aid + "/photos/" + cur.id + "/rotate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      credentials: "same-origin", body: JSON.stringify({ graus: g }),
    }).then(function (r) {
      if (!r.ok) { alert("Não foi possível salvar a rotação."); return; }
      // arquivo já girado no servidor → zera a rotação de view e recarrega a imagem
      E.rot = 0; E.zoom = 1; E.px = 0; E.py = 0;
      var im = img();
      if (im) { im.src = cur.full.split("?")[0] + "?t=" + Date.now(); }
      transformar();
      // atualiza a grade (thumb girada) via refresh do Dash
      if (window.dash_clientside && window.dash_clientside.set_props) {
        _bump += 1;
        window.dash_clientside.set_props("store-fa-fotos-refresh", { data: _bump });
      }
    });
  }

  document.addEventListener("click", function (ev) {
    var thumb = ev.target.closest && ev.target.closest("#fa-fotos-grid img.fa-foto-thumb");
    if (thumb) {
      var imgs = coletar(), alvo = thumb.getAttribute("data-full"), idx = 0;
      for (var k = 0; k < imgs.length; k++) { if (imgs[k].full === alvo) { idx = k; break; } }
      abrir(idx);
      return;
    }
    var act = ev.target.closest && ev.target.closest("[data-lb]");
    if (act) {
      var a = act.getAttribute("data-lb");
      if (a === "close") { fechar(); }
      else if (a === "prev") { nav(-1); }
      else if (a === "next") { nav(1); }
      else if (a === "rot-esq") { girar(-90); }
      else if (a === "rot-dir") { girar(90); }
      else if (a === "reset") { reset(); }
      else if (a === "salvar") { salvar(); }
      return;
    }
    if (ev.target.id === "fa-fotos-lightbox") { fechar(); }
  });

  document.addEventListener("keydown", function (ev) {
    var o = overlay();
    if (!o || o.style.display === "none") { return; }
    if (ev.key === "Escape") { fechar(); }
    else if (ev.key === "ArrowLeft") { nav(-1); }
    else if (ev.key === "ArrowRight") { nav(1); }
  });

  document.addEventListener("wheel", function (ev) {
    var o = overlay();
    if (!o || o.style.display === "none") { return; }
    ev.preventDefault();
    E.zoom = Math.min(5, Math.max(1, E.zoom + (ev.deltaY < 0 ? 0.2 : -0.2)));
    if (E.zoom <= 1) { E.px = 0; E.py = 0; }  // ao voltar a 1×, recentraliza
    transformar();
  }, { passive: false });

  // PAN — arrastar a imagem (útil quando ampliada/girada, some as bordas do recorte).
  document.addEventListener("mousedown", function (ev) {
    var st = ev.target.closest && ev.target.closest(".fa-lb-stage");
    if (!st) { return; }
    ev.preventDefault();
    E.drag = true; E.x0 = ev.clientX; E.y0 = ev.clientY; E.p0x = E.px; E.p0y = E.py;
  });
  document.addEventListener("mousemove", function (ev) {
    if (!E.drag) { return; }
    E.px = E.p0x + (ev.clientX - E.x0);
    E.py = E.p0y + (ev.clientY - E.y0);
    transformar();
  });
  document.addEventListener("mouseup", function () { E.drag = false; });
})();
