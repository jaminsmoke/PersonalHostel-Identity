type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult:
    | ((event: {
        results: ArrayLike<ArrayLike<{ transcript: string }>>;
      }) => void)
    | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

export type ResultadoEscucha = {
  texto: string;
  error?: string;
};

function ctor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

export function vozDisponible(): boolean {
  return ctor() !== null && Boolean(window.isSecureContext);
}

export function escucharUnaFrase(): Promise<ResultadoEscucha> {
  const Ctor = ctor();
  if (!Ctor) {
    return Promise.resolve({
      texto: "",
      error: "Voz no disponible en este navegador",
    });
  }
  return new Promise((resolve) => {
    const rec = new Ctor();
    let cerrado = false;
    const fin = (resultado: ResultadoEscucha) => {
      if (cerrado) return;
      cerrado = true;
      try {
        rec.stop();
      } catch {
        /* ya parado */
      }
      resolve(resultado);
    };
    rec.lang = "es-ES";
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (event) => {
      fin({ texto: event.results[0]?.[0]?.transcript ?? "" });
    };
    rec.onerror = (event) => {
      fin({ texto: "", error: event.error });
    };
    rec.onend = () => {
      fin({ texto: "", error: "sin_audio" });
    };
    try {
      rec.start();
    } catch {
      fin({ texto: "", error: "no_se_pudo_iniciar" });
    }
  });
}
