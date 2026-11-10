#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const args=process.argv.slice(2),check=args.includes('--check')
const configPath=path.join(root,'version.json'),config=JSON.parse(fs.readFileSync(configPath,'utf8'))
if(args.includes('--bump')) {
 const value=args[args.indexOf('--bump')+1]
 if(!/^\d+\.\d+\.\d+$/.test(value))throw new Error('Use a plain semantic version')
 config.protocol_version=value;config.min_compatible_version=value.split('.').slice(0,2).join('.')+'.0'
 fs.writeFileSync(configPath,JSON.stringify(config,null,2)+'\n')
}
const version=config.protocol_version,min=config.min_compatible_version,errors=[]
if(min!==version.split('.').slice(0,2).join('.')+'.0')errors.push('min_compatible_version must be major.minor.0')
for(const name of ['command','response','event']) {
 const file=path.join(root,`packages/frameviz-protocol/schemas/envelope-${name}.json`)
 const schema=JSON.parse(fs.readFileSync(file,'utf8'))
 const [major,minor]=version.split('.')
 const expected={type:'string',pattern:`^${major}\\.${minor}\\.(0|[1-9][0-9]{0,8})$`}
 if(check) {if(JSON.stringify(schema.properties.protocol_version)!==JSON.stringify(expected))errors.push(file+': version series pattern')}
 else {schema.properties.protocol_version=expected;fs.writeFileSync(file,JSON.stringify(schema,null,2)+'\n')}
}
function edit(file,patterns) {
 let text=fs.readFileSync(path.join(root,file),'utf8')
 for(const [pattern,replacement] of patterns) {
  const found=text.match(pattern)
  if(!found) {errors.push(file+': required declaration missing');continue}
  if(check) {if(found[0]!==replacement)errors.push(file+': '+found[0])}
  else text=text.replace(pattern,replacement)
 }
 if(!check)fs.writeFileSync(path.join(root,file),text)
}
edit('packages/frameviz-protocol/src/constants.ts',[[/export const PROTOCOL_VERSION = "[\d.]+" as const;/,`export const PROTOCOL_VERSION = "${version}" as const;`]])
edit('packages/frameviz-py/frameviz/client.py',[[/PROTOCOL_VERSION = "[\d.]+"/,`PROTOCOL_VERSION = "${version}"`],[/MIN_COMPATIBLE_VERSION = "[\d.]+"/,`MIN_COMPATIBLE_VERSION = "${min}"`]])
edit('packages/frameviz-py/pyproject.toml',[[/^version = "[\d.]+"/m,`version = "${version}"`]])
edit('packages/frameviz-server/src/websocket.rs',[[/const PROTOCOL_VERSION: &str = "[\d.]+";/,`const PROTOCOL_VERSION: &str = "${version}";`]])
edit('packages/frameviz-cpp/include/frameviz/types.hpp',[[/constexpr const char \*PROTOCOL_VERSION = "[\d.]+";/,`constexpr const char *PROTOCOL_VERSION = "${version}";`],[/constexpr const char \*MIN_COMPATIBLE_VERSION = "[\d.]+";/,`constexpr const char *MIN_COMPATIBLE_VERSION = "${min}";`]])
edit('packages/frameviz-cpp/CMakeLists.txt',[[/project\(frameviz-cpp VERSION [\d.]+ LANGUAGES CXX\)/,`project(frameviz-cpp VERSION ${version} LANGUAGES CXX)`]])
edit('packages/frameviz-web-viewer/index.html',[[/const PROTOCOL_VERSION = '[\d.]+';/,`const PROTOCOL_VERSION = '${version}';`]])
function walk(dir) {
 for(const entry of fs.readdirSync(dir,{withFileTypes:true})) {
  if(entry.isSymbolicLink() || ['node_modules','.cache','.venv','.local','target','build','dist','dist-acceptance','.git'].includes(entry.name))continue
  const p=path.join(dir,entry.name),rel=path.relative(root,p)
  if(entry.isDirectory())walk(p)
  else if(entry.name==='package.json'||entry.name==='tauri.conf.json') {
   const data=JSON.parse(fs.readFileSync(p,'utf8'))
   if(data.version!==undefined) {if(check&&data.version!==version)errors.push(rel);else if(!check){data.version=version;fs.writeFileSync(p,JSON.stringify(data,null,2)+'\n')}}
  } else if(entry.name==='Cargo.toml')edit(rel,[[/^version = "[\d.]+"/m,`version = "${version}"`]])
 }
}
walk(root)
console.log(JSON.stringify({protocol_version:version,min_compatible_version:min,errors},null,2))
if(errors.length)process.exit(1)
