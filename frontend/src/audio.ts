// Motor de audio: reproduce el TTS que llega del backend y expone su "nivel"
// (amplitud) vía AnalyserNode para mover a NOVA. Si no hay audio (sin Piper),
// usa un envolvente sintético para que igual se vea hablar. Barge-in básico por mic.
import { ttsUrl } from "./config";

export class AudioEngine {
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private freq = new Uint8Array(0); // inferido Uint8Array<ArrayBuffer>
  private source: AudioBufferSourceNode | null = null;
  private nivelSuave = 0;
  private synthHasta = 0;
  private synthDesde = 0;
  private generacion = 0; // para cancelar colas al hacer stop
  hablando = false;
  onBargeIn: (() => void) | null = null;

  /** Se llama desde un gesto del usuario (autoplay policy). */
  resume() {
    this.ensure();
    this.ctx?.resume();
  }

  private ensure() {
    if (this.ctx) return;
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.ctx = new Ctx();
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.smoothingTimeConstant = 0.8;
    this.analyser.connect(this.ctx.destination);
    this.freq = new Uint8Array(this.analyser.frequencyBinCount);
  }

  /** Reproduce una lista de frases en orden (TTS streaming). */
  async hablar(frases: string[]) {
    this.ensure();
    this.stop();
    const gen = ++this.generacion;
    this.hablando = true;
    for (const frase of frases) {
      if (gen !== this.generacion) break;
      await this.reproducirFrase(frase, gen);
    }
    if (gen === this.generacion) this.hablando = false;
  }

  private async reproducirFrase(frase: string, gen: number) {
    if (!frase.trim()) return;
    try {
      const resp = await fetch(ttsUrl(frase));
      if (resp.status === 200 && this.ctx && this.analyser) {
        const buf = await this.ctx.decodeAudioData(await resp.arrayBuffer());
        if (gen !== this.generacion) return;
        await this.reproducirBuffer(buf, gen);
        return;
      }
    } catch {
      /* sin red / sin Piper → envolvente sintético */
    }
    await this.envolventeSintetico(frase, gen);
  }

  private reproducirBuffer(buf: AudioBuffer, gen: number): Promise<void> {
    return new Promise((resolve) => {
      if (!this.ctx || !this.analyser) return resolve();
      const src = this.ctx.createBufferSource();
      src.buffer = buf;
      src.connect(this.analyser);
      src.onended = () => resolve();
      this.source = src;
      src.start();
      // Si hacen stop, cortamos.
      const watch = setInterval(() => {
        if (gen !== this.generacion) {
          try { src.stop(); } catch { /* ya parado */ }
          clearInterval(watch);
          resolve();
        }
      }, 60);
    });
  }

  private envolventeSintetico(frase: string, gen: number): Promise<void> {
    const palabras = Math.max(1, frase.split(/\s+/).length);
    const dur = Math.min(6000, 350 + palabras * 280);
    this.synthDesde = performance.now();
    this.synthHasta = this.synthDesde + dur;
    return new Promise((resolve) => {
      const t = setInterval(() => {
        if (gen !== this.generacion || performance.now() >= this.synthHasta) {
          clearInterval(t);
          resolve();
        }
      }, 60);
    });
  }

  stop() {
    this.generacion++;
    this.hablando = false;
    this.synthHasta = 0;
    if (this.source) {
      try { this.source.stop(); } catch { /* ya parado */ }
      this.source = null;
    }
  }

  /** Nivel 0..1 (suavizado) para la visualización. */
  nivel(): number {
    let n = 0;
    if (this.analyser) {
      this.analyser.getByteFrequencyData(this.freq);
      let s = 0;
      for (let i = 0; i < this.freq.length; i++) s += this.freq[i];
      n = s / (this.freq.length * 255);
    }
    const ahora = performance.now();
    if (ahora < this.synthHasta) {
      const fase = (ahora - this.synthDesde) / 140;
      const env = 0.35 + 0.3 * Math.abs(Math.sin(fase)) + 0.15 * Math.abs(Math.sin(fase * 0.37));
      n = Math.max(n, env);
    }
    this.nivelSuave += (n - this.nivelSuave) * 0.25;
    return this.nivelSuave;
  }

  /** Barge-in: si el usuario habla mientras NOVA habla, dispara onBargeIn. */
  async habilitarMic() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.ensure();
      if (!this.ctx) return;
      const mic = this.ctx.createMediaStreamSource(stream);
      const an = this.ctx.createAnalyser();
      an.fftSize = 256;
      mic.connect(an);
      const data = new Uint8Array(an.frequencyBinCount);
      setInterval(() => {
        an.getByteFrequencyData(data);
        let s = 0;
        for (let i = 0; i < data.length; i++) s += data[i];
        const rms = s / (data.length * 255);
        if (this.hablando && rms > 0.22) {
          this.stop();
          this.onBargeIn?.();
        }
      }, 120);
    } catch {
      /* sin permiso de mic → sin barge-in (degrada) */
    }
  }
}
