/**
 * pdf2png.mjs — 用 pdfjs-dist 把 PDF 每页渲染成 PNG
 * 用法: node pdf2png.mjs <pdf-path> <output-dir> [start-page] [end-page]
 */
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from 'canvas';

const pdfPath = process.argv[2];
const outDir = process.argv[3] || 'output/pages';
const startPage = parseInt(process.argv[4]) || 1;
const endPage = parseInt(process.argv[5]) || 0;

if (!pdfPath) {
  console.error('Usage: node pdf2png.mjs <pdf-path> <output-dir> [start] [end]');
  process.exit(1);
}

mkdirSync(outDir, { recursive: true });

const data = new Uint8Array(readFileSync(pdfPath));
const doc = await getDocument({ data }).promise;
const total = endPage || doc.numPages;

console.log(`PDF: ${doc.numPages} pages, rendering ${startPage}-${total}`);

for (let i = startPage; i <= total; i++) {
  const page = await doc.getPage(i);
  const viewport = page.getViewport({ scale: 1.5 });
  const canvas = createCanvas(viewport.width, viewport.height);
  const ctx = canvas.getContext('2d');
  await page.render({ canvasContext: ctx, viewport }).promise;
  const buf = canvas.toBuffer('image/png');
  const outPath = `${outDir}/page_${String(i).padStart(4, '0')}.png`;
  writeFileSync(outPath, buf);
  console.log(`Page ${i}: ${buf.length} bytes`);
}

console.log(`Done: ${total - startPage + 1} pages → ${outDir}/`);
