// NOVA audio-reactiva: una esfera/supernova Three.js que pulsa y morfea con el
// nivel de la voz (amplitud del AnalyserNode). Idle en silencio, activa al hablar.
import * as THREE from "three";

const CYAN = new THREE.Color("#37d0ea");
const VIOLET = new THREE.Color("#b48cff");

export class Supernova {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private malla: THREE.Mesh;
  private nucleo: THREE.Mesh;
  private halo: THREE.Points;
  private base: Float32Array;
  private fases: Float32Array;
  private nivel = 0;
  private t = 0;
  private cont: HTMLElement;

  constructor(cont: HTMLElement) {
    this.cont = cont;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    cont.appendChild(this.renderer.domElement);

    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    this.camera.position.z = 3.2;

    // Cuerpo: icosaedro wireframe que se deforma con la voz.
    const geo = new THREE.IcosahedronGeometry(1, 5);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    this.base = (pos.array as Float32Array).slice();
    this.fases = new Float32Array(pos.count);
    for (let i = 0; i < pos.count; i++) this.fases[i] = Math.random() * Math.PI * 2;
    const mat = new THREE.MeshBasicMaterial({ color: CYAN, wireframe: true, transparent: true, opacity: 0.85 });
    this.malla = new THREE.Mesh(geo, mat);
    this.scene.add(this.malla);

    // Núcleo interior tenue.
    this.nucleo = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.62, 3),
      new THREE.MeshBasicMaterial({ color: CYAN, transparent: true, opacity: 0.12 })
    );
    this.scene.add(this.nucleo);

    // Halo de partículas (supernova).
    const N = 1400;
    const hp = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const r = 1.25 + Math.random() * 0.9;
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(2 * Math.random() - 1);
      hp[i * 3] = r * Math.sin(ph) * Math.cos(th);
      hp[i * 3 + 1] = r * Math.sin(ph) * Math.sin(th);
      hp[i * 3 + 2] = r * Math.cos(ph);
    }
    const hg = new THREE.BufferGeometry();
    hg.setAttribute("position", new THREE.BufferAttribute(hp, 3));
    this.halo = new THREE.Points(
      hg,
      new THREE.PointsMaterial({ color: VIOLET, size: 0.02, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    this.scene.add(this.halo);

    new ResizeObserver(() => this.resize()).observe(cont);
    this.resize();
    this.renderer.setAnimationLoop(() => this.frame());
  }

  setNivel(n: number) {
    this.nivel = Math.max(0, Math.min(1, n));
  }

  private resize() {
    const w = this.cont.clientWidth || 1;
    const h = this.cont.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  private frame() {
    this.t += 0.016;
    const lvl = this.nivel;
    const geo = this.malla.geometry as THREE.BufferGeometry;
    const pos = geo.attributes.position as THREE.BufferAttribute;
    const arr = this.base;
    for (let i = 0; i < pos.count; i++) {
      const ox = arr[i * 3], oy = arr[i * 3 + 1], oz = arr[i * 3 + 2];
      const ph = this.fases[i];
      const disp =
        1 +
        0.035 * Math.sin(this.t * 1.6 + ph) +
        lvl * 0.55 * (0.5 + 0.5 * Math.sin(this.t * 7 + ph * 2.3));
      pos.setXYZ(i, ox * disp, oy * disp, oz * disp);
    }
    pos.needsUpdate = true;

    const escala = 1 + lvl * 0.18;
    this.nucleo.scale.setScalar(escala);
    this.malla.rotation.y += 0.0024 + lvl * 0.02;
    this.malla.rotation.x += 0.0009;
    this.halo.rotation.y -= 0.0012 + lvl * 0.01;

    const m = this.malla.material as THREE.MeshBasicMaterial;
    m.color.copy(CYAN).lerp(VIOLET, lvl * 0.5);
    m.opacity = 0.7 + lvl * 0.3;
    (this.halo.material as THREE.PointsMaterial).opacity = 0.35 + lvl * 0.5;

    this.renderer.render(this.scene, this.camera);
  }
}
