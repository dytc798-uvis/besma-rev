/**
 * a4-manual 캡처 → 웹 설명서 public 폴더 동기화
 * Usage: node scripts/sync-fe-guide-screenshots.mjs
 */
import { cp, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(__dirname, "..", "..", "docs", "reports", "functional-eval-e2e", "screenshots", "a4-manual");
const DEST = path.resolve(__dirname, "..", "public", "fe-guide", "screenshots");

async function main() {
  await mkdir(DEST, { recursive: true });
  const { readdir } = await import("node:fs/promises");
  const files = (await readdir(SRC)).filter((f) => f.endsWith(".png"));
  for (const f of files) {
    await cp(path.join(SRC, f), path.join(DEST, f));
    console.log("sync", f);
  }
  const legacyMap = [
    ["hq_director_approval.png", "hq_approval.png"],
    ["team_evaluate_mobile.png", "team_evaluate.png"],
  ];
  for (const [src, dest] of legacyMap) {
    if (files.includes(src)) {
      await cp(path.join(SRC, src), path.join(DEST, dest));
      console.log("sync legacy", dest, "<-", src);
    }
  }
  console.log(`Done: ${files.length} files → ${DEST}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
