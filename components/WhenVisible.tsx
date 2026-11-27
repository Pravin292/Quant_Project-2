"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Mounts heavy content (the 3D library) only once it is near the screen and the browser
 * is idle, behind a placeholder of the same height so the page does not jump.
 */
export default function WhenVisible({ height, children }: { height: number; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    let timer = 0;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        observer.disconnect();
        const idle = window.requestIdleCallback as typeof window.requestIdleCallback | undefined;
        if (idle) idle(() => setShow(true), { timeout: 1500 });
        else timer = globalThis.setTimeout(() => setShow(true), 200) as unknown as number;
      },
      { rootMargin: "100px" },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
      window.clearTimeout(timer);
    };
  }, []);
  return (
    <div ref={ref} style={{ minHeight: height }}>
      {show ? children : <div aria-hidden="true" className="animate-pulse rounded-xl bg-(--line)" style={{ height }} />}
    </div>
  );
}
