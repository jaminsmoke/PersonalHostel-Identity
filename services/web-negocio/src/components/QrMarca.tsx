import { useMemo } from "react";

/** Marca de pie con finder patterns; la URL real va al lado, no se finge un QR escaneable. */
export function QrMarca({ semilla }: { semilla: string }) {
  const celdas = useMemo(() => {
    let h = 2166136261;
    for (let i = 0; i < semilla.length; i++) {
      h ^= semilla.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    const bits: boolean[] = [];
    for (let i = 0; i < 21 * 21; i++) {
      h ^= i + 1;
      h = Math.imul(h, 16777619);
      bits.push((h >>> 8) % 3 !== 0);
    }
    return bits;
  }, [semilla]);

  const finder = (r: number, c: number) => {
    const inFinder = (x: number, y: number) =>
      r >= y && r < y + 7 && c >= x && c < x + 7
        ? r === y || r === y + 6 || c === x || c === x + 6 || (r >= y + 2 && r <= y + 4 && c >= x + 2 && c <= x + 4)
        : null;
    return inFinder(0, 0) ?? inFinder(14, 0) ?? inFinder(0, 14);
  };

  const rects: string[] = [];
  for (let r = 0; r < 21; r++) {
    for (let c = 0; c < 21; c++) {
      const f = finder(r, c);
      const on = f !== null ? f : Boolean(celdas[r * 21 + c]);
      if (on) rects.push(`M${c} ${r}h1v1h-1z`);
    }
  }

  return (
    <svg viewBox="0 0 21 21" className="w-16 h-16 text-primary" aria-hidden>
      <rect width="21" height="21" fill="#0c0f0f" />
      <path d={rects.join("")} fill="currentColor" />
    </svg>
  );
}
