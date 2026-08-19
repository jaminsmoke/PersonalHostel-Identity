export interface SeccionNav {
  id: string;
  etiqueta: string;
}

export function Nav({
  nombre,
  secciones,
}: {
  nombre: string;
  secciones: SeccionNav[];
}) {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-surface/70 backdrop-blur-xl border-b border-outline-variant/40">
      <div className="max-w-page mx-auto px-margin-mobile md:px-gutter h-20 flex items-center justify-between">
        <a href="#inicio" className="font-display text-headline-sm text-primary font-semibold">
          {nombre}
        </a>
        <div className="hidden md:flex gap-gutter items-center text-label-md">
          {secciones.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="text-on-surface-variant hover:text-primary-fixed-dim transition-colors duration-300"
            >
              {s.etiqueta}
            </a>
          ))}
        </div>
      </div>
    </nav>
  );
}