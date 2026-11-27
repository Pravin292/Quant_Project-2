"use client";

import dynamic from "next/dynamic";

import { useApi } from "@/lib/api";
import type { Assumptions, Grid } from "@/lib/types";
import { Card, Notice, Skeleton } from "./ui";
import WhenVisible from "./WhenVisible";

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
          <WhenVisible height={(height ?? 420) + 70}>
            <Surface grid={query.data} price={assumptions.bridge.price} height={height} />
          </WhenVisible>
        </div>
      ) : (
        <div className="animate-pulse rounded-xl bg-(--line)" style={{ height: (height ?? 420) + 70 }} />
      )}
    </Card>
  );
}
