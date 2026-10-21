// webapp/src/assets/fa_photos_upload.js
//
// Upload das fotos da Análise de Falhas (SDD analise-falhas-fotos, DS-08 / Bloco D).
//
// O botão "Adicionar fotos" cria um <input type=file> na hora (o Dash não tem input
// nativo de arquivo). Cada imagem é COMPRIMIDA no navegador (canvas → maior lado
// ~1920px, JPEG q=0,8) antes de subir — foto de celular de 8 MB vira ~500 KB, aliviando
// rede e file server. Sobe via fetch multipart para a rota Flask; ao terminar, bumpa
// `store-fa-fotos-refresh` para o Dash recarregar a grade do Mongo.

(function () {
  var MAX_LADO = 1920;
  var _bump = 0;

  function alerta(msg, tipo) {
    var box = document.getElementById("fa-fotos-alerta");
    if (!box) { return; }
    box.innerHTML = msg
      ? '<div class="alert alert-' + (tipo || "danger") + ' py-1 px-2 mb-0 small">' + msg + "</div>"
      : "";
  }

  function carregarImagem(file) {
    return new Promise(function (res, rej) {
      var url = URL.createObjectURL(file);
      var im = new Image();
      im.onload = function () { URL.revokeObjectURL(url); res(im); };
      im.onerror = function () {
        URL.revokeObjectURL(url);
        rej(new Error("Formato não suportado neste navegador (ex.: HEIC do iPhone)."));
      };
      im.src = url;
    });
  }

  function comprimir(file) {
    return carregarImagem(file).then(function (im) {
      var w = im.naturalWidth, h = im.naturalHeight;
      var escala = Math.min(1, MAX_LADO / Math.max(w, h));
      w = Math.round(w * escala); h = Math.round(h * escala);
      var canvas = document.createElement("canvas");
      canvas.width = w; canvas.height = h;
      canvas.getContext("2d").drawImage(im, 0, 0, w, h);
      return new Promise(function (res, rej) {
        canvas.toBlob(function (b) {
          b ? res(b) : rej(new Error("Falha ao processar a imagem."));
        }, "image/jpeg", 0.8);
      });
    });
  }

  function enviar(aid, file) {
    return comprimir(file).then(function (blob) {
      var fd = new FormData();
      fd.append("file", blob, "foto.jpg");
      return fetch("/api/failure-analysis/" + aid + "/photos", {
        method: "POST", body: fd, credentials: "same-origin",
      }).then(function (resp) {
        if (resp.ok) { return; }
        return resp.json().catch(function () { return {}; }).then(function (j) {
          throw new Error(j.erro || ("Erro " + resp.status));
        });
      });
    });
  }

  function refresca() {
    if (window.dash_clientside && window.dash_clientside.set_props) {
      _bump += 1;
      window.dash_clientside.set_props("store-fa-fotos-refresh", { data: _bump });
    }
  }

  function processar(files) {
    var aidEl = document.getElementById("fa-fotos-aid");
    var aid = aidEl ? aidEl.textContent.trim() : "";
    if (!aid || !files.length) { return; }
    alerta("Enviando " + files.length + " foto(s)…", "info");
    var erros = [];
    var seq = Promise.resolve();
    files.forEach(function (f) {
      seq = seq.then(function () {
        return enviar(aid, f).catch(function (e) { erros.push(f.name + ": " + e.message); });
      });
    });
    seq.then(function () {
      refresca();
      alerta(erros.length ? erros.join("<br>") : "", erros.length ? "warning" : "");
    });
  }

  function podeEditar() {
    var area = document.getElementById("fa-fotos-upload-area");
    return area && getComputedStyle(area).display !== "none";
  }

  // Miniatura que falhou ao carregar (ex.: file server fora — BR-09) vira um
  // placeholder de imagem quebrada, sem derrubar a grade. `error` não borbulha,
  // então escuta na fase de captura.
  document.addEventListener("error", function (ev) {
    var t = ev.target;
    if (t && t.classList && t.classList.contains("fa-foto-thumb") &&
        !t.classList.contains("fa-foto-quebrada")) {
      var ph = document.createElement("div");
      ph.className = "fa-foto-thumb fa-foto-quebrada";
      ph.innerHTML = '<i class="bi bi-image-alt"></i>';
      if (t.parentNode) { t.parentNode.replaceChild(ph, t); }
    }
  }, true);

  // Delegação no document (a página é SPA; não precisa reanexar).
  document.addEventListener("click", function (ev) {
    // Adicionar fotos
    var btn = ev.target.closest && ev.target.closest("#fa-fotos-btn");
    if (btn) {
      ev.preventDefault();
      var inp = document.createElement("input");
      inp.type = "file";
      inp.accept = "image/jpeg,image/png,image/webp";
      inp.multiple = true;
      inp.style.display = "none";
      // O input precisa estar no DOM para o seletor de arquivo abrir de forma
      // confiável (input solto é instável em alguns navegadores/headless).
      document.body.appendChild(inp);
      inp.onchange = function () {
        processar(Array.prototype.slice.call(inp.files));
        inp.remove();
      };
      inp.click();
      return;
    }
    // Excluir foto (o botão só é renderizado para autor/nível 3)
    var del = ev.target.closest && ev.target.closest(".fa-foto-del");
    if (del) {
      ev.preventDefault();
      ev.stopPropagation();
      var aid = del.getAttribute("data-aid"), fid = del.getAttribute("data-id");
      if (!aid || !fid) { return; }
      if (!window.confirm("Excluir esta foto? A ação não pode ser desfeita.")) { return; }
      fetch("/api/failure-analysis/" + aid + "/photos/" + fid,
        { method: "DELETE", credentials: "same-origin" })
        .then(function (r) {
          if (r.ok) { refresca(); }
          else { r.json().catch(function () { return {}; }).then(function (j) { alerta(j.erro || ("Erro " + r.status)); }); }
        });
      return;
    }
    // Editar legenda (clique na legenda; só quando se pode editar)
    var leg = ev.target.closest && ev.target.closest(".fa-foto-legenda");
    if (leg && podeEditar()) {
      var card = leg.closest(".fa-foto-card");
      var img = card && card.querySelector(".fa-foto-thumb");
      if (!img) { return; }
      var nova = window.prompt("Legenda da foto:", leg.textContent || "");
      if (nova === null) { return; }
      fetch("/api/failure-analysis/" + img.getAttribute("data-aid") + "/photos/" + img.getAttribute("data-id"),
        { method: "PATCH", headers: { "Content-Type": "application/json" },
          credentials: "same-origin", body: JSON.stringify({ legenda: nova }) })
        .then(function (r) { if (r.ok) { refresca(); } else { alerta("Erro ao salvar a legenda."); } });
    }
  });
})();
