import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Svg({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  );
}

export function IconoMenu(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </Svg>
  );
}

export function IconoCerrar(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  );
}

export function IconoDirecciones(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3l8 8-8 10L4 11l8-8z" />
      <path d="M12 11v6" />
      <path d="M12 11l4-1" />
    </Svg>
  );
}

export function IconoPin(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 21s7-6.2 7-11a7 7 0 10-14 0c0 4.8 7 11 7 11z" />
      <circle cx="12" cy="10" r="2.2" />
    </Svg>
  );
}

export function IconoTelefono(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M7 3h3l1.5 4-2 1.5a12 12 0 006 6L17 12.5l4 1.5v3a2 2 0 01-2 2A16 16 0 015 7a2 2 0 012-2z" />
    </Svg>
  );
}

export function IconoCorreo(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="5" width="18" height="14" rx="1.5" />
      <path d="M3 7l9 7 9-7" />
    </Svg>
  );
}

export function IconoWeb(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18" />
    </Svg>
  );
}

export function IconoInfo(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </Svg>
  );
}

export function IconoRed(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="7" cy="8" r="2.2" />
      <circle cx="17" cy="8" r="2.2" />
      <circle cx="12" cy="17" r="2.2" />
      <path d="M9 9.2l6 0M8.5 10l2.8 5M15.5 10l-2.8 5" />
    </Svg>
  );
}
