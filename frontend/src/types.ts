// Contrato del WS con el backend (Prompts 3/5/9).
export type Modalidad = "voz" | "pantalla" | "ambos";

export interface TraceEvent {
  type: "trace";
  etapa: string;
  agente: string;
  grupo: string;
  modelo: string;
  detalle: string;
  estado: string;
  ts: number;
}

export interface Resultado {
  tipo: "tarjeta" | "itinerario" | "tabla" | "pregunta" | "texto";
  titulo: string;
  texto?: string;
  cuerpo?: string;
  color?: string;
  pasos?: Array<{
    n: number;
    area: string;
    descripcion: string;
    finanzas?: boolean;
    estrategia?: boolean;
  }>;
}

export interface Presentacion {
  type: "presentacion";
  modalidad: Modalidad;
  texto: string;
  voz: string;
  proceso: TraceEvent[];
  resultado: Resultado;
  meta: { route?: string; intent?: string; model?: string; memoria?: string[] };
}

export interface VozMsg {
  type: "voz";
  frases: string[];
}

export interface Answer {
  type: "answer";
  text: string;
  route: string;
  model: string;
}

export type ServerMsg =
  | TraceEvent
  | Presentacion
  | VozMsg
  | Answer
  | { type: string; [k: string]: unknown };
