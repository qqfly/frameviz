#!/usr/bin/env node
// The unauthenticated legacy relay is intentionally disabled.
console.error('Unsupported relay. Start the authenticated Rust Host and bundled viewer; see README.md.')
process.exitCode = 2
