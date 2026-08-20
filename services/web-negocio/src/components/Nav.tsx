import { NavLink, useParams } from "react-router-dom";
import { useState } from "react";
import { IconoCerrar, IconoMenu } from "../icons";
import { rutaNegocio, useWeb } from "../web-context";

const ENLACES: Array<{ pagina?: string; etiqueta: string }> = [
  { etiqueta: "Inicio" },
  { pagina: "horario", etiqueta: "Horario" },
  { pagina: "carta", etiqueta: "Carta" },
  { pagina: "equipo", etiqueta: "Equipo" },
  { pagina: "galeria", etiqueta: "Galería" },
  { pagina: "contacto", etiqueta: "Contacto" },
];

export function Nav() {
  const web = useWeb();
  const { slug } = useParams<{ slug: string }>();
  const [abierto, setAbierto] = useState(false);
  if (!slug) return null;

  const ctaHref = web.contacto?.telefono
    ? `tel:${web.contacto.telefono}`
    : web.contacto?.email_contacto
      ? `mailto:${web.contacto.email_contacto}`
      : rutaNegocio(slug, "contacto");

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    isActive
      ? "text-primary border-b-2 border-primary pb-1"
      : "text-on-surface-variant hover:text-primary-fixed-dim transition-colors duration-300";

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-surface/70 backdrop-blur-xl border-b border-outline-variant/40">
      <div className="max-w-page mx-auto px-margin-mobile md:px-gutter h-20 flex items-center justify-between">
        <NavLink
          to={rutaNegocio(slug)}
          end
          className="font-display text-headline-sm text-primary font-semibold tracking-widest uppercase"
        >
          {web.nombre}
        </NavLink>
        <div className="hidden md:flex gap-gutter items-center text-label-md uppercase tracking-widest">
          {ENLACES.map((s) => (
            <NavLink key={s.etiqueta} to={rutaNegocio(slug, s.pagina)} end className={linkClass}>
              {s.etiqueta}
            </NavLink>
          ))}
          <a
            href={ctaHref}
            className="bg-primary-container text-on-primary-container px-6 py-2 rounded hover:opacity-80 transition-opacity"
          >
            Reservar
          </a>
        </div>
        <button
          type="button"
          className="md:hidden text-primary p-2 -mr-2"
          onClick={() => setAbierto((v) => !v)}
          aria-expanded={abierto}
          aria-label={abierto ? "Cerrar menú" : "Abrir menú"}
        >
          {abierto ? <IconoCerrar className="w-7 h-7" /> : <IconoMenu className="w-7 h-7" />}
        </button>
      </div>
      {abierto && (
        <div className="md:hidden border-t border-outline-variant/40 bg-surface px-margin-mobile py-stack-md flex flex-col gap-stack-md text-label-md uppercase tracking-widest">
          {ENLACES.map((s) => (
            <NavLink
              key={s.etiqueta}
              to={rutaNegocio(slug, s.pagina)}
              end
              className={linkClass}
              onClick={() => setAbierto(false)}
            >
              {s.etiqueta}
            </NavLink>
          ))}
          <a href={ctaHref} className="text-primary-container" onClick={() => setAbierto(false)}>
            Reservar
          </a>
        </div>
      )}
    </nav>
  );
}
