"use client";

import dynamic from "next/dynamic";

import { useApi } from "@/lib/api";
import type { Assumptions, Grid } from "@/lib/types";
import { Card, Notice, Skeleton } from "./ui";

const Surface = dynamic(() => import("./three/Surface"), { ssr: false, loading: () => <Skeleton rows={4} /> });

export default function SurfaceCard({ assumptions, height }: { assumptions: Assumptions; height?: number }) {
  const query = useApi<Grid>("/api/surface", assumptions);
  return (
    <Card
      title="Valuation landscape: WACC × terminal growth"
      note="Height is fair value per share. The flat sheet is the market price: blue ground rises above it, orange sits below."
    >
      {query.error ? (
        <Notice kind="error">{query.error}</Notice>
      ) : query.data ? (
        <div className={query.loading ? "opacity-60" : ""}>
          <Surface grid={query.data} price={assumptions.bridge.price} height={height} />
        </div>
      ) : (
        <Skeleton rows={4} />
      )}
    </Card>
  );
}
