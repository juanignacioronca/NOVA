// Cámara en modo CENTINELA: la previsualización es local (getUserMedia, no se sube
// nada por defecto). Un loop muestrea cuadros todo el tiempo y calcula la diferencia
// con el cuadro anterior; la MAYORÍA del tiempo no pasa nada. Solo cuando hay un
// cambio relevante (movimiento / alguien aparece) dispara `onCambio` con una foto,
// y con un enfriamiento para no saturar el modelo de visión (GPU 6 GB).

type CambioCb = (dataUrl: string) => void;
type EstadoCb = (vigilando: boolean, nivel: number) => void;

export class CameraView {
  el: HTMLElement;
  private video: HTMLVideoElement;
  private label: HTMLElement;
  private stream: MediaStream | null = null;
  activa = false;

  // sentinela
  onCambio: CambioCb = () => {};
  onEstado: EstadoCb = () => {};
  private timer: number | null = null;
  private prev: ImageData | null = null;
  private small = document.createElement("canvas"); // muestreo chico (rápido)
  private ultimoEnvio = 0;
  private umbral = 0.06; // 6% de píxeles cambiados → "algo pasó"
  private enfriamientoMs = 15000; // mínimo entre avisos al backend (protege la GPU)
  private intervaloMs = 700; // cada cuánto muestrea

  constructor() {
    this.el = document.createElement("div");
    this.el.className = "cambox";
    this.el.hidden = true;
    this.video = document.createElement("video");
    this.video.autoplay = true;
    this.video.muted = true;
    this.video.playsInline = true;
    this.label = document.createElement("div");
    this.label.className = "camlabel";
    this.label.textContent = "cámara · local";
    this.small.width = 64;
    this.small.height = 48;
    this.el.append(this.video, this.label);
  }

  async toggle(): Promise<boolean> {
    if (this.activa) {
      this.stop();
      return false;
    }
    return this.start();
  }

  async start(): Promise<boolean> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ video: true });
      this.video.srcObject = this.stream;
      this.el.hidden = false;
      this.activa = true;
      this.prev = null;
      this.vigilar();
      return true;
    } catch {
      this.activa = false;
      return false;
    }
  }

  stop() {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.video.srcObject = null;
    this.el.hidden = true;
    this.activa = false;
    this.onEstado(false, 0);
  }

  // --- loop centinela ---
  private vigilar() {
    if (this.timer) clearInterval(this.timer);
    this.timer = window.setInterval(() => this.tick(), this.intervaloMs);
  }

  private tick() {
    if (!this.activa || !this.video.videoWidth) return;
    const ctx = this.small.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;
    ctx.drawImage(this.video, 0, 0, this.small.width, this.small.height);
    const cur = ctx.getImageData(0, 0, this.small.width, this.small.height);

    let nivel = 0;
    if (this.prev) {
      let cambiados = 0;
      const a = cur.data, b = this.prev.data;
      for (let i = 0; i < a.length; i += 4) {
        const d = Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]);
        if (d > 60) cambiados++;
      }
      nivel = cambiados / (a.length / 4);
    }
    this.prev = cur;

    if (nivel > this.umbral) {
      this.label.textContent = "● movimiento";
      const ahora = performance.now();
      if (ahora - this.ultimoEnvio > this.enfriamientoMs) {
        this.ultimoEnvio = ahora;
        const foto = this.capturar();
        if (foto) this.onCambio(foto);
      }
    } else {
      this.label.textContent = "vigilando…";
    }
    this.onEstado(true, nivel);
  }

  /** Captura un fotograma como dataURL (JPEG) para enviar al backend. */
  capturar(): string | null {
    if (!this.activa || !this.video.videoWidth) return null;
    const c = document.createElement("canvas");
    // limitar tamaño para no mandar imágenes enormes por el WS
    const escala = Math.min(1, 640 / this.video.videoWidth);
    c.width = Math.round(this.video.videoWidth * escala);
    c.height = Math.round(this.video.videoHeight * escala);
    c.getContext("2d")?.drawImage(this.video, 0, 0, c.width, c.height);
    return c.toDataURL("image/jpeg", 0.6);
  }
}
