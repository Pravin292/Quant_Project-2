"use client";

import { useEffect, useMemo } from "react";
import * as THREE from "three";

/** Text drawn on a sprite, so it always faces the camera and lives inside the 3D scene. */
export default function Label({
  position,
  text,
  dark,
  size = 0.42,
}: {
  position: [number, number, number];
  text: string;
  dark: boolean;
  size?: number;
}) {
  const { texture, ratio } = useMemo(() => {
    const canvas = document.createElement("canvas");
    const draw = canvas.getContext("2d")!;
    const font = "600 44px system-ui, sans-serif";
    draw.font = font;
    canvas.width = Math.ceil(draw.measureText(text).width) + 40;
    canvas.height = 72;
    draw.font = font; // resizing the canvas resets the context
    draw.fillStyle = dark ? "rgba(17,23,41,0.9)" : "rgba(255,255,255,0.92)";
    draw.beginPath();
    draw.roundRect(0, 0, canvas.width, canvas.height, 18);
    draw.fill();
    draw.fillStyle = dark ? "#eef1f8" : "#0c1020";
    draw.textBaseline = "middle";
    draw.fillText(text, 20, 38);
    const t = new THREE.CanvasTexture(canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    return { texture: t, ratio: canvas.width / canvas.height };
  }, [text, dark]);
  useEffect(() => () => texture.dispose(), [texture]);
  return (
    <sprite position={position} scale={[size * ratio, size, 1]} renderOrder={10}>
      <spriteMaterial map={texture} depthTest={false} transparent toneMapped={false} />
    </sprite>
  );
}
