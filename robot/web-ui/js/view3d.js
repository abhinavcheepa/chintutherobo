/**
 * Bundled Three.js 3D Digital Twin Visualizer.
 * Clean resource disposal and pause/resume lifecycle to preserve mobile battery.
 */

import { State } from './state.js';

class Robot3DView {
  constructor() {
    this.container = null;
    this.scene = null;
    this.camera = null;
    this.renderer = null;

    this.robotGroup = null;
    this.legL = null;
    this.legR = null;

    this.animFrameId = null;
    this.isRunning = false;
  }

  init() {
    this.container = document.getElementById('three-viewport');
    if (!this.container || typeof THREE === 'undefined') {
      console.warn('Three.js container or library not initialized.');
      return;
    }

    const width = this.container.clientWidth || 450;
    const height = this.container.clientHeight || 380;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x090d16);

    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.05, 50);
    this.camera.position.set(0.36, 0.22, 0.44);
    this.camera.lookAt(0, 0.07, 0);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.appendChild(this.renderer.domElement);

    // Ambient Light
    const ambLight = new THREE.AmbientLight(0xffffff, 0.85);
    this.scene.add(ambLight);

    // Key Light
    const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight1.position.set(2, 4, 3);
    this.scene.add(dirLight1);

    // Cyan Fill / Accent Light
    const dirLight2 = new THREE.DirectionalLight(0x00e5ff, 1.0);
    dirLight2.position.set(-2, 1, -2);
    this.scene.add(dirLight2);

    // Ground Grid
    const grid = new THREE.GridHelper(1.6, 16, 0x00e5ff, 0x1e293b);
    grid.position.y = -0.04;
    this.scene.add(grid);

    this.buildRobot();

    window.addEventListener('resize', () => this.onResize());
    State.on('activeTab', (tab) => this.onTabChange(tab));

    this.start();
  }

  buildRobot() {
    this.robotGroup = new THREE.Group();

    // 1. Main Chassis Body (Upper Torso)
    const chassisGeo = new THREE.BoxGeometry(0.12, 0.07, 0.16);
    const chassisMat = new THREE.MeshStandardMaterial({
      color: 0x0ea5e9, // Bright vibrant tech cyan-blue
      metalness: 0.6,
      roughness: 0.25
    });
    const chassis = new THREE.Mesh(chassisGeo, chassisMat);
    chassis.position.y = 0.10;
    this.robotGroup.add(chassis);

    // Electronics & Battery Pack on top
    const topPackGeo = new THREE.BoxGeometry(0.09, 0.035, 0.12);
    const topPackMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.8,
      roughness: 0.3
    });
    const topPack = new THREE.Mesh(topPackGeo, topPackMat);
    topPack.position.set(0, 0.145, 0);
    this.robotGroup.add(topPack);

    // Glowing Cyan Status Visor / Eyes
    const visorGeo = new THREE.BoxGeometry(0.08, 0.016, 0.01);
    const visorMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff });
    const visor = new THREE.Mesh(visorGeo, visorMat);
    visor.position.set(0, 0.105, 0.082);
    this.robotGroup.add(visor);

    // Rear Status LED
    const ledGeo = new THREE.SphereGeometry(0.008, 12, 12);
    const ledMat = new THREE.MeshBasicMaterial({ color: 0x10b981 });
    const led = new THREE.Mesh(ledGeo, ledMat);
    led.position.set(0, 0.105, -0.082);
    this.robotGroup.add(led);

    // 2. Helper for 3-link leg assembly
    const createLeg = (isLeft) => {
      const legRoot = new THREE.Group();
      const xPos = isLeft ? -0.075 : 0.075;
      legRoot.position.set(xPos, 0.08, 0);

      // Hip Actuator Bracket
      const hipBracketGeo = new THREE.BoxGeometry(0.025, 0.03, 0.03);
      const bracketMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.7 });
      const hipBracket = new THREE.Mesh(hipBracketGeo, bracketMat);
      legRoot.add(hipBracket);

      // Thigh Link (Aluminum Rod)
      const thighGeo = new THREE.CylinderGeometry(0.007, 0.007, 0.08, 12);
      const metalMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.85, roughness: 0.2 });
      const thigh = new THREE.Mesh(thighGeo, metalMat);
      thigh.position.y = -0.04;
      legRoot.add(thigh);

      // Knee Joint Servo
      const kneeGeo = new THREE.CylinderGeometry(0.012, 0.012, 0.025, 16);
      kneeGeo.rotateZ(Math.PI / 2);
      const kneeMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.6 });
      const knee = new THREE.Mesh(kneeGeo, kneeMat);
      knee.position.y = -0.075;
      legRoot.add(knee);

      // Wheel Rim
      const wheelRimGeo = new THREE.CylinderGeometry(0.035, 0.035, 0.024, 24);
      wheelRimGeo.rotateZ(Math.PI / 2);
      const wheelRimMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, metalness: 0.7, roughness: 0.3 });
      const wheelRim = new THREE.Mesh(wheelRimGeo, wheelRimMat);
      wheelRim.position.y = -0.11;
      legRoot.add(wheelRim);

      // Wheel Tire (Outer Rubber Ring)
      const tireGeo = new THREE.TorusGeometry(0.035, 0.009, 12, 24);
      tireGeo.rotateY(Math.PI / 2);
      const tireMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.9 });
      const tire = new THREE.Mesh(tireGeo, tireMat);
      tire.position.y = -0.11;
      legRoot.add(tire);

      return legRoot;
    };

    this.legL = createLeg(true);
    this.legR = createLeg(false);

    this.robotGroup.add(this.legL);
    this.robotGroup.add(this.legR);

    this.scene.add(this.robotGroup);
  }

  onTabChange(activeTab) {
    if (activeTab === 'telemetry') {
      setTimeout(() => {
        this.onResize();
        this.start();
      }, 50);
    } else if (activeTab === 'drive') {
      this.start();
    } else {
      this.stop();
    }
  }

  onResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    if (w < 20 || h < 20) return;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  start() {
    if (this.isRunning) return;
    this.isRunning = true;
    const loop = () => {
      if (!this.isRunning) return;
      this.updatePose();
      if (this.renderer && this.scene && this.camera) {
        this.renderer.render(this.scene, this.camera);
      }
      this.animFrameId = requestAnimationFrame(loop);
    };
    loop();
  }

  stop() {
    this.isRunning = false;
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
  }

  updatePose() {
    if (!this.robotGroup) return;

    const pitchDeg = State.get('pitch') || 0.0;
    const rollDeg = State.get('roll') || 0.0;
    const heightL = State.get('legHeightL') || 135;
    const heightR = State.get('legHeightR') || 135;

    // Pitch & Roll rotations
    this.robotGroup.rotation.x = THREE.MathUtils.degToRad(-pitchDeg);
    this.robotGroup.rotation.z = THREE.MathUtils.degToRad(rollDeg);

    // Leg extension scaling
    if (this.legL && this.legR) {
      this.legL.scale.y = heightL / 135.0;
      this.legR.scale.y = heightR / 135.0;
    }
  }
}

export const View3D = new Robot3DView();
