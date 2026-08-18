(function () {
  "use strict";

  const camarerosApiBase = (window.CAMAREROS_API_URL || "http://localhost:8080").replace(/\/+$/, "");

  const qr = new URLSearchParams(window.location.search).get("qr");
  const path = window.location.pathname.replace(/^\/+/, "").replace(/\/+$/, "");
  const segments = path.split("/");

  const output = document.getElementById("output");

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function render(icono, titulo, detalle) {
    output.innerHTML =
      '<div class="icon">' + icono + "</div>" +
      '<p class="status">' + titulo + "</p>" +
      '<p class="detail">' + detalle + "</p>";
  }

  function fila(etiqueta, valor) {
    return (
      '<div class="field"><span class="field-label">' + etiqueta + "</span>" +
      '<span class="field-value">' + esc(valor) + "</span></div>"
    );
  }

  function renderCredencial(ficha) {
    document.title = (ficha.nombre || "Profesional") + " — Personal Hostel";
    output.className = "output ok";

    const foto = ficha.foto_url
      ? '<img class="avatar" src="' + esc(camarerosApiBase + ficha.foto_url) + '" alt="Foto de ' + esc(ficha.nombre) + '" />'
      : '<div class="avatar avatar-empty">' + esc((ficha.nombre || "?").charAt(0).toUpperCase()) + "</div>";

    const nick = ficha.nick ? '<p class="nick">@' + esc(ficha.nick) + "</p>" : "";

    const campos = [];
    if (ficha.email) campos.push(fila("Email", ficha.email));
    if (ficha.telefono) campos.push(fila("Teléfono", ficha.telefono));
    if (ficha.direccion) campos.push(fila("Dirección", ficha.direccion));
    if (ficha.ciudad) campos.push(fila("Ciudad", ficha.ciudad));
    const contacto = campos.length
      ? '<div class="contacto">' + campos.join("") + "</div>"
      : "";

    output.innerHTML =
      '<p class="brand">Personal Hostel — Credencial profesional</p>' +
      foto +
      '<p class="status">' + esc(ficha.nombre) + " " + esc(ficha.apellidos || "") + "</p>" +
      nick +
      contacto +
      '<p class="edit-hint">¿Es tu cuenta? Edítala en tu app (Personal Comander).</p>';
  }

  function errorPublico(status, code) {
    if (code === "identity.qr_invalido" || status === 422) {
      render("⚠️", "QR no válido",
        "Este código no es un QR de profesional válido. Comprueba que el enlace está completo.");
    } else if (code === "identity.credencial_inactiva" || status === 409) {
      render("🚫", "Credencial no activa",
        "La clave de este QR ha sido revocada o renovada. Pide al profesional su QR actualizado.");
    } else {
      render("⚠️", "No se ha podido cargar la ficha",
        "Ocurrió un error. Inténtalo de nuevo más tarde.");
    }
  }

  if (!(segments.length === 1 && segments[0] === "camareros") || !qr) {
    render("⚠️", "Enlace inválido",
      "Esta dirección no corresponde a la ficha pública de un profesional de Personal Hostel.");
    return;
  }

  fetch(camarerosApiBase + "/v1/camareros/ficha?qr=" + encodeURIComponent(qr), {
    headers: { "Accept": "application/json" },
  })
    .then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        return { status: res.status, body: body };
      });
    })
    .then(function (out) {
      if (out.status === 200) {
        renderCredencial(out.body);
      } else {
        errorPublico(out.status, (out.body && out.body.code) || "");
      }
    })
    .catch(function () {
      render("🔌", "Sin conexión",
        "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.");
    });
})();