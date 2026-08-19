import type { WebNegocio } from "../types";

export function Footer({ web }: { web: WebNegocio }) {
  return (
    <footer className="w-full py-stack-lg bg-surface-lowest border-t border-outline-variant/40">
      <div className="max-w-page mx-auto px-margin-mobile md:px-gutter flex flex-col md:flex-row justify-between items-center gap-stack-md">
        <div className="font-display text-headline-sm text-primary">{web.nombre}</div>
        <div className="text-body-md text-on-surface-variant text-sm text-center md:text-right">
          © {new Date().getFullYear()} {web.organizacion_nombre}. Gestionado con Personal Hostel.
        </div>
      </div>
    </footer>
  );
}