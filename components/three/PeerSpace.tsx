"use client";

import { Line } from "@react-three/drei";

import { num } from "@/lib/format";
import type { Multiples } from "@/lib/types";
import Label from "./Label";
import Scene, { usePalette } from "./Scene";

function Points({ companies, selected }: { companies: Multiples[]; selected: string }) {
  const palette = usePalette();
  const shown = companies.filter((c) => c.pe !== null && c.ev_ebitda !== null);
  // Axes span the data (not zero) so close companies separate; the ranges are labelled.
  const range = (values: number[]) => [Math.min(...values), Math.max(...values)] as const;
  const [pe0, pe1] = range(shown.map((c) => c.pe!));
  const [ev0, ev1] = range(shown.map((c) => c.ev_ebitda!));
  const share = (v: number, lo: number, hi: number) => (v - lo) / (hi - lo || 1);
  const maxCap = Math.max(...shown.map((c) => c.market_cap));
  return (
    <group position={[0, -0.8, 0]}>
      {shown.map((c, i) => {
        const x = (share(c.pe!, pe0, pe1) - 0.5) * 8;
        const y = 0.5 + share(c.ev_ebitda!, ev0, ev1) * 3.4;
        const z = (i / Math.max(shown.length - 1, 1) - 0.5) * 4; // depth only separates companies
        const radius = 0.12 + 0.26 * Math.cbrt(c.market_cap / maxCap);
        const mine = c.ticker === selected;
        return (
          <group key={c.ticker} position={[x, 0, z]}>
            <Line points={[[0, 0, 0], [0, y, 0]]} color={palette.ink} transparent opacity={0.35} lineWidth={1} />
            <mesh position={[0, y, 0]}>
              <sphereGeometry args={[radius, 32, 32]} />
              <meshStandardMaterial color={mine ? palette.below : palette.above} roughness={0.25} metalness={0.35} />
            </mesh>
            <Label
              position={[0, y + radius + 0.3, 0]}
              text={`${c.ticker.replace(".NS", "")} · ${num(c.pe, 1)}x / ${num(c.ev_ebitda, 1)}x`}
              dark={palette.dark}
            />
          </group>
        );
      })}
      <gridHelper args={[10, 20, palette.line, palette.line]} />
      <Label position={[0, 0.1, 3]} text={`P/E ${num(pe0, 1)}x → ${num(pe1, 1)}x`} dark={palette.dark} />
      <Label position={[-2.5, 4.4, 0]} text={`↑ EV/EBITDA ${num(ev0, 1)}x to ${num(ev1, 1)}x`} dark={palette.dark} />
    </group>
  );
}

export default function PeerSpace({ companies, selected }: { companies: Multiples[]; selected: string }) {
  return (
    <Scene label="3D view of each company's P/E and EV/EBITDA multiples. The table above lists the same numbers.">
      <Points companies={companies} selected={selected} />
    </Scene>
  );
}
