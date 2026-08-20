import type { FondoSlot } from "../media";
import { fondoUrl } from "../media";
import { useWeb } from "../web-context";

export function FondoPagina({
  slot,
  overlayClassName = "bg-background/85",
}: {
  slot: FondoSlot;
  overlayClassName?: string;
}) {
  const web = useWeb();
  const url = fondoUrl(web, slot);
  return (
    <div className="absolute inset-0 z-0">
      <div
        className="w-full h-full bg-cover bg-center"
        style={{ backgroundImage: `url(${url})` }}
        aria-hidden
      />
      <div className={`absolute inset-0 ${overlayClassName}`} />
    </div>
  );
}
