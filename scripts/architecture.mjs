// Draws docs/architecture.png: node scripts/architecture.mjs
import { chromium } from "@playwright/test";

const box = (x, y, w, title, sub) => `<rect x="${x}" y="${y}" width="${w}" height="64" rx="10" fill="#fff" stroke="#111"/>
<text x="${x + w / 2}" y="${y + 27}" font-weight="700">${title}</text><text x="${x + w / 2}" y="${y + 47}" fill="#555" font-size="12">${sub}</text>`;
const arrow = (d, label, x, y) => `<path d="${d}" fill="none" stroke="#111" stroke-width="1.4" marker-end="url(#a)"/>` +
  (label ? `<text x="${x}" y="${y}" font-size="11" fill="#555">${label}</text>` : "");
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="430" font-family="system-ui, sans-serif" font-size="14" text-anchor="middle">
<defs><marker id="a" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0L9 4.5L0 9z" fill="#111"/></marker></defs>
<rect width="1000" height="430" fill="#fff"/>
<rect x="352" y="96" width="624" height="314" rx="16" fill="#f4f4f4"/>
<text x="664" y="124" font-weight="700">Vercel (one project, deployed from main)</text>
${box(24, 24, 230, "Yahoo Finance", "statements, prices, peers")}
${box(24, 170, 230, "GitHub Actions (daily)", "refresh, test, commit")}
${box(24, 316, 230, "FRED and Damodaran", "risk-free rate, risk premium")}
${box(382, 150, 250, "Next.js dashboard", "React, Recharts, three.js")}
${box(690, 150, 256, "FastAPI function /api", "validation, cache, rate limit")}
${box(690, 306, 256, "DCF engine src/dcf", "all finance logic")}
${box(382, 306, 250, "data/snapshots", "dated JSON with sources")}
${arrow("M139 88 L139 168")}
${arrow("M139 316 L139 236")}
${arrow("M254 202 C 320 202, 310 338, 380 338", "commits", 322, 262)}
${arrow("M632 182 L688 182", "JSON", 660, 172)}
${arrow("M818 214 L818 304")}
${arrow("M632 338 L688 338", "reads", 660, 328)}
${arrow("M760 150 C 700 36, 420 30, 258 50", "live price per request", 520, 30)}
</svg>`;
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || undefined });
const page = await browser.newPage({ viewport: { width: 1000, height: 430 }, deviceScaleFactor: 2 });
await page.setContent(`<body style="margin:0">${svg}</body>`);
await page.screenshot({ path: "docs/architecture.png" });
await browser.close();
