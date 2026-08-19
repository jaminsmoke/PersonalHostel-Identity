import { absUrl } from "../config";
import { useWeb } from "../web-context";

export function Galeria() {
  const web = useWeb();
  return (
    <section className="flex-grow pt-[120px] pb-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto w-full">
      <h1 className="font-display text-headline-lg-mobile md:text-display-lg text-on-surface mb-stack-lg">
        Galería
      </h1>
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
