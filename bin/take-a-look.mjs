#!/usr/bin/env node
// One-line launcher: `npx github:sooyun79-droid/take-a-look audit <path>`.
// The auditor itself is a dependency-free Python program; this wrapper only
// locates Python 3.11+, forwards the arguments and returns the same exit code.
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const MIN_MAJOR = 3;
const MIN_MINOR = 11;
const PROBE = "import sys;sys.stdout.write('%d.%d' % sys.version_info[:2])";
const CANDIDATES =
  process.platform === "win32"
    ? [["python"], ["python3"], ["py", "-3"]]
    : [["python3"], ["python"]];

function probe(command, prefix) {
  const result = spawnSync(command, [...prefix, "-I", "-c", PROBE], { encoding: "utf8" });
  if (result.error || result.status !== 0) return null;
  const [major, minor] = result.stdout.trim().split(".").map(Number);
  if (!Number.isFinite(major) || !Number.isFinite(minor)) return null;
  return [major, minor];
}

function findPython() {
  let older = null;
  for (const [command, ...prefix] of CANDIDATES) {
    const version = probe(command, prefix);
    if (!version) continue;
    if (version[0] === MIN_MAJOR && version[1] >= MIN_MINOR) return { command, prefix };
    if (version[0] === MIN_MAJOR && older === null) older = { command, prefix, version };
  }
  return older ? { command: older.command, prefix: older.prefix, version: older.version } : null;
}

const found = findPython();
if (!found) {
  console.error(
    [
      "떼껄룩을 실행하려면 Python 3.11 이상이 필요합니다. (Take a Look needs Python 3.11 or newer.)",
      "  · macOS: brew install python@3.12",
      '  · Windows: https://www.python.org/downloads/ 에서 설치하고 "Add python.exe to PATH"를 선택하세요.',
      "  · Linux: sudo apt install python3.12 (배포판에 맞는 패키지 이름)",
      "npm/npx는 Python을 대신 설치하지 않습니다.",
    ].join("\n"),
  );
  process.exit(1);
}
if (found.version) {
  const [major, minor] = found.version;
  console.error(
    [
      `설치된 Python ${major}.${minor}로는 떼껄룩을 실행할 수 없습니다. Python 3.11 이상이 필요합니다.`,
      `(Take a Look needs Python 3.11 or newer; found Python ${major}.${minor}.)`,
    ].join("\n"),
  );
  process.exit(1);
}

const child = spawnSync(
  found.command,
  // -B: no __pycache__ in the user's folder, -P: do not import from the audited folder.
  [...found.prefix, "-B", "-P", "-m", "take_a_look", ...process.argv.slice(2)],
  {
    stdio: "inherit",
    cwd: process.cwd(),
    env: {
      ...process.env,
      PYTHONPATH: [ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
      PYTHONIOENCODING: "utf-8",
    },
  },
);

if (child.error) {
  console.error(
    `Python 실행에 실패했습니다. (Failed to start Python: ${child.error.message})`,
  );
  process.exit(1);
}
process.exit(child.status === null ? 1 : child.status);
