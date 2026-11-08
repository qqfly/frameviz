#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./create_new_frameviz_app.sh --name <AppName> [--path <BasePath>] [--force]

Options:
  --name   Required. New app name, e.g. RobotStudio
  --path   Base directory where app folder will be created. Default: ./
  --force  Back up and replace only a directory previously created by this generator
EOF
}

APP_NAME=""
BASE_PATH="$PWD"
FORCE="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      APP_NAME="${2:-}"
      shift 2
      ;;
    --path)
      BASE_PATH="${2:-}"
      shift 2
      ;;
    --force)
      FORCE="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$APP_NAME" ]]; then
  echo "Error: --name is required" >&2
  usage
  exit 1
fi

if [[ ! "$APP_NAME" =~ ^[A-Za-z][A-Za-z0-9_-]{0,63}$ ]]; then
  echo "Error: app name must start with a letter and contain only letters, digits, _ or -" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR/template"

if [[ ! -d "$TEMPLATE_DIR" ]]; then
  REPO_TEMPLATE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)/templates/frameviz-template-external-app"
  if [[ -d "$REPO_TEMPLATE_DIR" ]]; then
    TEMPLATE_DIR="$REPO_TEMPLATE_DIR"
  else
    echo "Error: template directory not found at $TEMPLATE_DIR" >&2
    echo "Run this script from extracted devkit root." >&2
    exit 1
  fi
fi

mkdir -p "$BASE_PATH"
TARGET_DIR="$BASE_PATH/$APP_NAME"

if [[ -L "$TARGET_DIR" ]]; then
  echo "Error: refusing a symlink target" >&2; exit 1
fi
if [[ -e "$TARGET_DIR" ]]; then
  if [[ "$FORCE" == "1" ]]; then
    if [[ ! -f "$TARGET_DIR/.frameviz-generated" ]]; then
      echo "Error: refusing to overwrite a directory not created by this generator" >&2; exit 1
    fi
    BACKUP_DIR="${TARGET_DIR}.backup.$(date +%Y%m%d%H%M%S)"
    if [[ -e "$BACKUP_DIR" ]]; then echo "Backup already exists" >&2; exit 1; fi
    mv "$TARGET_DIR" "$BACKUP_DIR"
    mkdir -p "$TARGET_DIR"
  else
    echo "Error: target exists: $TARGET_DIR" >&2
    echo "Use --force to overwrite." >&2
    exit 1
  fi
else
  mkdir -p "$TARGET_DIR"
fi

# Keep redistribution notices with both source-tree and extracted-devkit templates.
NOTICE_ROOT="$TEMPLATE_DIR"
if [[ ! -f "$NOTICE_ROOT/LICENSE" ]]; then NOTICE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"; fi
# Copy reviewed source extensions only; reject local env/build artifacts.
python3 - "$TEMPLATE_DIR" "$TARGET_DIR" "$NOTICE_ROOT" <<'COPY'
import pathlib, shutil, sys
source, target, notices = map(pathlib.Path, sys.argv[1:])
allowed={'.py','.rs','.ts','.js','.mjs','.vue','.cpp','.hpp','.h','.cmake','.in','.toml','.json','.yaml','.yml','.html','.css','.sh','.md','.txt','.lock','.png','.ico','.icns','.tgz'}
for path in source.rglob('*'):
    rel=path.relative_to(source)
    if any(p.startswith('.') or p in {'node_modules','dist','build','target','__pycache__'} for p in rel.parts): continue
    if path.is_symlink() or not path.is_file(): continue
    if path.suffix not in allowed and path.name not in {'CMakeLists.txt','LICENSE','NOTICE'}: continue
    dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
for name in ['LICENSE','NOTICE']:
    shutil.copy2(notices/name,target/name)
shutil.copytree(notices/'THIRD_PARTY_LICENSES',target/'THIRD_PARTY_LICENSES',dirs_exist_ok=True)
(target/'.frameviz-generated').write_text('FrameViz template generator v1\n')
COPY

# Ensure generated app starts clean even if source template came from a dirty tree.
rm -rf \
  "$TARGET_DIR/node_modules" \
  "$TARGET_DIR/dist" \
  "$TARGET_DIR/cpp/build" \
  "$TARGET_DIR/src-tauri/target" \
  "$TARGET_DIR/src-tauri/resources/cpp"

APP_NAME="$APP_NAME" TARGET_DIR="$TARGET_DIR" python3 <<'PY'
import json
import os
import re
from pathlib import Path

app_name = os.environ["APP_NAME"].strip()
target_dir = Path(os.environ["TARGET_DIR"])

def to_kebab(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return s or "frameviz-app"

def to_snake(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return s or "frameviz_app"

slug = to_kebab(app_name)
crate_name = to_snake(app_name)

pkg_path = target_dir / "package.json"
pkg = json.loads(pkg_path.read_text())
pkg["name"] = slug
pkg_path.write_text(json.dumps(pkg, indent=2) + "\n")

tauri_conf_path = target_dir / "src-tauri" / "tauri.conf.json"
tauri_conf = json.loads(tauri_conf_path.read_text())
tauri_conf["productName"] = app_name
tauri_conf["identifier"] = f"dev.qqfly.frameviz.{slug}"
if "app" in tauri_conf and "windows" in tauri_conf["app"] and tauri_conf["app"]["windows"]:
    tauri_conf["app"]["windows"][0]["title"] = app_name
tauri_conf_path.write_text(json.dumps(tauri_conf, indent=2) + "\n")

cargo_path = target_dir / "src-tauri" / "Cargo.toml"
cargo_text = cargo_path.read_text()
cargo_text = re.sub(r'(?m)^name = ".*"$', f'name = "{crate_name}"', cargo_text, count=1)
cargo_text = re.sub(r'(?m)^description = ".*"$', f'description = "{app_name} (FrameViz App)"', cargo_text, count=1)
cargo_path.write_text(cargo_text)

cargo_lock_path = target_dir / "src-tauri" / "Cargo.lock"
if cargo_lock_path.exists():
    cargo_lock_text = cargo_lock_path.read_text()
    cargo_lock_text = cargo_lock_text.replace('name = "frameviz-external-app"', f'name = "{crate_name}"', 1)
    cargo_lock_path.write_text(cargo_lock_text)

index_path = target_dir / "index.html"
index_text = index_path.read_text()
index_text = re.sub(r"(?is)<title>.*?</title>", f"<title>{app_name}</title>", index_text, count=1)
index_path.write_text(index_text)

app_vue_path = target_dir / "src" / "App.vue"
app_vue_text = app_vue_path.read_text()
app_vue_text = re.sub(r"(?is)<h1>.*?</h1>", f"<h1>{app_name}</h1>", app_vue_text, count=1)
app_vue_path.write_text(app_vue_text)

readme_path = target_dir / "README.md"
if readme_path.exists():
    readme_text = readme_path.read_text()
    readme_text = re.sub(r"(?m)^# .*$", f"# {app_name}", readme_text, count=1)
    readme_path.write_text(readme_text)

cpp_main_path = target_dir / "cpp" / "src" / "main.cpp"
if cpp_main_path.exists():
    cpp_text = cpp_main_path.read_text()
    cpp_text = cpp_text.replace("FrameViz External App Backend (C++)", f"{app_name} Backend (C++)")
    cpp_main_path.write_text(cpp_text)

python_backend_path = target_dir / "python" / "backend_external_app.py"
if python_backend_path.exists():
    py_text = python_backend_path.read_text()
    py_text = py_text.replace("FrameViz External App Backend (Python)", f"{app_name} Backend (Python)")
    python_backend_path.write_text(py_text)
PY

echo "Created: $TARGET_DIR"
echo
echo "Next steps:"
echo "  cd $TARGET_DIR"
echo "  pnpm install"
echo "  pnpm build"
echo "  # Install the explicit local FrameViz 0.4.0 wheel, then Python dependencies."
echo "  .venv/bin/python -m pip install /path/to/frameviz-0.4.0-py3-none-any.whl -r python/requirements.txt"
echo "  pnpm tauri:dev"
echo "  # or:"
echo "  pnpm tauri:dev:all"
