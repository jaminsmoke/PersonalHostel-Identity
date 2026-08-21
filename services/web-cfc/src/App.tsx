import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, Route, Routes, useParams } from "react-router-dom";
import {
  cargarMesa,
  euros,
  totalLineas,
  type Linea,
  type Producto,
} from "./mesa";
import { extraerAccion, parsearComanda, parsearQuitar } from "./voz/parser";
import { escucharUnaFrase, vozDisponible } from "./voz/reconocer";

type Pestana = "carta" | "pedido" | "cuenta";

function ErrorQr({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-3 px-5 py-10">
      <p className="text-sm font-semibold tracking-wide text-accent uppercase">
        Mesa
      </p>
      <h1 className="text-2xl font-bold">{titulo}</h1>
      <p className="text-muted leading-relaxed">{detalle}</p>
    </main>
  );
}

function MesaShell() {
  const { token } = useParams();
  if (!token?.trim()) {
    return (
      <ErrorQr
        titulo="Falta el código de la mesa"
        detalle="Abre el QR que hay en tu mesa. Esta página no elige mesa a mano."
      />
    );
  }
  return <MesaApp token={token.trim()} />;
}

function MesaApp({ token }: { token: string }) {
  const sesion = useMemo(() => cargarMesa(token), [token]);
  const [pestana, setPestana] = useState<Pestana>("carta");
  const [carrito, setCarrito] = useState<Linea[]>([]);
  const [cuenta, setCuenta] = useState<Linea[]>(sesion.cuenta);
  const [aviso, setAviso] = useState<string | null>(null);
  const [escuchando, setEscuchando] = useState(false);
  const [previewVoz, setPreviewVoz] = useState<string | null>(null);
  const mic = vozDisponible();

  useEffect(() => {
    document.title =
      sesion.etiqueta === "Tu mesa"
        ? "Tu mesa"
        : `Mesa ${sesion.etiqueta}`;
  }, [sesion.etiqueta]);

  const categorias = useMemo(() => {
    const mapa = new Map<string, Producto[]>();
    for (const p of sesion.carta) {
      const lista = mapa.get(p.categoria) ?? [];
      lista.push(p);
      mapa.set(p.categoria, lista);
    }
    return [...mapa.entries()];
  }, [sesion.carta]);

  function anadir(producto: Producto, cantidad = 1) {
    setCarrito((prev) => {
      const i = prev.findIndex((l) => l.productoId === producto.id);
      if (i < 0) {
        return [
          ...prev,
          {
            productoId: producto.id,
            nombre: producto.nombre,
            cantidad,
            precio_centimos: producto.precio_centimos,
          },
        ];
      }
      const copia = [...prev];
      copia[i] = { ...copia[i], cantidad: copia[i].cantidad + cantidad };
      return copia;
    });
    setPestana("pedido");
  }

  function quitar(nombre: string, cantidad = 1) {
    setCarrito((prev) => {
      const i = prev.findIndex(
        (l) => l.nombre.toLowerCase() === nombre.toLowerCase(),
      );
      if (i < 0) return prev;
      const copia = [...prev];
      const resto = copia[i].cantidad - cantidad;
      if (resto <= 0) copia.splice(i, 1);
      else copia[i] = { ...copia[i], cantidad: resto };
      return copia;
    });
  }

  async function pedirPorVoz() {
    if (!mic || escuchando) return;
    setAviso(null);
    setPreviewVoz(null);
    setEscuchando(true);
    const r = await escucharUnaFrase();
    setEscuchando(false);
    if (r.error && !r.texto) {
      setAviso(
        r.error === "not-allowed"
          ? "Sin permiso de micrófono. Puedes pedir tocando la carta."
          : "No he oído nada. Prueba otra vez o pide desde la carta.",
      );
      return;
    }
    setPreviewVoz(r.texto);
    const accion = extraerAccion(r.texto);
    if (accion.tipo === "quitar") {
      const parsed = parsearQuitar(
        accion.texto,
        carrito.map((l) => ({ nombreProducto: l.nombre })),
      );
      if (parsed.lineas.length === 0) {
        setAviso("No he reconocido qué quitar del pedido.");
        return;
      }
      for (const linea of parsed.lineas) {
        quitar(linea.nombreProducto, linea.cantidad);
      }
      setPestana("pedido");
      return;
    }
    const parsed = parsearComanda(accion.texto, sesion.carta);
    if (parsed.lineas.length === 0) {
      setAviso("No he reconocido productos de la carta.");
      return;
    }
    for (const linea of parsed.lineas) {
      const producto = sesion.carta.find((p) => p.id === linea.producto.id);
      if (producto) anadir(producto, linea.cantidad);
    }
  }

  function enviarPedido() {
    if (carrito.length === 0) return;
    if (sesion.modo !== "demo") {
      setAviso(
        "Este QR aún no está conectado al servidor. Cuando existan los tokens de mesa, el pedido irá a barra.",
      );
      return;
    }
    setCuenta((prev) => [...prev, ...carrito]);
    setCarrito([]);
    setPestana("cuenta");
    setAviso(
      "Pedido apuntado en esta demostración. Bar no lo ha recibido: falta el contrato de bandeja.",
    );
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col bg-ink pb-[calc(5.5rem+env(safe-area-inset-bottom))]">
      <header className="sticky top-0 z-10 border-b border-line bg-ink/95 px-4 pt-[max(0.75rem,env(safe-area-inset-top))] pb-3 backdrop-blur">
        <p className="text-xs font-semibold tracking-[0.16em] text-accent uppercase">
          {sesion.localNombre || "Pedir en mesa"}
        </p>
        <h1 className="text-2xl font-bold">
          {sesion.etiqueta === "Tu mesa"
            ? "Tu mesa"
            : `Mesa ${sesion.etiqueta}`}
        </h1>
        {sesion.modo === "pendiente_contrato" ? (
          <p className="mt-1 text-sm text-muted">
            El código de esta mesa todavía no está dado de alta. La carta y la
            cuenta llegarán cuando Identity emita el token.
          </p>
        ) : (
          <p className="mt-1 text-sm text-muted">
            Demostración local. El micrófono no envía audio a nuestro servidor.
          </p>
        )}
      </header>

      <main className="flex-1 px-4 py-4">
        {aviso ? (
          <p className="mb-3 rounded-xl bg-raised px-3 py-2 text-sm text-paper">
            {aviso}
          </p>
        ) : null}
        {previewVoz ? (
          <p className="mb-3 text-sm text-muted">«{previewVoz}»</p>
        ) : null}

        {pestana === "carta" ? (
          sesion.carta.length === 0 ? (
            <p className="text-muted">No hay carta que mostrar todavía.</p>
          ) : (
            <ul className="flex flex-col gap-6">
              {categorias.map(([categoria, productos]) => (
                <li key={categoria}>
                  <h2 className="mb-2 text-sm font-semibold tracking-wide text-muted uppercase">
                    {categoria}
                  </h2>
                  <ul className="flex flex-col gap-2">
                    {productos.map((p) => (
                      <li
                        key={p.id}
                        className="flex items-center justify-between gap-3 rounded-2xl bg-panel px-3 py-3"
                      >
                        <div>
                          <p className="font-semibold">{p.nombre}</p>
                          <p className="text-sm text-muted">
                            {euros(p.precio_centimos)}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="min-h-11 min-w-11 rounded-full bg-accent px-4 font-semibold text-ink"
                          onClick={() => anadir(p)}
                        >
                          +
                        </button>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )
        ) : null}

        {pestana === "pedido" ? (
          carrito.length === 0 ? (
            <p className="text-muted">
              El pedido de esta pantalla está vacío. Añade desde la carta o por
              voz.
            </p>
          ) : (
            <ListaLineas
              lineas={carrito}
              pie={`A enviar · ${euros(totalLineas(carrito))}`}
              accion={{
                etiqueta: "Enviar a barra",
                onClick: enviarPedido,
              }}
            />
          )
        ) : null}

        {pestana === "cuenta" ? (
          cuenta.length === 0 ? (
            <p className="text-muted">
              En esta mesa aún no hay líneas apuntadas. Varios móviles con el
              mismo QR verán la misma cuenta cuando el servidor la sirva.
            </p>
          ) : (
            <ListaLineas
              lineas={cuenta}
              pie={`En esta mesa · ${euros(totalLineas(cuenta))}`}
            />
          )
        ) : null}
      </main>

      <button
        type="button"
        className="fixed right-4 bottom-[calc(5.25rem+env(safe-area-inset-bottom))] z-20 min-h-14 min-w-14 rounded-full bg-accent px-5 font-semibold text-ink shadow-lg disabled:opacity-40"
        disabled={!mic || escuchando || sesion.carta.length === 0}
        onClick={() => void pedirPorVoz()}
        aria-label={escuchando ? "Escuchando" : "Pedir por voz"}
      >
        {escuchando ? "…" : mic ? "Voz" : "Sin voz"}
      </button>

      <nav className="fixed right-0 bottom-0 left-0 z-20 border-t border-line bg-panel pb-[env(safe-area-inset-bottom)]">
        <ul className="mx-auto grid max-w-md grid-cols-3">
          {(
            [
              ["carta", "Carta"],
              ["pedido", `Pedido${carrito.length ? ` (${carrito.length})` : ""}`],
              ["cuenta", "Cuenta"],
            ] as const
          ).map(([id, label]) => (
            <li key={id}>
              <button
                type="button"
                className={`flex min-h-14 w-full items-center justify-center text-sm font-semibold ${
                  pestana === id ? "text-accent" : "text-muted"
                }`}
                onClick={() => setPestana(id)}
              >
                {label}
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

function ListaLineas({
  lineas,
  pie,
  accion,
}: {
  lineas: Linea[];
  pie: string;
  accion?: { etiqueta: string; onClick: () => void };
}) {
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-2">
        {lineas.map((l, i) => (
          <li
            key={`${l.productoId}-${i}`}
            className="flex items-baseline justify-between rounded-2xl bg-panel px-3 py-3"
          >
            <span>
              {l.cantidad}× {l.nombre}
            </span>
            <span className="text-muted">
              {euros(l.precio_centimos * l.cantidad)}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-right text-lg font-bold">{pie}</p>
      {accion ? (
        <button
          type="button"
          className="min-h-12 rounded-2xl bg-accent font-semibold text-ink"
          onClick={accion.onClick}
        >
          {accion.etiqueta}
        </button>
      ) : null}
    </div>
  );
}

function Inicio() {
  return (
    <ErrorQr
      titulo="Escanea el QR de tu mesa"
      detalle="Hay una sola dirección; cada mesa tiene su propio código. Sin él no se puede pedir."
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/m/:token" element={<MesaShell />} />
        <Route path="/" element={<Inicio />} />
        <Route path="*" element={<Inicio />} />
      </Routes>
    </BrowserRouter>
  );
}
