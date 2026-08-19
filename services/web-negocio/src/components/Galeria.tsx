import { absUrl } from "../config";
import type { WebNegocio } from "../types";

export function Galeria({ web }: { web: WebNegocio }) {
  return (
    <section
      id="galeria"
      className="py-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto scroll-mt-20"
    >
      <h2 className="text-label-md text-primary-fixed-dim uppercase tracking-widest mb-stack-md">
        Galería
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {web.galeria.map((img) => (
          <a
            key={img.id}
            href={absUrl(img.url)}
            className="block aspect-square overflow-hidden rounded-lg border border-outline-variant/50"
          >
            <img
              className="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
              src={absUrl(img.url)}
              alt=""
              loading="lazy"
            />
          </a>
        ))}
      </div>
    </section>
  );
}