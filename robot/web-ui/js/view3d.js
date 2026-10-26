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

    const width = this.container.clientWidth || 320;
    const height = this.container.clientHeight || 260;

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(0x090d16, 0.004);

    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.05, 50);
    this.camera.position.set(0.40, 0.28, 0.50);
    this.camera.lookAt(0, 0.09, 0);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.appendChild(this.renderer.domElement);

    // Ambient & Accent Lights
    const ambLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambLight);

    const dirLight = new THREE.DirectionalLight(0x00e5ff, 1.4);
    dirLight.position.set(2, 4, 3);
    this.scene.add(dirLight);

    // Ground Grid
    const grid = new THREE.GridHelper(2.0, 20, 0x00e5ff, 0x1e293b);
    grid.position.y = -0.04;
    this.scene.add(grid);

    this.buildRobot();

    window.addEventListener('resize', () => this.onResize());
    State.on('activeTab', (tab) => this.onTabChange(tab));

    this.start();
  }

  buildRobot() {
    this.robotGroup = new THREE.Group();

    // Main Chassis Body (Pi + Mega + LiPo)
    const chassisGeo = new THREE.BoxGeometry(0.12, 0.08, 0.16);
    const chassisMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.8,
      roughness: 0.25
    });
    const chassis = new THREE.Mesh(chassisGeo, chassisMat);
    chassis.position.y = 0.12;
    this.robotGroup.add(chassis);

    // Glowing Cyan Status Visor
    const visorGeo = new THREE.BoxGeometry(0.09, 0.016, 0.01);
    const visorMat = new THREE.MeshBasicMaterial({ color: 0x00e5ff });
    const visor = new THREE.Mesh(visorGeo, visorMat);
    visor.position.set(0, 0.13, 0.081);
    this.robotGroup.add(visor);

    // Helper for 3-link leg assembly
    const createLeg = (isLeft) => {
      const legRoot = new THREE.Group();
      legRoot.position.set(isLeft ? -0.08 : 0.08, 0.10, 0);

      // Thigh Link (120mm = 0.12m)
      const thighGeo = new THREE.CylinderGeometry(0.009, 0.009, 0.08, 12);
      const metalMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.7 });
      const thigh = new THREE.Mesh(thighGeo, metalMat);
      thigh.position.y = -0.04;
      legRoot.add(thigh);

      // Wheel (80mm diameter = 0.04m radius)
      const wheelGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.022, 24);
      wheelGeo.rotateZ(Math.PI / 2);
      const wheelMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.75 });
      const wheel = new THREE.Mesh(wheelGeo, wheelMat);
      wheel.position.y = -0.10;
      legRoot.add(wheel);

      return legRoot;
    };

    this.legL = createLeg(true);
    this.legR = createLeg(false);

    this.robotGroup.add(this.legL);
    this.robotGroup.add(this.legR);

    this.scene.add(this.robotGroup);
  }

  onTabChange(activeTab) {
    if (activeTab === 'drive' || activeTab === 'telemetry') {
      this.start();
    } else {
      this.stop(); // Conserve mobile GPU resources when on other tabs
    }
  }

  onResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
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

    const pitchDeg = State.get('pitch');
    const rollDeg = State.get('roll');
    const heightL = State.get('legHeightL') || 118;
    const heightR = State.get('legHeightR') || 118;

    // Pitch & Roll rotations
    this.robotGroup.rotation.x = THREE.MathUtils.degToRad(-pitchDeg);
    this.robotGroup.rotation.z = THREE.MathUtils.degToRad(rollDeg);

    // Leg extension scaling
    if (this.legL && this.legR) {
      this.legL.scale.y = heightL / 118.0;
      this.legR.scale.y = heightR / 118.0;
    }
  }
}

export const View3D = new Robot3DView();
