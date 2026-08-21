import { describe, expect, it } from "vitest";
import {
  extraerAccion,
  normalizar,
  parsearComanda,
  parsearQuitar,
} from "./parser";

const carta = [
  { id: "cafe-leche", nombre: "Café con leche" },
  { id: "cafe-solo", nombre: "Café solo" },
  { id: "tarta", nombre: "Tarta de queso" },
  { id: "croquetas", nombre: "Croquetas" },
  { id: "cana", nombre: "Caña" },
];

describe("normalizar", () => {
  it("quita acentos y pasa a minúsculas", () => {
    expect(normalizar("Café con leche")).toBe("cafe con leche");
  });
});

describe("extraerAccion", () => {
  it("añade por defecto", () => {
    expect(extraerAccion("dos cafés con leche")).toEqual({
      tipo: "anadir",
      texto: "dos cafes con leche",
    });
  });

  it("detecta quitar", () => {
    expect(extraerAccion("quita un café")).toEqual({
      tipo: "quitar",
      texto: "un cafe",
    });
  });
});

describe("parsearComanda", () => {
  it("entiende cantidades y varios productos", () => {
    const r = parsearComanda(
      "dos cafés con leche y una tarta de queso",
      carta,
    );
    expect(r.lineas).toEqual([
      { producto: carta[0], cantidad: 2 },
      { producto: carta[2], cantidad: 1 },
    ]);
    expect(r.noEntendido).toEqual([]);
  });

  it("ignora relleno de sala", () => {
    const r = parsearComanda("ponme porfa una caña gracias", carta);
    expect(r.lineas).toEqual([{ producto: carta[4], cantidad: 1 }]);
  });

  it("no confunde café capuccino con café solo", () => {
    const r = parsearComanda("un café capuccino", carta);
    expect(r.lineas.map((l) => l.producto.id)).not.toContain("cafe-solo");
  });

  it("entiende treinta y cinco", () => {
    const r = parsearComanda("treinta y cinco croquetas", carta);
    expect(r.lineas).toEqual([{ producto: carta[3], cantidad: 35 }]);
  });
});

describe("parsearQuitar", () => {
  it("quita del carrito por nombre", () => {
    const r = parsearQuitar("quita un café con leche", [
      { nombreProducto: "Café con leche" },
      { nombreProducto: "Caña" },
    ]);
    expect(r.lineas).toEqual([
      { nombreProducto: "Café con leche", cantidad: 1 },
    ]);
  });
});
