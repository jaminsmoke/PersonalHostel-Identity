import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { cargarWeb, ErrorPublico } from "./api";
import type { WebNegocio } from "./types";
import { Nav } from "./components/Nav";
import { Hero } from "./components/Hero";
import { Nosotros } from "./components/Nosotros";
import { Horario } from "./components/Horario";
import { Carta } from "./components/Carta";
import { Equipo } from "./components/Equipo";
import { Galeria } from "./components/Galeria";
import { Contacto } from "./components/Contacto";
import { Footer } from "./components/Footer";

type EstadoCarga =
  | { fase: "cargando" }
  | { fase: "error"; status: number; code: string; detalle: string }
  | { fase: "ok"; web: WebNegocio };

function slugDeRuta(): string | null {
  const path = window.location.pathname.replace(/^\/+/, "").replace(/\/+$/, "");
  const segments = path.split("/");
  return segments.length === 2 && segments[0] === "negocios" ? segments[1] : null;
}

export default function App() {
  const [estado, setEstado] = useState<EstadoCarga>({ fase: "cargando" });
  const [seccion] = useState(() =>
    new URLSearchParams(window.location.search).get("seccion"),
  );

  useEffect(() => {
    const slug = slugDeRuta();
    if (!slug) {
      setEstado({
        fase: "error",
        status: 400,
        code: "identity.enlace_no_encontrado",
        detalle:
          "Esta dirección no corresponde a la web pública de un negocio de Personal Hostel.",
      });
      return;
    }
    cargarWeb(slug)
      .then((web) => {
        setEstado({ fase: "ok", web });
        document.title = `${web.nombre} — Personal Hostel`;
      })
      .catch((error: unknown) => {
        if (error instanceof ErrorPublico) {
          setEstado({
            fase: "error",
            status: error.status,
            code: error.code,
            detalle: error.message,
          });
        } else {
          setEstado({ fase: "error", status: 0, code: "", detalle: "Sin conexión" });
        }
      });
  }, []);

  useEffect(() => {
    if (estado.fase !== "ok") return;
    if (!seccion) return;
    const target = document.getElementById(seccion);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [estado, seccion]);

  if (estado.fase === "cargando") {
    return <PantallaCarga />;
  }
  if (estado.fase === "error") {
    return <PantallaError estado={estado} />;
  }

  const web = estado.web;
  const style = { "--brand": web.color_primario || "#fbbc00" } as CSSProperties;
  const secciones: Array<{ id: string; etiqueta: string }> = [
    { id: "inicio", etiqueta: "Inicio" },
  ];
  if (web.perfil) secciones.push({ id: "nosotros", etiqueta: "Nosotros" });
  if (web.horario?.length) secciones.push({ id: "horario", etiqueta: "Horario" });
  if (web.categorias.length) secciones.push({ id: "carta", etiqueta: "Carta" });
  if (web.equipo.length) secciones.push({ id: "equipo", etiqueta: "Equipo" });
  if (web.galeria.length) secciones.push({ id: "galeria", etiqueta: "Galería" });
  if (web.contacto) secciones.push({ id: "contacto", etiqueta: "Contacto" });

  return (
    <div style={style}>
      <Nav nombre={web.nombre} secciones={secciones} />
      <main>
        <Hero web={web} />
        {web.perfil && <Nosotros web={web} />}
        {web.horario?.length && <Horario web={web} />}
        {web.categorias.length > 0 && <Carta web={web} />}
        {web.equipo.length > 0 && <Equipo web={web} />}
        {web.galeria.length > 0 && <Galeria web={web} />}
        {web.contacto && <Contacto web={web} />}
      </main>
      <Footer web={web} />
    </div>
  );
}

function PantallaCarga() {
  return (
    <div className="min-h-screen grid place-items-center bg-background text-on-surface-variant">
      <p className="text-label-md uppercase tracking-widest">Cargando…</p>
    </div>
  );
}

function PantallaError({ estado }: { estado: Extract<EstadoCarga, { fase: "error" }> }) {
  const sinConexion = estado.status === 0;
  const noEncontrado =
    estado.status === 404 || estado.code === "identity.enlace_no_encontrado";
  const revocado = estado.status === 410 || estado.code === "identity.enlace_revocado";
  const privada = estado.code === "identity.web_privada";

  const icono = sinConexion ? "🔌" : noEncontrado ? "❓" : revocado ? "🚫" : privada ? "🔒" : "⚠️";
  const titulo = sinConexion
    ? "Sin conexión"
    : noEncontrado
      ? "Enlace no encontrado"
      : revocado
        ? "Enlace no disponible"
        : privada
          ? "Web privada"
          : "No se ha podido cargar";
  const detalle = sinConexion
    ? "No se ha podido conectar con el servicio. Inténtalo de nuevo en unos segundos."
    : noEncontrado
      ? "No existe una web pública con ese código. Comprueba que el enlace está completo."
      : revocado
        ? "Este enlace ya no está activo. Pide al negocio su enlace actualizado."
        : privada
          ? "El negocio ha marcado esta página como privada."
          : "Ocurrió un error. Inténtalo de nuevo más tarde.";

  return (
    <div className="min-h-screen grid place-items-center bg-background px-margin-mobile">
      <div className="text-center max-w-md">
        <div className="text-3xl mb-3">{icono}</div>
        <p className="text-headline-sm text-on-surface font-semibold mb-2">{titulo}</p>
        <p className="text-body-md text-on-surface-variant">{detalle}</p>
      </div>
    </div>
  );
}