export interface HorarioTurno {
  abre: string;
  cierra: string;
}

export interface HorarioDia {
  dia_semana: number;
  cerrado: boolean;
  turnos: HorarioTurno[];
}

export interface ProductoPublico {
  nombre: string;
  precio_centimos: number;
  moneda: string;
  destino: "barra" | "cocina";
  descripcion?: string | null;
}

export interface CategoriaCarta {
  nombre: string;
  productos: ProductoPublico[];
}

export interface PerfilSeccion {
  eslogan?: string | null;
  descripcion?: string | null;
  direccion?: string | null;
  ciudad?: string | null;
}

export interface ContactoSeccion {
  telefono?: string | null;
  email_contacto?: string | null;
  web?: string | null;
  redes: Record<string, string>;
}

export interface HeroSeccion {
  url: string;
}

export interface ImagenGaleria {
  id: string;
  url: string;
}

export interface AbiertoAhora {
  abierto: boolean;
  proximo_cambio?: string | null;
}

export interface MiembroEquipo {
  camarero_id: string;
  nombre: string;
  apellidos: string;
  nick?: string | null;
  foto_url?: string | null;
  rol: string;
}

export interface WebNegocio {
  establecimiento_id: string;
  nombre: string;
  tipo_establecimiento?: string | null;
  logo_url?: string | null;
  organizacion_nombre: string;
  plantilla: string;
  color_primario?: string | null;
  perfil?: PerfilSeccion | null;
  contacto?: ContactoSeccion | null;
  hero?: HeroSeccion | null;
  galeria: ImagenGaleria[];
  abierto_ahora?: AbiertoAhora | null;
  horario?: HorarioDia[] | null;
  equipo: MiembroEquipo[];
  categorias: CategoriaCarta[];
}

export interface ErrorWeb {
  code: string;
  detail: string;
}