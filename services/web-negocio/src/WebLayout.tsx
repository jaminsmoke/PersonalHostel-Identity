import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { Navigate, Outlet, useLocation, useParams, useSearchParams } from "react-router-dom";
import { cargarWeb, ErrorPublico } from "./api";
import type { WebNegocio } from "./types";
import { Nav } from "./components/Nav";
import { Footer } from "./components/Footer";
import { WebContext } from "./web-context";

type EstadoCarga =
  | { fase: "cargando" }
  | { fase: "error"; status: number; code: string; detalle: string }
  | { fase: "ok"; web: WebNegocio };

const SECCIONES_LEGACY: Record<string, string> = {
  carta: "carta",
  horario: "horario",
  equipo: "equipo",
  contacto: "contacto",
  galeria: "galeria",
  inicio: "",
  nosotros: "",
};

export function WebLayout() {
  const { slug } = useParams<{ slug: string }>();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [estado, setEstado] = useState<EstadoCarga>({ fase: "cargando" });

  useEffect(() => {
    if (!slug) return;
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
  }, [slug]);

  const seccion = searchParams.get("seccion");
  const hash = location.hash.replace(/^#/, "");
  const destinoLegacy = (seccion && SECCIONES_LEGACY[seccion]) ?? (hash && SECCIONES_LEGACY[hash]);
  if (slug && destinoLegacy !== undefined && (seccion || hash)) {
    const to = destinoLegacy ? `/negocios/${slug}/${destinoLegacy}` : `/negocios/${slug}`;
    return <Navigate to={to} replace />;
  }

  if (estado.fase === "cargando") {
    return <PantallaCarga />;
  }
  if (estado.fase === "error") {
    return <PantallaError estado={estado} />;
  }

  const web = estado.web;
  const style = { "--brand": web.color_primario || "#fbbc00" } as CSSProperties;

  return (
    <WebContext.Provider value={web}>
      <div className="min-h-screen flex flex-col" style={style}>
        <Nav />
        <main className="flex-1">
          <Outlet />
        </main>
        <Footer />
      </div>
    </WebContext.Provider>
  );
}

function PantallaCarga() {
  return (
    <div className="min-h-screen grid place-items-center bg-background text-on-surface-variant">
      <p className="text-label-md uppercase tracking-widest">Cargando…</p>
    </div>
  );
}

export function PantallaError({
  estado,
}: {
  estado?: Extract<EstadoCarga, { fase: "error" }>;
}) {
  const sinConexion = estado?.status === 0;
  const noEncontrado =
    !estado ||
    estado.status === 400 ||
    estado.status === 404 ||
    estado.code === "identity.enlace_no_encontrado";
  const revocado = estado?.status === 410 || estado?.code === "identity.enlace_revocado";
  const privada = estado?.code === "identity.web_privada";

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
