(function () {
  "use strict";

  const camarerosApiBase = (window.CAMAREROS_API_URL || "http://localhost:8080").replace(/\/+$/, "");
  const negocioApiBase = (window.NEGOCIO_API_URL || "http://localhost:8082").replace(/\/+$/, "");
  const TOKEN_KEY = "ph_web_token";

  const output = document.getElementById("output");
  const topbar = document.getElementById("topbar");
  const badge = document.getElementById("badge");
  const navPerfil = document.getElementById("nav-perfil");
  const navInvitaciones = document.getElementById("nav-invitaciones");
  const logoutBtn = document.getElementById("logout");

  // ---------------------------------------------------------------- utilidades

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
  }

  function setToken(token) {
    try { localStorage.setItem(TOKEN_KEY, token); } catch (e) { /* sin almacenamiento */ }
  }

  function clearToken() {
    try { localStorage.removeItem(TOKEN_KEY); } catch (e) { /* sin almacenamiento */ }
  }

  function iniciales(nombre, apellidos) {
    const a = (nombre || "").trim().charAt(0);
    const b = (apellidos || "").trim().charAt(0);
    return (a + b).toUpperCase() || "?";
  }

  // fetch que devuelve { status, body } sin lanzar por HTTP != 2xx
  function fetchJson(url, options) {
    return fetch(url, options)
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (body) {
          return { status: res.status, body: body };
        });
      });
  }

  function authHeaders(extra) {
    const headers = Object.assign({ "Accept": "application/json" }, extra || {});
    const token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    return headers;
  }

  function render(html, className) {
    output.className = "output" + (className ? " " + className : "");
    output.innerHTML = html;
  }

  function renderEstado(icono, titulo, detalle, className) {
    render(
      '<div class="icon">' + icono + "</div>" +
      '<p class="status">' + esc(titulo) + "</p>" +
      '<p class="detail">' + esc(detalle) + "</p>",
      className || ""
    );
  }

  function showTopbar(show) {
    topbar.hidden = !show;
  }

  function setActiveNav(view) {
    const onPerfil = view === "perfil";
    navPerfil.classList.toggle("active", onPerfil);
    navInvitaciones.classList.toggle("active", !onPerfil);
  }

  // ---------------------------------------------------------------- ficha pública por QR

  function fila(etiqueta, valor) {
    return (
      '<div class="field"><span class="field-label">' + esc(etiqueta) + "</span>" +
      '<span class="field-value">' + esc(valor) + "</span></div>"
    );
  }

  function renderCredencial(ficha) {
    document.title = (ficha.nombre || "Profesional") + " — Personal Hostel";
    render(
      '<p class="brand">Personal Hostel — Credencial profesional</p>' +
      (ficha.foto_url
        ? '<img class="avatar" src="' + esc(camarerosApiBase + ficha.foto_url) + '" alt="Foto de ' + esc(ficha.nombre) + '" />'
        : '<div class="avatar avatar-empty">' + esc((ficha.nombre || "?").charAt(0).toUpperCase()) + "</div>") +
      '<p class="status">' + esc(ficha.nombre) + " " + esc(ficha.apellidos || "") + "</p>" +
      (ficha.nick ? '<p class="nick">@' + esc(ficha.nick) + "</p>" : "") +
      (ficha.email ? fila("Email", ficha.email) : "") +
      (ficha.telefono ? fila("Teléfono", ficha.telefono) : "") +
      (ficha.direccion ? fila("Dirección", ficha.direccion) : "") +
      (ficha.ciudad ? fila("Ciudad", ficha.ciudad) : "") +
      '<p class="edit-hint">¿Es tu cuenta? Entra y edítala desde tu app (Personal Comander).</p>',
      "ok"
    );
  }

  function errorPublico(status, code) {
    if (code === "identity.qr_invalido" || status === 422) {
      renderEstado("⚠️", "QR no válido",
        "Este código no es un QR de profesional válido. Comprueba que el enlace está completo.", "err");
    } else if (code === "identity.credencial_inactiva" || status === 409) {
      renderEstado("🚫", "Credencial no activa",
        "La clave de este QR ha sido revocada o renovada. Pide al profesional su QR actualizado.", "err");
    } else {
      renderEstado("⚠️", "No se ha podido cargar la ficha",
        "Ocurrió un error. Inténtalo de nuevo más tarde.", "err");
    }
  }

  function cargarFichaPublica(qr) {
    fetchJson(camarerosApiBase + "/v1/camareros/ficha?qr=" + encodeURIComponent(qr), {
      headers: { "Accept": "application/json" },
    }).then(function (out) {
      if (out.status === 200) {
        renderCredencial(out.body);
      } else {
        errorPublico(out.status, (out.body && out.body.code) || "");
      }
    }).catch(function () {
      renderEstado("🔌", "Sin conexión",
        "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.", "err");
    });
  }

  // ---------------------------------------------------------------- magic-link de invitación

  function estadoInvitacionToken(status, code, detalle) {
    if (code === "identity.invitacion_expirada" || status === 410) {
      return ["⏰", "La invitación ha expirado",
        "Este enlace ya no es válido. Pide al responsable del establecimiento que te envíe una nueva invitación.", "err"];
    }
    if (code === "identity.invitacion_ya_usada" || status === 409) {
      return ["🔁", "La invitación ya se ha usado",
        "Este enlace ya fue utilizado o revocado. Si crees que es un error, contacta con el establecimiento.", "warn"];
    }
    if (code === "identity.invitacion_no_autorizada" || status === 403) {
      return ["🚫", "No autorizado",
        "La invitación no corresponde a tu cuenta. Entra con el email al que se envió la invitación.", "err"];
    }
    if (code === "identity.invitacion_no_encontrada" || status === 404) {
      return ["❓", "Invitación no encontrada",
        "No existe una invitación para este enlace. Comprueba que el enlace está completo.", "err"];
    }
    if (code === "identity.camarero_no_encontrado") {
      return ["👤", "Cuenta no encontrada",
        "No existe una cuenta de profesional para el email de la invitación. Regístrate primero en Personal Hostel.", "warn"];
    }
    return ["⚠️", "No se ha podido completar",
      detalle || "Ocurrió un error al procesar la invitación. Inténtalo de nuevo más tarde.", "err"];
  }

  function cargarInvitacionToken(token) {
    document.title = "Personal Hostel — Invitación";
    render(
      '<div class="icon">📩</div>' +
      '<p class="status">Invitación a un establecimiento</p>' +
      '<p class="detail">Te han invitado a trabajar en un establecimiento de Personal Hostel. ¿Quieres aceptar?</p>' +
      '<div class="acciones">' +
        '<button class="btn btn-aceptar" id="btn-aceptar" type="button">Aceptar</button>' +
        '<button class="btn btn-rechazar" id="btn-rechazar" type="button">Rechazar</button>' +
      "</div>",
      ""
    );

    function manejarErrorToken() {
      renderEstado("🔌", "Sin conexión",
        "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.", "err");
    }

    function manejarResultadoToken(aceptar) {
      return function (out) {
        const code = (out.body && out.body.code) || "";
        const detalle = (out.body && out.body.detail) || "";
        if (out.status === 200) {
          if (aceptar) {
            renderEstado("✅", "¡Ya estás dentro!",
              "Te has añadido correctamente al establecimiento. Ya puedes trabajar en él desde Personal Bar.", "ok");
          } else {
            renderEstado("🚫", "Invitación rechazada",
              "Has rechazado la invitación. El establecimiento verá que la has declinado.", "warn");
          }
        } else {
          const st = estadoInvitacionToken(out.status, code, detalle);
          renderEstado(st[0], st[1], st[2], st[3]);
        }
      };
    }

    function postAceptarToken() {
      render('<p class="hint">Procesando invitación…</p>', "");
      fetchJson(negocioApiBase + "/v1/invitaciones/" + encodeURIComponent(token) + "/aceptar", {
        method: "POST",
        headers: { "Accept": "application/json" },
      }).then(manejarResultadoToken(true)).catch(manejarErrorToken);
    }

    function postRechazarToken() {
      render('<p class="hint">Procesando invitación…</p>', "");
      fetchJson(negocioApiBase + "/v1/invitaciones/" + encodeURIComponent(token) + "/rechazar", {
        method: "POST",
        headers: { "Accept": "application/json" },
      }).then(manejarResultadoToken(false)).catch(manejarErrorToken);
    }

    document.getElementById("btn-aceptar").addEventListener("click", postAceptarToken);
    document.getElementById("btn-rechazar").addEventListener("click", postRechazarToken);
  }

  // ---------------------------------------------------------------- login

  function renderLogin(error) {
    document.title = "Personal Hostel — Acceso";
    showTopbar(false);
    render(
      '<p class="brand">Personal Hostel — Profesional</p>' +
      '<p class="status">Accede a tu espacio</p>' +
      '<p class="detail">Entra con el email y la contraseña de tu cuenta de profesional para ver tu perfil, tus invitaciones y dónde trabajas.</p>' +
      (error ? '<p class="login-error">' + esc(error) + "</p>" : "") +
      '<form id="login-form" class="login-form" novalidate>' +
        '<label class="field-label" for="login-email">Email</label>' +
        '<input id="login-email" class="input" type="email" autocomplete="email" required />' +
        '<label class="field-label" for="login-password">Contraseña</label>' +
        '<input id="login-password" class="input" type="password" autocomplete="current-password" required />' +
        '<button class="btn btn-aceptar" type="submit">Entrar</button>' +
      "</form>",
      ""
    );

    document.getElementById("login-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      const email = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value;
      if (!email || !password) {
        renderLogin("Introduce tu email y contraseña.");
        return;
      }
      fetchJson(camarerosApiBase + "/v1/auth/login", {
        method: "POST",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ email: email, password: password }),
      }).then(function (out) {
        if (out.status === 200 && out.body.token) {
          setToken(out.body.token);
          cargarSesion();
        } else {
          const code = (out.body && out.body.code) || "";
          if (code === "identity.credential_revoked" || out.status === 409) {
            renderLogin("Tu cuenta no tiene una clave activa. Renueva la clave desde tu app (Personal Comander).");
          } else if (code === "identity.rate_limited" || out.status === 429) {
            renderLogin((out.body && out.body.detail) || "Demasiados intentos. Espera un momento e inténtalo de nuevo.");
          } else {
            renderLogin("Email o contraseña incorrectos.");
          }
        }
      }).catch(function () {
        renderLogin("No se ha podido conectar. Inténtalo de nuevo en unos segundos.");
      });
    });
  }

  function logout() {
    clearToken();
    renderLogin();
  }

  // ---------------------------------------------------------------- sesión autenticada

  function cargarSesion() {
    showTopbar(true);
    fetchJson(camarerosApiBase + "/v1/camareros/me", {
      headers: authHeaders(),
    }).then(function (out) {
      if (out.status === 200) {
        window._perfil = out.body;
        cargarDatos();
      } else if (out.status === 401) {
        clearToken();
        renderLogin();
      } else {
        renderEstado("⚠️", "No se ha podido cargar tu perfil",
          "Vuelve a intentarlo o sal y entra de nuevo.", "err");
      }
    }).catch(function () {
      renderEstado("🔌", "Sin conexión",
        "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.", "err");
    });
  }

  function cargarDatos() {
    const invitaciones = fetchJson(camarerosApiBase + "/v1/camareros/me/invitaciones", {
      headers: authHeaders(),
    });
    const establecimientos = fetchJson(camarerosApiBase + "/v1/camareros/me/establecimientos", {
      headers: authHeaders(),
    });

    Promise.all([invitaciones, establecimientos]).then(function (res) {
      const inv = res[0].status === 200 ? res[0].body : [];
      const est = res[1].status === 200 ? res[1].body : [];
      window._invitaciones = inv;
      window._establecimientos = est;

      const pendientes = inv.filter(function (i) { return i.estado === "pendiente"; }).length;
      badge.textContent = String(pendientes);
      badge.hidden = pendientes === 0;

      const view = window.location.hash === "#invitaciones" ? "invitaciones" : "perfil";
      renderVista(view);
    }).catch(function () {
      renderEstado("🔌", "Sin conexión",
        "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.", "err");
    });
  }

  function renderVista(view) {
    if (view === "invitaciones") {
      renderInvitaciones(window._invitaciones || []);
    } else {
      renderPerfil(window._perfil, window._establecimientos || []);
    }
    setActiveNav(view);
  }

  function renderPerfil(perfil, establecimientos) {
    document.title = (perfil.nombre || "Profesional") + " — Personal Hostel";
    const avatar = perfil.foto_url
      ? '<img class="avatar" src="' + esc(camarerosApiBase + perfil.foto_url) + '" alt="Foto de ' + esc(perfil.nombre) + '" />'
      : '<div class="avatar avatar-empty">' + esc(iniciales(perfil.nombre, perfil.apellidos)) + "</div>";

    const nick = perfil.nick ? '<p class="nick">@' + esc(perfil.nick) + "</p>" : "";

    const locales = establecimientos.map(function (e) {
      const rol = e.rol === "dueno" ? "Propietario/a" : "Staff";
      return '<li class="local"><span>' + esc(e.nombre) + "</span>" +
        '<span class="rol">' + esc(rol) + "</span></li>";
    }).join("");
    const bloqueLocales = establecimientos.length
      ? '<ul class="locales">' + locales + "</ul>"
      : '<p class="detail">No estás trabajando en ningún establecimiento ahora mismo.</p>';

    render(
      '<p class="brand">Personal Hostel — Tu espacio</p>' +
      avatar +
      '<p class="status">' + esc(perfil.nombre) + " " + esc(perfil.apellidos || "") + "</p>" +
      nick +
      '<div class="contacto">' +
        (perfil.email ? fila("Email", perfil.email) : "") +
        (perfil.telefono ? fila("Teléfono", perfil.telefono) : "") +
      "</div>" +
      '<section class="seccion">' +
        '<h2 class="seccion-title">Trabajas en</h2>' +
        bloqueLocales +
      "</section>" +
      '<p class="edit-hint">¿Quieres editar tu perfil? Hazlo desde tu app (Personal Comander).</p>',
      "ok"
    );
  }

  function renderInvitaciones(invitaciones) {
    document.title = "Invitaciones — Personal Hostel";

    if (!invitaciones.length) {
      render(
        '<p class="brand">Invitaciones</p>' +
        '<div class="icon">🔕</div>' +
        '<p class="status">Sin invitaciones</p>' +
        '<p class="detail">Cuando un establecimiento te invite a trabajar, aparecerá aquí.</p>',
        ""
      );
      return;
    }

    const items = invitaciones.map(function (inv) {
      let extra = "";
      if (inv.estado === "pendiente") {
        extra =
          '<div class="acciones">' +
            '<button class="btn btn-aceptar" data-id="' + esc(inv.id) + '" data-accion="aceptar" type="button">Aceptar</button>' +
            '<button class="btn btn-rechazar" data-id="' + esc(inv.id) + '" data-accion="rechazar" type="button">Rechazar</button>' +
          "</div>";
      } else {
        const etiqueta = inv.estado === "aceptada" ? "Aceptada" : (inv.estado === "rechazada" ? "Rechazada" : "Expirada");
        extra = '<p class="estado-chip">' + esc(etiqueta) + "</p>";
      }
      return (
        '<li class="invitacion">' +
          '<div class="invitacion-head">' +
            '<span class="invitacion-nombre">' + esc(inv.establecimiento_nombre) + "</span>" +
            '<span class="rol">' + esc(inv.rol === "dueno" ? "Propietario/a" : "Staff") + "</span>" +
          "</div>" +
          extra +
        "</li>"
      );
    }).join("");

    render(
      '<p class="brand">Invitaciones</p>' +
      '<ul class="invitaciones">' + items + "</ul>",
      ""
    );

    Array.prototype.forEach.call(document.querySelectorAll("[data-accion]"), function (btn) {
      btn.addEventListener("click", function () {
        const id = btn.getAttribute("data-id");
        if (btn.getAttribute("data-accion") === "aceptar") {
          postAceptarInvitacion(id);
        } else {
          postRechazarInvitacion(id);
        }
      });
    });
  }

  function manejarErrorInvitacion() {
    renderEstado("🔌", "Sin conexión",
      "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos.", "err");
  }

  function manejarResultadoInvitacion(out) {
    if (out.status === 200) {
      cargarDatos();
      return;
    }
    const code = (out.body && out.body.code) || "";
    const detalle = (out.body && out.body.detail) || "";
    if (code === "identity.invitacion_ya_usada" || out.status === 409) {
      renderEstado("🔁", "La invitación ya no está disponible", detalle, "warn");
    } else if (code === "identity.invitacion_expirada" || out.status === 410) {
      renderEstado("⏰", "La invitación ha expirado", detalle, "err");
    } else {
      renderEstado("⚠️", "No se ha podido completar", detalle || "Inténtalo de nuevo más tarde.", "err");
    }
  }

  function postAceptarInvitacion(id) {
    fetchJson(camarerosApiBase + "/v1/camareros/me/invitaciones/" + encodeURIComponent(id) + "/aceptar", {
      method: "POST",
      headers: authHeaders(),
    }).then(manejarResultadoInvitacion).catch(manejarErrorInvitacion);
  }

  function postRechazarInvitacion(id) {
    fetchJson(camarerosApiBase + "/v1/camareros/me/invitaciones/" + encodeURIComponent(id) + "/rechazar", {
      method: "POST",
      headers: authHeaders(),
    }).then(manejarResultadoInvitacion).catch(manejarErrorInvitacion);
  }

  function handleHash() {
    if (!getToken()) return;
    const view = window.location.hash === "#invitaciones" ? "invitaciones" : "perfil";
    // si ya tenemos datos cargados, renderiza; si no, recarga la sesión
    if (window._perfil) {
      renderVista(view);
    } else {
      cargarSesion();
    }
  }

  // ---------------------------------------------------------------- arranque

  const path = window.location.pathname.replace(/^\/+/, "").replace(/\/+$/, "");
  const segments = path.split("/");
  const qr = new URLSearchParams(window.location.search).get("qr");

  logoutBtn.addEventListener("click", logout);
  navPerfil.addEventListener("click", function (ev) {
    ev.preventDefault();
    window.location.hash = "#perfil";
  });
  navInvitaciones.addEventListener("click", function () {
    window.location.hash = "#invitaciones";
  });
  window.addEventListener("hashchange", handleHash);

  if (segments.length === 1 && segments[0] === "camareros" && qr) {
    showTopbar(false);
    cargarFichaPublica(qr);
  } else if (segments.length === 2 && segments[0] === "invitaciones" && segments[1]) {
    showTopbar(false);
    cargarInvitacionToken(segments[1]);
  } else if (getToken()) {
    cargarSesion();
  } else {
    renderLogin();
  }
})();
