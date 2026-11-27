"use client";

import { useState } from "react";

import Label from "./Label";
import Scene, { usePalette } from "./Scene";

export interface Cell3D {
  col: number;
  row: number;
  from: number;
  to: number;
  tone: "above" | "below" | "third" | "neutral";
  tip: string;
}

const W = 9;
const H = 4;

interface Props {
  columns: string[];
  rows: string[];
  cells: Cell3D[];
}

function Bars({ columns, rows, cells, onHover }: Props & { onHover: (tip: string | null) => void }) {
  const palette = usePalette();
  const [active, setActive] = useState<number | null>(null);
  const values = cells.flatMap((c) => [c.from, c.to]);
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, ...values);
  const y = (v: number) => ((v - lo) / (hi - lo || 1)) * H;
  const step = W / columns.length;
  const x = (col: number) => (col + 0.5) * step - W / 2;
  const z = (row: number) => (row - (rows.length - 1) / 2) * 1.35;
  const front = z(rows.length - 1) + 1.1;
  return (
    <group position={[0, -0.4, 0]}>
      {cells.map((c, i) => {
        const height = Math.max(Math.abs(y(c.to) - y(c.from)), 0.03);
        return (
          <mesh
            key={i}
            position={[x(c.col), (y(c.from) + y(c.to)) / 2, z(c.row)]}
            onPointerOver={(e) => {
              e.stopPropagation();
              setActive(i);
              onHover(c.tip);
            }}
            onPointerOut={() => {
              setActive(null);
              onHover(null);
            }}
          >
            <boxGeometry args={[step * 0.62, height, 0.8]} />
            <meshStandardMaterial
              color={palette[c.tone]}
              emissive={active === i ? palette.ink : "#000000"}
              emissiveIntensity={active === i ? 0.3 : 0}
              roughness={0.3}
              metalness={0.25}
            />
          </mesh>
        );
      })}
      {columns.map((name, i) => (
        // alternate heights so neighbouring names do not collide
        <Label key={name} position={[x(i), columns.length > 6 && i % 2 ? -0.5 : -0.05, front]} text={name} dark={palette.dark} size={columns.length > 6 ? 0.3 : 0.36} />
      ))}
      {rows.map((name, i) =>
        name ? <Label key={name} position={[W / 2 + 0.9, 0.2, z(i)]} text={name} dark={palette.dark} /> : null,
      )}
      <gridHelper args={[12, 24, palette.line, palette.line]} position={[0, -0.01, 0]} />
    </group>
  );
}

export default function Bars3D({ label, ...props }: Props & { label: string }) {
  const [tip, setTip] = useState<string | null>(null);
  return (
    <div>
      <p className="mb-2 text-sm">{tip ?? <span className="text-(--ink-2)">Point at a bar for its value.</span>}</p>
      <Scene label={label} chart>
        <Bars {...props} onHover={setTip} />
      </Scene>
    </div>
  );
}
