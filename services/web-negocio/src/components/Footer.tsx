import { useParams } from "react-router-dom";
import { IconoRed } from "../icons";
import { urlPaginaPublica } from "../media";
import { useWeb } from "../web-context";
import { QrMarca } from "./QrMarca";

export function Footer() {
  const web = useWeb();
  const { slug } = useParams<{ slug: string }>();
  const urlPublica = slug ? urlPaginaPublica(slug) : "";
  const redes = Object.entries(web.contacto?.redes || {});

  return (
    <footer className="w-full py-stack-lg bg-surface-lowest border-t border-outline-variant/40">
      <div className="max-w-page mx-auto px-margin-mobile md:px-gutter flex flex-col md:flex-row justify-between items-center gap-stack-lg">
        <div className="font-display text-headline-sm text-primary tracking-widest uppercase">
          {web.nombre}
        </div>
        <div className="flex items-center gap-6">
          {redes.length > 0
            ? redes.map(([nombre, url]) => (
                <a
                  key={nombre}
                  className="text-on-surface-variant hover:text-primary"
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={nombre}
                >
                  <IconoRed className="w-5 h-5" />
                </a>
              ))
            : [0, 1, 2].map((i) => (
                <span key={i} className="text-outline-variant" aria-hidden>
                  <IconoRed className="w-5 h-5 opacity-40" />
                </span>
              ))}
        </div>
        <div className="flex items-center gap-4">
          {urlPublica && <QrMarca semilla={urlPublica} />}
          <div className="text-body-md text-on-surface-variant text-sm text-center md:text-right">
            <p>
              © {new Date().getFullYear()} {web.organizacion_nombre}.
            </p>
            <p>Gestionado con Personal Hostel.</p>
            {urlPublica && (
              <a className="text-label-md text-outline hover:text-primary break-all" href={urlPublica}>
                {urlPublica.replace(/^https?:\/\//, "")}
              </a>
            )}
          </div>
        </div>
      </div>
    </footer>
  );
}
