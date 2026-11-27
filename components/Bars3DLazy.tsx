"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "./ui";

const Bars3DLazy = dynamic(() => import("./three/Bars3D"), { ssr: false, loading: () => <Skeleton rows={4} /> });

export default Bars3DLazy;
