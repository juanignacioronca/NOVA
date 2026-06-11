// Cliente WebSocket robusto (reconecta solo). Degrada si el backend no responde.
import { WS_URL } from "./config";
import type { Modalidad, ServerMsg } from "./types";

type MsgHandler = (msg: ServerMsg) => void;
type StatusHandler = (online: boolean) => void;

export class NovaSocket {
  private ws: WebSocket | null = null;
  private onMsg: MsgHandler;
  private onStatus: StatusHandler;
  private reintentos = 0;

  constructor(onMsg: MsgHandler, onStatus: StatusHandler) {
    this.onMsg = onMsg;
    this.onStatus = onStatus;
    this.connect();
  }

  private connect() {
    try {
      this.ws = new WebSocket(WS_URL);
    } catch {
      this.reconnect();
      return;
    }
    this.ws.onopen = () => {
      this.reintentos = 0;
      this.onStatus(true);
    };
    this.ws.onclose = () => {
      this.onStatus(false);
      this.reconnect();
    };
    this.ws.onerror = () => this.ws?.close();
    this.ws.onmessage = (e) => {
      try {
        this.onMsg(JSON.parse(e.data) as ServerMsg);
      } catch {
        /* mensaje no-JSON: lo ignoramos */
      }
    };
  }

  private reconnect() {
    this.reintentos = Math.min(this.reintentos + 1, 6);
    setTimeout(() => this.connect(), 500 * this.reintentos);
  }

  private send(obj: unknown) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  enviarTexto(texto: string) {
    this.send({ type: "text", text: texto });
  }
  enviarModalidad(value: Modalidad) {
    this.send({ type: "modalidad", value });
  }
  enviarStop() {
    this.send({ type: "stop" });
  }
}
