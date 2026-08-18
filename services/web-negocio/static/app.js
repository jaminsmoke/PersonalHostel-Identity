(function () {
  "use strict";

  const negocioApiBase = (window.NEGOCIO_API_URL || "http://localhost:8082").replace(/\/+$/, "");

  const path = window.location.pathname.replace(/^\/+/, "").replace(/\/+$/, "");
  const segments = path.split("/");
  const slug = segments.length === 2 && segments[0] === "negocios" ? segments[1] : null;
  const seccion = new URLSearchParams(window.location.search).get("seccion");

  const output = document.getElementById("output");

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function renderError(icono, titulo, detalle) {
    document.body.className = "theme-default";
    output.innerHTML =
      '<div class="icon">' + icono + "</div>" +
      '<p class="status">' + titulo + "</p>" +
      '<p class="detail">' + detalle + "</p>";
  }

  function errorPublico(status, code) {
    if (code === "identity.enlace_no_encontrado" || status === 404) {
      renderError("❓", "Enlace no encontrado",
        "No existe una web pública con ese código. Comprueba que el enlace está completo.");
    } else if (code === "identity.enlace_revocado" || status === 410) {
      renderError("🚫", "Enlace no disponible",
        "Este enlace ya no está activo. Pide al negocio su enlace actualizado.");
    } else {
      renderError("⚠️", "No se ha podido cargar",
        "Ocurrió un error. Inténtalo de nuevo más tarde.");
    }
  }

  function formatPrecio(centimos, moneda) {
    const simbolo = moneda === "EUR" ? "€" : moneda;
    return (Number(centimos) / 100).toFixed(2) + " " + simbolo;
  }

  function plantillaPorTipo(tipo) {
    if (tipo === "bar") return "theme-bar";
    if (tipo === "restaurante" || tipo === "cafeteria") return "theme-hosteleria";
    if (tipo === "pub" || tipo === "copas") return "theme-noche";
    return "theme-default";
  }

  function renderWeb(web) {
    document.title = (web.nombre || "Negocio") + " — Personal Hostel";
    document.body.className = plantillaPorTipo(web.tipo_establecimiento);

    const logo = web.logo_url
      ? '<img class="logo" src="' + esc(negocioApiBase + web.logo_url) + '" alt="Logo de ' + esc(web.nombre) + '" />'
      : '<div class="logo logo-empty">' + esc((web.nombre || "?").charAt(0).toUpperCase()) + "</div>";

    const tipo = web.tipo_establecimiento
      ? '<p class="tipo">' + esc(web.tipo_establecimiento) + "</p>"
      : "";

    const organizacion = web.organizacion_nombre && web.organizacion_nombre !== web.nombre
      ? '<p class="organizacion">' + esc(web.organizacion_nombre) + "</p>"
      : "";

    const bloques = (web.categorias || []).map(function (cat) {
      const items = (cat.productos || []).map(function (p) {
        return '<li class="producto"><span>' + esc(p.nombre) +
          '</span><span class="precio">' + esc(formatPrecio(p.precio_centimos, p.moneda)) + "</span></li>";
      }).join("");
      return '<section class="categoria"><h2>' + esc(cat.nombre) +
        '</h2><ul class="productos">' + items + "</ul></section>";
    }).join("");

    output.innerHTML =
      '<header class="hero">' + logo +
        '<div class="hero-text">' +
          '<h1 class="nombre">' + esc(web.nombre) + "</h1>" +
          tipo + organizacion +
        "</div>" +
      "</header>" +
      '<section class="carta" id="carta">' +
        '<h2 class="carta-title">Carta</h2>' +
        (bloques || '<p class="detail">No hay productos disponibles en este momento.</p>') +
      "</section>";

    if (seccion === "carta") {
      const target = document.getElementById("carta");
      if (target && target.scrollIntoView) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
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
        renderError("🔌", "Sin conexión",
          "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.");
      });
  }

  if (!slug) {
    renderError("⚠️", "Enlace inválido",
      "Esta dirección no corresponde a la web pública de un negocio de Personal Hostel.");
    return;
  }

  cargarPublico(
    negocioApiBase + "/v1/negocio/web?slug=" + encodeURIComponent(slug),
    renderWeb
  );
})();