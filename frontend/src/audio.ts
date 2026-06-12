// Motor de audio: reproduce la voz de NOVA y expone su "nivel" (amplitud) para
// mover la esfera. Dos caminos de voz, en orden:
//   1) /tts (Piper) → audio real + análisis FFT (la esfera baila con la onda).
//   2) speechSynthesis del navegador → voz audible sin instalar nada ($0), con
//      una envolvente sintética para que la esfera igual se mueva.
// Barge-in básico por mic. micNivel() mueve la esfera mientras vos hablás.
import { ttsUrl } from "./config";

export class AudioEngine {
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private freq = new Uint8Array(0);
  private source: AudioBufferSourceNode | null = null;
  private nivelSuave = 0;
  private synthActivo = false; // hablando por el navegador (envolvente)
  private generacion = 0; // para cancelar colas al hacer stop
  private micRms = 0;
  private voz: SpeechSynthesisVoice | null = null;
  hablando = false;
  onBargeIn: (() => void) | null = null;
  onHablarInicio: (() => void) | null = null;
  onHablarFin: (() => void) | null = null;

  constructor() {
    this.cargarVoz();
  }

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

  // --- selección de voz en español del navegador ---
  private cargarVoz() {
    if (!("speechSynthesis" in window)) return;
    const pick = () => {
      const vs = window.speechSynthesis.getVoices();
      this.voz =
        vs.find((v) => /^es(-|_)?(419|MX|AR|US)?/i.test(v.lang)) ||
        vs.find((v) => /^es/i.test(v.lang)) ||
        vs[0] ||
        null;
    };
    pick();
    if (!this.voz) window.speechSynthesis.onvoiceschanged = pick;
  }

  /** Reproduce una lista de frases en orden (TTS streaming). */
  async hablar(frases: string[]) {
    this.ensure();
    this.stop();
    const gen = ++this.generacion;
    this.hablando = true;
    this.onHablarInicio?.();
    for (const frase of frases) {
      if (gen !== this.generacion) break;
      await this.reproducirFrase(frase, gen);
    }
    if (gen === this.generacion) {
      this.hablando = false;
      this.onHablarFin?.();
    }
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
      /* sin red / sin Piper → voz del navegador */
    }
    await this.hablarNavegador(frase, gen);
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
      const watch = setInterval(() => {
        if (gen !== this.generacion) {
          try { src.stop(); } catch { /* ya parado */ }
          clearInterval(watch);
          resolve();
        }
      }, 60);
    });
  }

  /** Voz audible por el navegador (speechSynthesis). Mueve la esfera con envolvente. */
  private hablarNavegador(frase: string, gen: number): Promise<void> {
    return new Promise((resolve) => {
      if (!("speechSynthesis" in window) || !frase.trim()) return resolve();
      const u = new SpeechSynthesisUtterance(frase);
      if (this.voz) u.voice = this.voz;
      u.lang = this.voz?.lang || "es-ES";
      u.rate = 1.03;
      u.pitch = 1.0;
      let done = false;
      const fin = () => {
        if (done) return;
        done = true;
        this.synthActivo = false;
        clearInterval(watch);
        resolve();
      };
      u.onstart = () => { this.synthActivo = true; };
      u.onend = fin;
      u.onerror = fin;
      const watch = setInterval(() => {
        if (gen !== this.generacion) {
          try { window.speechSynthesis.cancel(); } catch { /* noop */ }
          fin();
        }
      }, 80);
      try {
        window.speechSynthesis.cancel(); // limpia cola previa
        window.speechSynthesis.speak(u);
      } catch {
        fin();
      }
    });
  }

  stop() {
    this.generacion++;
    this.hablando = false;
    this.synthActivo = false;
    try { window.speechSynthesis.cancel(); } catch { /* noop */ }
    if (this.source) {
      try { this.source.stop(); } catch { /* ya parado */ }
      this.source = null;
    }
    this.onHablarFin?.();
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
    if (this.synthActivo) {
      const fase = performance.now() / 130;
      const env = 0.4 + 0.28 * Math.abs(Math.sin(fase)) + 0.16 * Math.abs(Math.sin(fase * 0.37));
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
        this.micRms = rms;
        if (this.hablando && rms > 0.22) {
          this.stop();
          this.onBargeIn?.();
        }
      }, 120);
    } catch {
      /* sin permiso de mic → sin barge-in (degrada) */
    }
  }

  /** Nivel del micrófono 0..1 (para mover la esfera mientras el usuario habla). */
  micNivel(): number {
    return this.micRms;
  }
}
