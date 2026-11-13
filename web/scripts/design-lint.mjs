import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SRC_DIR = path.resolve(__dirname, "../src");

const BANNED_WORDS = [
  "seamless",
  "revolutionise",
  "revolutionize",
  "empower",
  "leverage",
  "unlock",
  "supercharge",
  "next-gen",
  "cutting-edge",
  "ai-powered",
  "magic",
  "effortless",
];

function walkFiles(dir) {
  const results = [];
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkFiles(fullPath));
    } else if (/\.(ts|tsx|js|jsx|css|mjs)$/.test(entry.name)) {
      results.push(fullPath);
    }
  }
  return results;
}

function isExempt(filePath) {
  const rel = path.relative(SRC_DIR, filePath).replace(/\\/g, "/");
  if (rel === "styles/tokens.css") return true;
  if (rel.startsWith("components/ui/")) return true;
  return false;
}

const violations = [];
const files = walkFiles(SRC_DIR);

for (const filePath of files) {
  if (isExempt(filePath)) continue;
  const rel = path.relative(path.resolve(__dirname, ".."), filePath).replace(/\\/g, "/");
  const content = fs.readFileSync(filePath, "utf8");
  const lines = content.split(/\r?\n/);

  lines.forEach((line, index) => {
    const lineNum = index + 1;

    const hexMatch = line.match(/#[0-9a-fA-F]{6}\b/);
    if (hexMatch) {
      violations.push(`${rel}:${lineNum} - Raw 6-digit hex value "${hexMatch[0]}" is forbidden outside styles/tokens.css and components/ui/`);
    }

    if (/\bgradient\b|linear-gradient|radial-gradient|conic-gradient|bg-gradient/i.test(line)) {
      violations.push(`${rel}:${lineNum} - Gradient usage is forbidden`);
    }

    if (/\bbackdrop-blur\b/.test(line)) {
      violations.push(`${rel}:${lineNum} - "backdrop-blur" is forbidden`);
    }

    if (/\bshadow-[a-z0-9[\]]+/i.test(line) && !/\bshadow-none\b/.test(line)) {
      violations.push(`${rel}:${lineNum} - "shadow-*" utility is forbidden`);
    }

    const radiusMatch = line.match(/\brounded-(xl|2xl|3xl)\b/);
    if (radiusMatch) {
      violations.push(`${rel}:${lineNum} - Large border radius "${radiusMatch[0]}" is forbidden (max 8px)`);
    }

    if (/lucide-react/.test(line)) {
      violations.push(`${rel}:${lineNum} - Importing from "lucide-react" is forbidden`);
    }

    if (line.includes("\u2014")) {
      violations.push(`${rel}:${lineNum} - Em dash (U+2014) is forbidden in UI copy`);
    }

    if (/it['\u2019]s not\s+[^,.!?;]+,\s*it['\u2019]s/i.test(line)) {
      violations.push(`${rel}:${lineNum} - "It's not X, it's Y" phrasing is forbidden`);
    }

    for (const word of BANNED_WORDS) {
      const escaped = word.replace("-", "\\-");
      const regex = new RegExp(`\\b${escaped}\\b`, "i");
      if (regex.test(line)) {
        violations.push(`${rel}:${lineNum} - Banned buzzword "${word}" is forbidden`);
      }
    }
  });
}

if (violations.length > 0) {
  console.error("Design lint failed with violations:");
  for (const v of violations) {
    console.error(`  - ${v}`);
  }
  process.exit(1);
} else {
  console.log(`Design lint passed (${files.length} files scanned).`);
}

