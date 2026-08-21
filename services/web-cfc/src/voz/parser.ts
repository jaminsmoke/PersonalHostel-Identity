/** Parser de comanda hablada, semántica alineada con Commander (`VozParser.kt`). */

export type ProductoVoz = {
  id: string;
  nombre: string;
};

export type LineaVoz = {
  producto: ProductoVoz;
  cantidad: number;
};

export type ResultadoVoz = {
  lineas: LineaVoz[];
  noEntendido: string[];
};

export type LineaQuitar = {
  nombreProducto: string;
  cantidad: number;
};

export type ResultadoQuitar = {
  lineas: LineaQuitar[];
  noEntendido: string[];
};

export type AccionVoz =
  | { tipo: "anadir"; texto: string }
  | { tipo: "quitar"; texto: string };

export function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9ñ\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function levenshtein(a: string, b: string): number {
  if (a === b) return 0;
  const dp = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    let prev = dp[0];
    dp[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const temp = dp[j];
      dp[j] = Math.min(
        dp[j] + 1,
        dp[j - 1] + 1,
        prev + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
      prev = temp;
    }
  }
  return dp[b.length];
}

const NUMEROS: Record<string, number> = {
  cero: 0,
  un: 1,
  una: 1,
  uno: 1,
  unas: 1,
  unos: 1,
  dos: 2,
  tres: 3,
  cuatro: 4,
  cinco: 5,
  seis: 6,
  siete: 7,
  ocho: 8,
  nueve: 9,
  diez: 10,
  once: 11,
  doce: 12,
  trece: 13,
  catorce: 14,
  quince: 15,
  dieciseis: 16,
  diecisiete: 17,
  dieciocho: 18,
  diecinueve: 19,
  veinte: 20,
  veintiuno: 21,
  veintiun: 21,
  veintidos: 22,
  veintitres: 23,
  veinticuatro: 24,
  veinticinco: 25,
  veintiseis: 26,
  veintisiete: 27,
  veintiocho: 28,
  veintinueve: 29,
  treinta: 30,
  cuarenta: 40,
  cincuenta: 50,
  sesenta: 60,
  setenta: 70,
  ochenta: 80,
  noventa: 90,
  cien: 100,
  ciento: 100,
};

const DECENAS = new Set([
  "veinte",
  "treinta",
  "cuarenta",
  "cincuenta",
  "sesenta",
  "setenta",
  "ochenta",
  "noventa",
]);

const RELLENO = new Set([
  "y",
  "e",
  "el",
  "la",
  "los",
  "las",
  "un",
  "una",
  "uno",
  "de",
  "del",
  "a",
  "al",
  "por",
  "para",
  "quiero",
  "quisiera",
  "me",
  "pongo",
  "pon",
  "ponme",
  "pongame",
  "trae",
  "traeme",
  "necesito",
  "tambien",
  "mas",
  "otra",
  "otro",
  "luego",
  "despues",
  "deme",
  "vale",
  "gracias",
  "porfa",
  "porfavor",
  "ademas",
  "ahora",
  "dame",
  "poner",
  "anadir",
  "anade",
  "anadime",
  "apunta",
  "apuntame",
  "vamos",
  "ver",
  "pues",
  "entonces",
  "va",
  "venga",
  "bueno",
  "porfi",
  "todo",
  "nada",
  "ok",
  "mira",
  "oye",
  "eh",
  "esto",
  "favor",
  "mesa",
]);

const KEYWORDS_QUITAR = [
  "quita",
  "borra",
  "elimina",
  "saca",
  "quitar",
  "borrar",
  "eliminar",
  "retira",
  "retirar",
  "tacha",
  "anula",
  "anular",
];

function esCantidad(tok: string): boolean {
  return Number.isFinite(Number(tok)) || tok in NUMEROS;
}

function numeroCompuesto(tokens: string[], i: number): number | null {
  if (i + 2 >= tokens.length) return null;
  const decena = NUMEROS[tokens[i]];
  if (decena === undefined || !DECENAS.has(tokens[i])) return null;
  if (tokens[i + 1] !== "y" && tokens[i + 1] !== "e") return null;
  const unidad = NUMEROS[tokens[i + 2]];
  if (unidad === undefined || unidad < 1 || unidad > 9) return null;
  return decena + unidad;
}

export function extraerAccion(texto: string): AccionVoz {
  const norm = normalizar(texto);
  for (const kw of KEYWORDS_QUITAR) {
    if (norm === kw) return { tipo: "quitar", texto: "" };
    if (norm.startsWith(`${kw} `)) {
      return { tipo: "quitar", texto: norm.slice(kw.length).trim() };
    }
  }
  return { tipo: "anadir", texto: norm };
}

function buscarExacto<T>(
  tokens: string[],
  i: number,
  items: Array<{ toks: string[]; item: T }>,
): { len: number; item: T } | null {
  let mejor: { len: number; item: T } | null = null;
  for (const { toks, item } of items) {
    if (i + toks.length > tokens.length) continue;
    const slice = tokens.slice(i, i + toks.length);
    if (slice.every((t, idx) => t === toks[idx])) {
      if (!mejor || toks.length > mejor.len) mejor = { len: toks.length, item };
    }
  }
  return mejor;
}

function buscarDifuso<T>(
  tokens: string[],
  i: number,
  items: Array<{ toks: string[]; item: T }>,
): { len: number; item: T } | null {
  let mejor: { len: number; item: T } | null = null;
  let mejorDist = Number.POSITIVE_INFINITY;
  let mejorLen = 0;
  for (const { toks, item } of items) {
    let len = Math.min(toks.length, tokens.length - i);
    if (len < 1) continue;
    const headIn = tokens[i].length > 1 && tokens[i].endsWith("s")
      ? tokens[i].slice(0, -1)
      : tokens[i];
    const headOk =
      levenshtein(headIn, toks[0]) <= 1 || levenshtein(tokens[i], toks[0]) <= 1;
    while (len > 1 && headOk) {
      const last = tokens[i + len - 1];
      const prev = tokens[i + len - 2];
      const colaSala =
        RELLENO.has(last) || (esCantidad(last) && prev === "para");
      const lastProd = toks[len - 1];
      const lastSing =
        last.length > 1 && last.endsWith("s") ? last.slice(0, -1) : last;
      const lastNoEsProducto =
        lastProd !== undefined &&
        levenshtein(last, lastProd) > 1 &&
        levenshtein(lastSing, lastProd) > 1;
      if (!colaSala && !lastNoEsProducto) break;
      len -= 1;
    }
    if (len < toks.length && i + len < tokens.length) {
      const nextInput = tokens[i + len];
      const nextProduct = toks[len];
      const nextEsSala =
        RELLENO.has(nextInput) ||
        (nextInput === "para" &&
          i + len + 1 < tokens.length &&
          esCantidad(tokens[i + len + 1]));
      if (!nextEsSala && levenshtein(nextInput, nextProduct) > 2) continue;
    }
    const sub = tokens.slice(i, i + len).join(" ");
    const subSingular =
      sub.length > 1 && sub.endsWith("s") ? sub.slice(0, -1) : sub;
    const objetivoFull = toks.join(" ");
    const objetivo = toks.slice(0, len).join(" ");
    const d = Math.min(
      levenshtein(sub, objetivo),
      levenshtein(sub, objetivoFull),
      levenshtein(subSingular, objetivoFull),
    );
    const tolerancia = len === 1 ? 1 : len + 1;
    if (d > tolerancia) continue;
    if (d < mejorDist || (d === mejorDist && len > mejorLen)) {
      mejorDist = d;
      mejorLen = len;
      mejor = { len, item };
    }
  }
  return mejor;
}

function indiceTrasPara(
  tokens: string[],
  i: number,
  hayProducto: (j: number) => boolean,
): number | null {
  if (tokens[i] !== "para" || i + 1 >= tokens.length || !esCantidad(tokens[i + 1])) {
    return null;
  }
  const after = i + 2;
  if (after >= tokens.length || !hayProducto(after)) return after;
  return i + 1;
}

export function parsearComanda(
  texto: string,
  productos: ProductoVoz[],
): ResultadoVoz {
  const tokens = normalizar(texto).split(" ").filter(Boolean);
  if (tokens.length === 0) return { lineas: [], noEntendido: [] };

  const items = productos.map((p) => ({
    toks: normalizar(p.nombre).split(" ").filter(Boolean),
    item: p,
  }));

  const hayProducto = (j: number) =>
    buscarExacto(tokens, j, items) !== null ||
    buscarDifuso(tokens, j, items) !== null;

  const lineas: LineaVoz[] = [];
  const noEntendido: string[] = [];
  let i = 0;
  let qty = 1;

  while (i < tokens.length) {
    const tok = tokens[i];
    const salto = indiceTrasPara(tokens, i, hayProducto);
    if (salto !== null) {
      i = salto;
      continue;
    }
    const compuesto = numeroCompuesto(tokens, i);
    if (compuesto !== null) {
      qty = compuesto;
      i += 3;
      continue;
    }
    const numero = Number.isFinite(Number(tok)) ? Number(tok) : NUMEROS[tok];
    if (numero !== undefined) {
      qty = numero;
      i += 1;
      continue;
    }
    const match =
      buscarExacto(tokens, i, items) ?? buscarDifuso(tokens, i, items);
    if (match) {
      lineas.push({ producto: match.item, cantidad: qty });
      i += match.len;
      qty = 1;
      continue;
    }
    if (RELLENO.has(tok)) {
      i += 1;
      continue;
    }
    noEntendido.push(tok);
    i += 1;
  }
  return { lineas, noEntendido };
}

export function parsearQuitar(
  texto: string,
  lineas: Array<{ nombreProducto: string }>,
): ResultadoQuitar {
  const tokens = normalizar(texto).split(" ").filter(Boolean);
  if (tokens.length === 0) return { lineas: [], noEntendido: [] };

  const items = lineas.map((l) => ({
    toks: normalizar(l.nombreProducto).split(" ").filter(Boolean),
    item: l,
  }));

  const hayProducto = (j: number) =>
    buscarExacto(tokens, j, items) !== null ||
    buscarDifuso(tokens, j, items) !== null;

  const quitadas: LineaQuitar[] = [];
  const noEntendido: string[] = [];
  let i = 0;
  let qty = 1;

  while (i < tokens.length) {
    const tok = tokens[i];
    const salto = indiceTrasPara(tokens, i, hayProducto);
    if (salto !== null) {
      i = salto;
      continue;
    }
    const compuesto = numeroCompuesto(tokens, i);
    if (compuesto !== null) {
      qty = compuesto;
      i += 3;
      continue;
    }
    const numero = Number.isFinite(Number(tok)) ? Number(tok) : NUMEROS[tok];
    if (numero !== undefined) {
      qty = numero;
      i += 1;
      continue;
    }
    const match =
      buscarExacto(tokens, i, items) ?? buscarDifuso(tokens, i, items);
    if (match) {
      quitadas.push({
        nombreProducto: match.item.nombreProducto,
        cantidad: qty,
      });
      i += match.len;
      qty = 1;
      continue;
    }
    if (RELLENO.has(tok)) {
      i += 1;
      continue;
    }
    noEntendido.push(tok);
    i += 1;
  }
  return { lineas: quitadas, noEntendido };
}
