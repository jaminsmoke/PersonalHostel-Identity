(function () {
  "use strict";

  const apiBase = (window.IDENTITY_API_URL || "http://localhost:8080").replace(/\/+$/, "");
  const camarerosApiBase = (window.CAMAREROS_API_URL || "http://localhost:8080").replace(/\/+$/, "");

  const qr = new URLSearchParams(window.location.search).get("qr");
  const path = window.location.pathname.replace(/^\/+/, "").replace(/\/+$/, "");
  const segments = path.split("/");
  const token = segments.length === 2 && segments[0] === "invitaciones" ? segments[1] : null;

  const output = document.getElementById("output");

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function render(kind, icon, title, detail) {
    output.className = "output " + kind;
    output.innerHTML =
      '<div class="icon">' + icon + "</div>" +
      '<p class="status">' + title + "</p>" +
      '<p class="detail">' + detail + "</p>";
  }

  function fila(etiqueta, valor) {
    return (
      '<div class="field"><span class="field-label">' + etiqueta + "</span>" +
      '<span class="field-value">' + esc(valor) + "</span></div>"
    );
  }

  function renderFicha(ficha) {
    document.title = (ficha.nombre || "Ficha") + " — Personal Hostel";
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
      '<p class="brand">Personal Hostel — Ficha profesional</p>' +
      foto +
      '<p class="status">' + esc(ficha.nombre) + " " + esc(ficha.apellidos || "") + "</p>" +
      nick +
      contacto +
      '<p class="edit-hint">¿Es tu cuenta? Edítala en tu app (Personal Comander).</p>';
  }

  if (qr) {
    fetch(camarerosApiBase + "/v1/camareros/ficha?qr=" + encodeURIComponent(qr), {
      headers: { "Accept": "application/json" },
    })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (body) {
          return { status: res.status, body: body };
        });
      })
      .then(function (out) {
        const code = (out.body && out.body.code) || "";
        if (out.status === 200) {
          renderFicha(out.body);
        } else if (code === "identity.qr_invalido" || out.status === 422) {
          render("err", "⚠️", "QR no válido",
            "Este código no es un QR de profesional válido. Comprueba que el enlace está completo.");
        } else if (code === "identity.credencial_inactiva" || out.status === 409) {
          render("err", "🚫", "Credencial no activa",
            "La clave de este QR ha sido revocada o renovada. Pide al profesional su QR actualizado.");
        } else {
          render("err", "⚠️", "No se ha podido cargar la ficha",
            (out.body && out.body.detail) || "Ocurrió un error. Inténtalo de nuevo más tarde.");
        }
      })
      .catch(function () {
        render("err", "🔌", "Sin conexión",
          "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.");
      });
    return;
  }

  if (!token) {
    render("err", "⚠️", "Enlace inválido",
      "Esta dirección no corresponde a una ficha o invitación de Personal Hostel.");
    return;
  }

  fetch(apiBase + "/v1/invitaciones/" + encodeURIComponent(token) + "/aceptar", {
    method: "POST",
    headers: { "Accept": "application/json" },
  })
    .then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        return { status: res.status, body: body };
      });
    })
    .then(function (out) {
      const code = (out.body && out.body.code) || "";
      const detail = (out.body && out.body.detail) || "";
      if (out.status === 200) {
        render("ok", "✅", "¡Ya estás dentro!",
          "Te has añadido correctamente al establecimiento. Ya puedes trabajar en él desde Personal Bar.");
      } else if (code === "identity.invitacion_expirada" || out.status === 410) {
        render("err", "⏰", "La invitación ha expirado",
          "Este enlace ya no es válido. Pide al responsable del establecimiento que te envíe una nueva invitación.");
      } else if (code === "identity.invitacion_ya_usada" || out.status === 409) {
        render("warn", "🔁", "La invitación ya se ha usado",
          "Este enlace ya fue utilizado o revocado. Si crees que es un error, contacta con el establecimiento.");
      } else if (code === "identity.invitacion_no_autorizada" || out.status === 403) {
        render("err", "🚫", "No autorizado",
          "La invitación no corresponde a tu cuenta. Entra con el email al que se envió la invitación.");
      } else if (code === "identity.invitacion_no_encontrada" || out.status === 404) {
        render("err", "❓", "Invitación no encontrada",
          "No existe una invitación para este enlace. Comprueba que el enlace está completo.");
      } else if (code === "identity.camarero_no_encontrado" || out.status === 404) {
        render("warn", "👤", "Cuenta no encontrada",
          "No existe una cuenta de profesional para el email de la invitación. Regístrate primero en Personal Hostel.");
      } else {
        render("err", "⚠️", "No se ha podido completar",
          detail || "Ocurrió un error al aceptar la invitación. Inténtalo de nuevo más tarde.");
      }
    })
    .catch(function () {
      render("err", "🔌", "Sin conexión",
        "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.");
    });
})();
