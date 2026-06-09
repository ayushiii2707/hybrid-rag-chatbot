import { useRef, useMemo, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import {
  PARTICLE_COUNT,
  generateWave,
  generateStars,
  generateWaveColors,
  generateStarColors
} from '../lib/particles';

const STAR_COUNT = 3000;

function createCircleTexture(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const r = size / 2;
  const gradient = ctx.createRadialGradient(r, r, 0, r, r, r);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.3, 'rgba(255,255,255,0.9)');
  gradient.addColorStop(0.6, 'rgba(255,255,255,0.4)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

function createSmallCircleTexture(): THREE.Texture {
  const size = 32;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const r = size / 2;
  const gradient = ctx.createRadialGradient(r, r, 0, r, r, r);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.4, 'rgba(255,255,255,0.5)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

function Particles({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const meshRef = useRef<THREE.Points>(null);
  const timeRef = useRef(0);

  // Generate initial static coordinate templates
  const initialPositions = useMemo(() => generateWave(PARTICLE_COUNT), []);
  const colors = useMemo(() => generateWaveColors(PARTICLE_COUNT), []);

  const texture = useMemo(() => createCircleTexture(), []);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(initialPositions), 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    return geo;
  }, [initialPositions, colors]);

  const material = useMemo(() => new THREE.PointsMaterial({
    size: 0.042,
    map: texture,
    vertexColors: true,
    transparent: true,
    opacity: 0.92,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true,
  }), [texture]);

  useFrame((_, delta) => {
    timeRef.current += delta;
    const scroll = scrollRef.current;

    if (meshRef.current) {
      const geo = meshRef.current.geometry;
      const positions = geo.attributes.position.array as Float32Array;
      const time = timeRef.current * 0.8; // speed of undulation

      // Compute and update Y values dynamically for real-time wave undulation
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const x = initialPositions[i * 3];
        const z = initialPositions[i * 3 + 2];

        const waveY = Math.sin(x * 0.6 + time) * Math.cos(z * 0.5 + time * 0.5) * 1.0
          + Math.sin(x * 0.3 - time * 0.2) * 0.5
          + Math.cos(z * 0.8 + x * 0.2 + time * 0.4) * 0.4;

        // Use a static deterministic jitter offset to avoid flickering
        const jitter = Math.sin(i * 133.7) * 0.04;
        positions[i * 3 + 1] = waveY + jitter - 1.2;
      }
      geo.attributes.position.needsUpdate = true;

      // Map scroll progress to mesh tilt and rotation
      meshRef.current.rotation.x = -0.20 + (scroll * 0.15);
      meshRef.current.rotation.y = timeRef.current * 0.04 + (scroll * 0.3);
    }
  });

  return <points ref={meshRef} geometry={geometry} material={material} />;
}

function Stars() {
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const positions = generateStars(STAR_COUNT);
    const colors = generateStarColors(STAR_COUNT);
    const sizes = new Float32Array(STAR_COUNT);
    for (let i = 0; i < STAR_COUNT; i++) {
      sizes[i] = Math.random() < 0.05 ? 0.08 : 0.025 + Math.random() * 0.03;
    }
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    return geo;
  }, []);

  const texture = useMemo(() => createSmallCircleTexture(), []);

  const material = useMemo(() => new THREE.PointsMaterial({
    size: 0.04,
    map: texture,
    vertexColors: true,
    transparent: true,
    opacity: 0.85,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true,
  }), [texture]);

  const ref = useRef<THREE.Points>(null);
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.005;
  });

  return <points ref={ref} geometry={geometry} material={material} />;
}

function CameraController({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const { camera } = useThree();
  useFrame(() => {
    const scroll = scrollRef.current;
    // Camera zooms out slightly and tilts upwards as user scrolls
    const targetZ = 9.0 + (scroll * 2.0);
    const targetY = -1.1 + (scroll * 0.8);
    camera.position.z += (targetZ - camera.position.z) * 0.04;
    camera.position.y += (targetY - camera.position.y) * 0.04;
  });
  return null;
}

/** Dynamically toggles canvas background transparency based on theme */
function ClearColorController({ theme }: { theme: 'dark' | 'light' }) {
  const { gl } = useThree();
  useEffect(() => {
    if (theme === 'light') {
      gl.setClearColor(new THREE.Color('#000008'), 0);
    } else {
      gl.setClearColor(new THREE.Color('#000008'), 1);
    }
  }, [theme, gl]);
  return null;
}

function isWebGLAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    );
  } catch {
    return false;
  }
}

interface ThreeSceneProps {
  scrollRef: React.MutableRefObject<number>;
  theme?: 'dark' | 'light';
}

export default function ThreeScene({ scrollRef, theme = 'dark' }: ThreeSceneProps) {
  if (!isWebGLAvailable()) return null;

  return (
    <Canvas
      style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', zIndex: 1 }}
      camera={{ position: [0, 0, 9], fov: 55 }}
      gl={{ antialias: true, alpha: true }}
      onCreated={({ gl }) => {
        gl.setClearColor(new THREE.Color('#000008'), 1);
        gl.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      }}
    >
      <ClearColorController theme={theme} />
      <Stars />
      <Particles scrollRef={scrollRef} />
      <CameraController scrollRef={scrollRef} />
    </Canvas>
  );
}
