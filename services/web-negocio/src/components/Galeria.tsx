import { absUrl } from "../config";
import { useWeb } from "../web-context";

export function Galeria() {
  const web = useWeb();
  const fotos = web.galeria;
  const huecos = Math.max(0, 6 - fotos.length);

  return (
    <section className="flex-grow pt-[120px] pb-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto w-full">
      <h1 className="font-display text-headline-lg-mobile md:text-display-lg text-on-surface mb-stack-sm">
        Galería
      </h1>
      {fotos.length === 0 && (
        <p className="text-body-lg text-on-surface-variant mb-stack-lg">
          Aún no hemos publicado fotos.
        </p>
      )}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-stack-lg">
        {fotos.map((img) => (
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
        {Array.from({ length: huecos }, (_, i) => (
          <div
            key={`hueco-${i}`}
            className="tile-stub aspect-square rounded-lg border border-outline-variant/40"
            aria-hidden
          />
        ))}
      </div>
    </section>
  );
}
