"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas, useThree } from "@react-three/fiber";
import { Component, useEffect, useRef, useState, useSyncExternalStore, type ComponentRef, type ReactNode } from "react";

function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", notify);
      return () => list.removeEventListener("change", notify);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

export interface Palette {
  above: string;
  below: string;
  neutral: string;
  third: string;
  line: string;
  ink: string;
  dark: boolean;
}

/** Greyscale: darker is further above the market price, lighter further below. */
const PALETTE: Palette = {
  above: "#111111",
  below: "#cfcfd2",
  neutral: "#7c7c82",
  third: "#96969c",
  line: "#e6e6e6",
  ink: "#0a0a0a",
  dark: false,
};

export function usePalette(): Palette {
  return PALETTE;
}

class Fallback extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <p className="p-6 text-sm text-(--ink-2)">
        3D graphics are not available in this browser. The tables on this page show the same numbers.
      </p>
    ) : (
      this.props.children
    );
  }
}

type View = { position: [number, number, number]; label: string };
const VIEWS: View[] = [
  { label: "Angle", position: [7.2, 5.4, 8] },
  { label: "Front", position: [0, 3, 11] },
  { label: "Side", position: [11, 3, 0] },
  { label: "Top", position: [0, 12, 0.01] },
];

const CHART_VIEW: View = { label: "Angle", position: [2.6, 4.2, 10.6] };

function Controls({ view, spin }: { view: View; spin: boolean }) {
  const camera = useThree((s) => s.camera);
  const invalidate = useThree((s) => s.invalidate);
  const aspect = useThree((s) => s.size.width / s.size.height);
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  useEffect(() => {
    // Step back on narrow (phone) stages so the whole model stays in frame.
    const back = Math.max(1, 1.2 / aspect);
    const [x, y, z] = view.position;
    camera.position.set(x * back, y * back, z * back);
    controls.current?.update();
    invalidate();
  }, [view, camera, invalidate, aspect]);
  return (
    <OrbitControls
      ref={controls}
      autoRotate={spin}
      autoRotateSpeed={0.6}
      enablePan={false}
      enableZoom={false}
      target={[0, 1.2, 0]}
      onStart={() => {
        if (controls.current) controls.current.autoRotate = false;
      }}
    />
  );
}

/** A rotatable 3D stage with keyboard-reachable camera presets. */
export default function Scene({
  label,
  height = 420,
  chart = false,
  children,
}: {
  label: string;
  height?: number;
  chart?: boolean; // bar charts open facing front and do not spin
  children: ReactNode;
}) {
  const first = chart ? CHART_VIEW : VIEWS[0];
  const [view, setView] = useState(first);
  const [spin, setSpin] = useState(!chart);
  const still = useMedia("(prefers-reduced-motion: reduce)");
  return (
    <figure>
      <div className="stage relative overflow-hidden rounded-xl" style={{ height }} role="img" aria-label={label}>
        <Fallback>
          <Canvas camera={{ position: first.position, fov: 42 }} dpr={[1, 2]}>
            <ambientLight intensity={1.4} />
            <directionalLight position={[6, 10, 4]} intensity={1.6} />
            <directionalLight position={[-8, 4, -6]} intensity={0.5} />
            {children}
            <Controls view={view} spin={spin && !still} />
          </Canvas>
        </Fallback>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
        <span className="mr-1 text-(--ink-2)">Drag to rotate. View:</span>
        {VIEWS.map((v) => (chart && v.label === "Angle" ? CHART_VIEW : v)).map((v) => (
          <button
            key={v.label}
            type="button"
            className="chip"
            onClick={() => {
              setSpin(false);
              setView({ ...v });
            }}
          >
            {v.label}
          </button>
        ))}
        <button type="button" className="chip" aria-pressed={spin && !still} onClick={() => setSpin((s) => !s)}>
          Spin
        </button>
      </div>
    </figure>
  );
}
