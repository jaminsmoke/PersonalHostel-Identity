(function () {
  "use strict";

  const apiBase = (window.IDENTITY_API_URL || "http://localhost:8080").replace(/\/+$/, "");
  const path = window.location.pathname.replace(/^\/+/, "").replace(/\/+$/, "");
  const segments = path.split("/");

  const token = segments.length === 2 && segments[0] === "invitaciones" ? segments[1] : null;

  const output = document.getElementById("output");

  function render(kind, icon, title, detail) {
    output.className = "output " + kind;
    output.innerHTML =
      '<div class="icon">' + icon + "</div>" +
      '<p class="status">' + title + "</p>" +
      '<p class="detail">' + detail + "</p>";
  }

  if (!token) {
    render("err", "⚠️", "Enlace inválido",
      "Esta dirección no corresponde a una invitación de Personal Hostel.");
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
