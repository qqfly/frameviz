#!/usr/bin/env node
import { spawn } from "node:child_process";

const child = spawn("pnpm", ["dev"], {
  stdio: "inherit",
  shell: true,
  env: process.env,
});

let shuttingDown = false;

const shutdown = (signal) => {
  if (shuttingDown) return;
  shuttingDown = true;
  try {
    child.kill(signal);
  } catch {
    // Ignore errors when the child is already closed.
  }
  // Ensure we exit cleanly even if the child ignores the signal.
  setTimeout(() => process.exit(0), 2000).unref();
};

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

child.on("exit", (code) => {
  if (shuttingDown) {
    process.exit(0);
  }
  process.exit(code ?? 0);
});
