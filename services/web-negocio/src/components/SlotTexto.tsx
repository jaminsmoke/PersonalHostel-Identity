/** Hueco de copy de plantilla: no es texto del local. */
export function SlotTexto({ lineas = 3, className = "" }: { lineas?: number; className?: string }) {
  return (
    <div className={`slot-texto ${className}`.trim()} aria-hidden>
      {Array.from({ length: lineas }, (_, i) => (
        <span
          key={i}
          className="slot-texto__linea"
          style={{ width: i === lineas - 1 ? "68%" : "100%" }}
        />
      ))}
    </div>
  );
}
