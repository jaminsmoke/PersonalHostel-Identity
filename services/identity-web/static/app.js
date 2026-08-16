(function () {
  "use strict";

  const apiBase = (window.IDENTITY_API_URL || "http://localhost:8080").replace(/\/+$/, "");
  const camarerosApiBase = (window.CAMAREROS_API_URL || "http://localhost:8080").replace(/\/+$/, "");
  const negocioApiBase = (window.NEGOCIO_API_URL || "http://localhost:8082").replace(/\/+$/, "");

  const qr = new URLSearchParams(window.location.search).get("qr");
  const slug = new URLSearchParams(window.location.search).get("slug");
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

  function renderFicha(ficha) {
    document.title = (ficha.nombre || "Ficha") + " — Personal Hostel";
    output.className = "output ok";

    const foto = ficha.foto_url
      ? '<img class="avatar" src="' + esc(camarerosApiBase + ficha.foto_url) + '" alt="Foto de ' + esc(ficha.nombre) + '" />'
      : '<div class="avatar avatar-empty">' + esc((ficha.nombre || "?").charAt(0).toUpperCase()) + "</div>";

    const nick = ficha.nick ? '<p class="nick">@' + esc(ficha.nick) + "</p>" : "";

    output.innerHTML =
      '<p class="brand">Personal Hostel — Ficha profesional</p>' +
      foto +
      '<p class="status">' + esc(ficha.nombre) + " " + esc(ficha.apellidos || "") + "</p>" +
      nick;
  }

  function renderFichaNegocio(ficha) {
    document.title = (ficha.nombre || "Negocio") + " — Personal Hostel";
    output.className = "output ok";

    const logo = ficha.logo_url
      ? '<img class="logo" src="' + esc(negocioApiBase + ficha.logo_url) + '" alt="Logo de ' + esc(ficha.nombre) + '" />'
      : '<div class="logo logo-empty">' + esc((ficha.nombre || "?").charAt(0).toUpperCase()) + "</div>";

    const tipo = ficha.tipo_establecimiento
      ? '<p class="tipo">' + esc(ficha.tipo_establecimiento) + "</p>"
      : "";

    const locales = (ficha.establecimientos || [])
      .map(function (e) { return '<li>' + esc(e.nombre) + "</li>"; })
      .join("");

    output.innerHTML =
      '<p class="brand">Personal Hostel — Ficha del negocio</p>' +
      logo +
      '<p class="status">' + esc(ficha.nombre) + "</p>" +
      tipo +
      (locales ? '<ul class="locales">' + locales + "</ul>" : "");
  }

  function formatPrecio(centimos, moneda) {
    var simbolo = moneda === "EUR" ? "€" : moneda;
    return (Number(centimos) / 100).toFixed(2) + " " + simbolo;
  }

  function renderCarta(carta) {
    document.title = (carta.nombre || "Carta") + " — Personal Hostel";
    document.querySelector("main").className = "card wide";
    output.className = "output ok";

    var bloques = (carta.categorias || []).map(function (cat) {
      var items = (cat.productos || []).map(function (p) {
        return '<li class="producto"><span>' + esc(p.nombre) +
          '</span><span class="precio">' + esc(formatPrecio(p.precio_centimos, p.moneda)) + "</span></li>";
      }).join("");
      return '<section class="categoria"><h2>' + esc(cat.nombre) +
        '</h2><ul class="productos">' + items + "</ul></section>";
    }).join("");

    output.innerHTML =
      '<p class="brand">Personal Hostel — Carta</p>' +
      '<p class="status">' + esc(carta.nombre) + "</p>" +
      (bloques || '<p class="detail">No hay productos disponibles en este momento.</p>');
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

  function errorPublico(status, code) {
    if (code === "identity.enlace_no_encontrado" || status === 404) {
      render("err", "❓", "Enlace no encontrado",
        "No existe un enlace público con ese código. Comprueba que el enlace está completo.");
    } else if (code === "identity.enlace_revocado" || status === 410) {
      render("err", "🚫", "Enlace no disponible",
        "Este enlace ya no está activo. Pide al negocio su enlace actualizado.");
    } else {
      render("err", "⚠️", "No se ha podido cargar",
        "Ocurrió un error. Inténtalo de nuevo más tarde.");
    }
  }

  function cargarPublico(url, okHandler) {
    fetch(url, { headers: { "Accept": "application/json" } })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (body) {
          return { status: res.status, body: body };
        });
      })
      .then(function (out) {
        if (out.status === 200) {
          okHandler(out.body);
        } else {
          errorPublico(out.status, (out.body && out.body.code) || "");
        }
      })
      .catch(function () {
        render("err", "🔌", "Sin conexión",
          "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.");
      });
  }

  if (path === "negocio" && slug) {
    cargarPublico(negocioApiBase + "/v1/negocio/ficha?slug=" + encodeURIComponent(slug), renderFichaNegocio);
    return;
  }

  if (path === "carta" && slug) {
    cargarPublico(negocioApiBase + "/v1/negocio/carta?slug=" + encodeURIComponent(slug), renderCarta);
    return;
  }

  if (!token) {
    render("err", "⚠️", "Enlace inválido",
      "Esta dirección no corresponde a una ficha, carta o invitación de Personal Hostel.");
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
