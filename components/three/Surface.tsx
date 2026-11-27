"use client";

import { Line } from "@react-three/drei";
import { useMemo, useState } from "react";
import * as THREE from "three";

import { pct, rupees } from "@/lib/format";
import type { Grid } from "@/lib/types";
import Label from "./Label";
import Scene, { usePalette, type Palette } from "./Scene";

const W = 8;
const D = 6;
const H = 4;

interface Layout {
  x: (col: number) => number;
  y: (value: number) => number;
  z: (row: number) => number;
}

function layout(grid: Grid, price: number | null): Layout {
  const all = grid.values.flat().filter((v): v is number => v !== null);
  if (price) all.push(price);
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  return {
    x: (c) => (c / (grid.columns.length - 1) - 0.5) * W,
    y: (v) => ((v - lo) / (hi - lo || 1)) * H,
    z: (r) => (r / (grid.rows.length - 1) - 0.5) * D,
  };
}

/** Neutral at the market price, blue above, orange below (full strength 50% away). */
function colourFor(value: number, price: number | null, p: Palette): THREE.Color {
  const gap = price ? value / price - 1 : 0;
  const strength = Math.min(Math.abs(gap) / 0.5, 1);
  return new THREE.Color(p.neutral).lerp(new THREE.Color(gap >= 0 ? p.above : p.below), strength);
}

function Mesh({ grid, price, onHover }: { grid: Grid; price: number | null; onHover: (cell: [number, number] | null) => void }) {
  const palette = usePalette();
  const at = layout(grid, price);
  const geometry = useMemo(() => {
    const scale = layout(grid, price);
    const nx = grid.columns.length;
    const positions: number[] = [];
    const colours: number[] = [];
    grid.values.forEach((row, r) =>
      row.forEach((v, c) => {
        positions.push(scale.x(c), scale.y(v ?? 0), scale.z(r));
        colours.push(...colourFor(v ?? 0, price, palette).toArray());
      }),
    );
    const index: number[] = [];
    for (let r = 0; r < grid.rows.length - 1; r++) {
      for (let c = 0; c < nx - 1; c++) {
        const corners = [grid.values[r][c], grid.values[r][c + 1], grid.values[r + 1][c], grid.values[r + 1][c + 1]];
        if (corners.some((v) => v === null)) continue; // growth not below WACC: leave a hole
        const a = r * nx + c;
        index.push(a, a + nx, a + 1, a + 1, a + nx, a + nx + 1);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
    g.setIndex(index);
    g.computeVertexNormals();
    return g;
  }, [grid, price, palette]);

  const wires = useMemo(() => {
    const scale = layout(grid, price);
    const point = (r: number, c: number) => {
      const v = grid.values[r][c];
      return v === null ? null : new THREE.Vector3(scale.x(c), scale.y(v) + 0.012, scale.z(r));
    };
    const segments: THREE.Vector3[] = [];
    grid.values.forEach((row, r) =>
      row.forEach((_, c) => {
        const here = point(r, c);
        if (!here) return;
        if (c % 1 === 0 && r % 4 === 0 && c + 1 < row.length) {
          const next = point(r, c + 1);
          if (next) segments.push(here, next);
        }
        if (c % 4 === 0 && r + 1 < grid.values.length) {
          const next = point(r + 1, c);
          if (next) segments.push(here, next);
        }
      }),
    );
    return segments;
  }, [grid, price]);

  const [cr, cc] = grid.centre;
  const base = grid.values[cr][cc];

  return (
    <group position={[0, -0.4, 0]}>
      <mesh
        geometry={geometry}
        onPointerMove={(e) => {
          e.stopPropagation();
          const col = Math.round((e.point.x / W + 0.5) * (grid.columns.length - 1));
          const row = Math.round((e.point.z / D + 0.5) * (grid.rows.length - 1));
          onHover([row, col]);
        }}
        onPointerOut={() => onHover(null)}
      >
        <meshStandardMaterial vertexColors side={THREE.DoubleSide} roughness={0.45} metalness={0.15} />
      </mesh>
      {wires.length > 0 && <Line points={wires} segments color={palette.ink} transparent opacity={0.22} lineWidth={1} />}
      {price !== null && (
        <group position={[0, at.y(price), 0]}>
          <mesh rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[W, D]} />
            <meshBasicMaterial color={palette.ink} transparent opacity={0.09} side={THREE.DoubleSide} depthWrite={false} />
          </mesh>
          <Line
            points={[[-W / 2, 0, -D / 2], [W / 2, 0, -D / 2], [W / 2, 0, D / 2], [-W / 2, 0, D / 2], [-W / 2, 0, -D / 2]]}
            color={palette.ink}
            transparent
            opacity={0.5}
            lineWidth={1}
          />
          <Label position={[-W / 2, 0.25, D / 2]} text={`Market price ${rupees(price)}`} dark={palette.dark} />
        </group>
      )}
      {base !== null && (
        <group position={[at.x(cc), at.y(base), at.z(cr)]}>
          <mesh>
            <sphereGeometry args={[0.13, 24, 24]} />
            <meshStandardMaterial color={palette.ink} emissive={palette.ink} emissiveIntensity={0.35} />
          </mesh>
          <Line points={[[0, 0, 0], [0, 1.1, 0]]} color={palette.ink} lineWidth={1.5} />
          <Label position={[0, 1.35, 0]} text={`Current case ${rupees(base)}`} dark={palette.dark} />
        </group>
      )}
      <gridHelper args={[10, 20, palette.line, palette.line]} position={[0, -0.02, 0]} />
      <Label
        position={[0, 0, D / 2 + 0.8]}
        text={`WACC ${pct(grid.columns[0])} → ${pct(grid.columns.at(-1))}`}
        dark={palette.dark}
      />
      <Label
        position={[W / 2 + 0.9, 0, 0]}
        text={`Growth ${pct(grid.rows[0])} → ${pct(grid.rows.at(-1))}`}
        dark={palette.dark}
      />
    </group>
  );
}

export default function Surface({
  grid,
  price,
  height,
  compact = false,
}: {
  grid: Grid;
  price: number | null;
  height?: number;
  compact?: boolean; // hero: readout under the stage
}) {
  const [cell, setCell] = useState<[number, number] | null>(null);
  const [row, col] = cell ?? grid.centre;
  const value = grid.values[row]?.[col];
  const readout = (
    <p className="my-2 text-sm" aria-live="off">
        <span className="text-(--ink-2)">{cell ? "Pointed at" : "Current case"}: </span>
        WACC {pct(grid.columns[col])}, terminal growth {pct(grid.rows[row])} →{" "}
        <strong>{rupees(value)}</strong>
        {value != null && price ? <span className="text-(--ink-2)"> ({pct(value / price - 1)} vs price)</span> : null}
      </p>
  );
  return (
    <div>
      {!compact && readout}
      <Scene
        height={height}
        label={`3D surface of fair value per share over WACC and terminal growth. The current case is ${rupees(grid.base_fair_value)} against a market price of ${rupees(price)}.`}
      >
        <Mesh grid={grid} price={price} onHover={setCell} />
      </Scene>
      {compact && readout}
    </div>
  );
}
