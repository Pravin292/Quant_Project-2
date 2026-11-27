"use client";

import { Line } from "@react-three/drei";
import { useState } from "react";

import { num, rupees } from "@/lib/format";
import Label from "./Label";
import Scene, { usePalette } from "./Scene";

export interface Bin {
  from: number;
  to: number;
  count: number;
}

const W = 10;
const H = 4;

function Bars({ bins, price, median, onHover }: { bins: Bin[]; price: number | null; median: number; onHover: (i: number | null) => void }) {
  const palette = usePalette();
  const [active, setActive] = useState<number | null>(null);
  const lo = bins[0].from;
  const hi = bins[bins.length - 1].to;
  const max = Math.max(...bins.map((b) => b.count));
  const span = Math.max(hi, price ?? hi) - Math.min(lo, price ?? lo);
  const left = Math.min(lo, price ?? lo);
  const x = (v: number) => ((v - left) / span - 0.5) * W;
  const marker = (value: number, label: string, lift: number) => (
    <group position={[x(value), 0, 1]}>
      <Line points={[[0, 0, 0], [0, H + lift, 0]]} color={palette.ink} lineWidth={2} />
      <Label position={[0, H + lift + 0.25, 0]} text={`${label} ${rupees(value)}`} dark={palette.dark} />
    </group>
  );
  return (
    <group position={[0, -0.6, 0]}>
      {bins.map((b, i) => {
        const height = Math.max((b.count / max) * H, 0.02);
        const above = price !== null && (b.from + b.to) / 2 > price;
        return (
          <mesh
            key={i}
            position={[x((b.from + b.to) / 2), height / 2, 0]}
            onPointerOver={(e) => {
              e.stopPropagation();
              setActive(i);
              onHover(i);
            }}
            onPointerOut={() => {
              setActive(null);
              onHover(null);
            }}
          >
            <boxGeometry args={[Math.max(((b.to - b.from) / span) * W * 0.86, 0.03), height, 1.4]} />
            <meshStandardMaterial
              color={above ? palette.above : palette.below}
              emissive={active === i ? palette.ink : "#000000"}
              emissiveIntensity={active === i ? 0.3 : 0}
              roughness={0.35}
              metalness={0.2}
            />
          </mesh>
        );
      })}
      {marker(median, "Median", 0.1)}
      {price !== null && marker(price, "Market price", 0.8)}
      <gridHelper args={[12, 24, palette.line, palette.line]} position={[0, -0.01, 0]} />
    </group>
  );
}

export default function Histogram({ bins, price, median }: { bins: Bin[]; price: number | null; median: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const b = hover === null ? null : bins[hover];
  return (
    <div>
      <p className="mb-2 text-sm">
        {b ? (
          <>
            {rupees(b.from)} to {rupees(b.to)}: <strong>{num(b.count)} runs</strong>
          </>
        ) : (
          <span className="text-(--ink-2)">Orange bars are below the market price, blue above. Point at a bar for its count.</span>
        )}
      </p>
      <Scene label={`3D histogram of simulated fair values. Median ${rupees(median)}, market price ${rupees(price)}.`}>
        <Bars bins={bins} price={price} median={median} onHover={setHover} />
      </Scene>
    </div>
  );
}
