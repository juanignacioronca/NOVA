// URLs del backend. En dev, Vite proxea /ws y /tts al backend local (mismo origen).
export const WS_URL =
  (location.protocol === "https:" ? "wss" : "ws") + "://" + location.host + "/ws";

export const ttsUrl = (texto: string) => "/tts?text=" + encodeURIComponent(texto);
