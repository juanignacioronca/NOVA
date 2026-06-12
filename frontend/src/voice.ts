// Entrada de voz por el navegador (Web Speech API / SpeechRecognition).
// Modo MANOS LIBRES: escucha en loop continuo; cada frase que terminás se manda
// a NOVA. Se re-arranca solo si el navegador corta por silencio. Se PAUSA mientras
// NOVA habla (para no transcribir su propia voz). STT 100% del navegador ($0).

type Cb = (t: string) => void;
type StateCb = (escuchando: boolean) => void;

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start(): void;
  stop(): void;
  onresult: ((e: any) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: any) => void) | null;
}

export class VoiceInput {
  private rec: SpeechRecognitionLike | null = null;
  escuchando = false; // hay reconocimiento activo ahora
  continuo = false; // modo manos libres encendido
  private pausado = false; // pausado mientras NOVA habla
  onFinal: Cb = () => {};
  onInterim: Cb = () => {};
  onState: StateCb = () => {};

  disponible(): boolean {
    return "webkitSpeechRecognition" in window || "SpeechRecognition" in window;
  }

  /** Enciende/apaga el modo manos libres. */
  toggle() {
    if (this.continuo) this.detener();
    else this.iniciar();
  }

  iniciar() {
    if (!this.disponible()) return;
    this.continuo = true;
    this.pausado = false;
    this.arrancar();
  }

  detener() {
    this.continuo = false;
    this.pausado = false;
    try { this.rec?.stop(); } catch { /* noop */ }
    this.escuchando = false;
    this.onState(false);
  }

  /** Pausa temporal (mientras NOVA habla). No apaga el modo manos libres. */
  pausar() {
    this.pausado = true;
    try { this.rec?.stop(); } catch { /* noop */ }
  }

  /** Reanuda tras la pausa (cuando NOVA terminó de hablar). */
  reanudar() {
    if (!this.pausado) return;
    this.pausado = false;
    if (this.continuo) this.arrancar();
  }

  private arrancar() {
    if (!this.continuo || this.pausado || this.escuchando) return;
    const SR =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    const rec: SpeechRecognitionLike = new SR();
    rec.lang = "es-AR";
    rec.interimResults = true;
    rec.continuous = true;
    rec.onresult = (e: any) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) {
          const t = (r[0].transcript || "").trim();
          if (t) this.onFinal(t);
        } else {
          interim += r[0].transcript;
        }
      }
      if (interim.trim()) this.onInterim(interim.trim());
    };
    rec.onend = () => {
      this.escuchando = false;
      this.onState(false);
      // re-arranca solo si seguimos en manos libres y no estamos pausados
      if (this.continuo && !this.pausado) setTimeout(() => this.arrancar(), 250);
    };
    rec.onerror = (e: any) => {
      // 'no-speech'/'aborted' son normales; onend re-arranca. 'not-allowed' = sin permiso.
      if (e && e.error === "not-allowed") this.detener();
    };
    this.rec = rec;
    this.escuchando = true;
    this.onState(true);
    try {
      rec.start();
    } catch {
      this.escuchando = false;
    }
  }
}
