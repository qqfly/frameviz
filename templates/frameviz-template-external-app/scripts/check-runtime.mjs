#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
const cwd=process.cwd(),require=createRequire(path.join(cwd,'package.json'))
const fail=message=>{console.error('[runtime-check] '+message);process.exit(1)}
const pkg=JSON.parse(fs.readFileSync(path.join(cwd,'package.json'),'utf8'))
const devkit=path.join(cwd,'DEVKIT_MANIFEST.json')
const required=fs.existsSync(devkit)?JSON.parse(fs.readFileSync(devkit,'utf8')).required_protocol_version:pkg.version
let version
try {version=JSON.parse(fs.readFileSync(require.resolve('@frameviz/protocol/package.json'),'utf8')).version}
catch {fail('Install the local FrameViz SDK tarballs or run setup:local-sdk with an explicit source path.')}
if(version!==required)fail(`SDK protocol mismatch: expected ${required}, found ${version}`)
if(process.env.FRAMEVIZ_RUNTIME_MANIFEST) {
 const manifest=JSON.parse(fs.readFileSync(process.env.FRAMEVIZ_RUNTIME_MANIFEST,'utf8'))
 if(manifest.protocol_version!==required)fail('Explicit runtime manifest has a different protocol version')
}
console.log(`[runtime-check] Local SDK ${version} is consistent. Live Host version and authentication are checked on connect.`)
