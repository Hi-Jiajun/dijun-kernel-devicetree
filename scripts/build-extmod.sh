#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# dijun 6.18.32-4k 外部内核模块安全构建 SDK（零源树污染 + 双契约自动门禁）。
#
# 功能：
#   1. 只读引用 --kernel-src 与 --mod-src，将模块源码干净复制到隔离工作区编译；
#   2. 强制锁死 LOCALVERSION="-4k"、CONFIG_LOCALVERSION_AUTO=n、make LOCALVERSION="" 与
#      KBUILD_GENDWARFKSYMS_STABLE=1，杜绝 "+/-dirty" 导致的 vermagic ENOEXEC；
#   3. 使用仓库 symvers/6.18.32-os4.0.4.0/vmlinux-{hmos,pure}.symvers（含 module_layout=0x60801db3），
#      避免误改硬编码构建树造成的符号 CRC 漂移；
#   4. 产出的每个 .ko 必须通过四重门禁（数量>=1、vermagic 逐字匹配、module_layout==0x60801db3、
#      abi-gate.py 0 错误），并输出 build-manifest.json。
#
# 用法：
#   CLANG_BIN=<clang-r584948c/bin> scripts/build-extmod.sh \
#     --kernel-src <6.18.32 源码树> --mod-src <模块源码目录> --out <输出目录> \
#     [--profile hmos|pure] [--vendor-symvers] [--extra-symvers <file>]... \
#     [--make-arg KEY=VAL]... [--prep-cache <dir>] \
#     [--sign-key <pem> --sign-cert <x509>] [--jobs 16]
set -euo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
KERNEL_SRC=""
MOD_SRC=""
OUT=""
PROFILE="hmos"
USE_VENDOR_SYMVERS=0
EXTRA_SYMVERS=()
EXTRA_MAKE_ARGS=()
PREP_CACHE=""
SIGN_KEY=""
SIGN_CERT=""
JOBS=$(nproc 2>/dev/null || echo 8)

EXPECTED_VERMAGIC="6.18.32-4k SMP preempt mod_unload modversions aarch64"
EXPECTED_UTS="6.18.32-4k"
EXPECTED_LAYOUT_CRC="0x60801db3"

while [ $# -gt 0 ]; do
    case "$1" in
        --kernel-src) KERNEL_SRC=${2:?}; shift 2;;
        --mod-src) MOD_SRC=${2:?}; shift 2;;
        --out) OUT=${2:?}; shift 2;;
        --profile) PROFILE=${2:?}; shift 2;;
        --vendor-symvers) USE_VENDOR_SYMVERS=1; shift;;
        --extra-symvers) EXTRA_SYMVERS+=("${2:?}"); shift 2;;
        --make-arg) EXTRA_MAKE_ARGS+=("${2:?}"); shift 2;;
        --prep-cache) PREP_CACHE=${2:?}; shift 2;;
        --sign-key) SIGN_KEY=${2:?}; shift 2;;
        --sign-cert) SIGN_CERT=${2:?}; shift 2;;
        --jobs) JOBS=${2:?}; shift 2;;
        -h|--help) sed -n '2,23p' "$0"; exit 0;;
        *) echo "未知参数: $1" >&2; exit 2;;
    esac
done

[ -n "$KERNEL_SRC" ] && [ -d "$KERNEL_SRC" ] || { echo "需要有效 --kernel-src <目录>" >&2; exit 2; }
[ -n "$MOD_SRC" ] && [ -d "$MOD_SRC" ] || { echo "需要有效 --mod-src <目录>" >&2; exit 2; }
[ -n "$OUT" ] || { echo "需要 --out <输出目录>" >&2; exit 2; }
[ -n "${CLANG_BIN:-}" ] && [ -x "$CLANG_BIN/clang" ] || { echo "需要环境变量 CLANG_BIN=<clang-r584948c/bin>" >&2; exit 2; }
if [ -n "$SIGN_KEY" ] || [ -n "$SIGN_CERT" ]; then
    [ -r "$SIGN_KEY" ] && [ -r "$SIGN_CERT" ] || { echo "--sign-key 与 --sign-cert 必须同时有效" >&2; exit 2; }
fi

case "$PROFILE" in
    hmos)
        VMLINUX_SYMVERS="$ROOT/symvers/6.18.32-os4.0.4.0/vmlinux-hmos.symvers"
        WHITELIST="$ROOT/configs/6.18/ksym-whitelist-hmos.txt"
        ;;
    pure)
        VMLINUX_SYMVERS="$ROOT/symvers/6.18.32-os4.0.4.0/vmlinux-pure.symvers"
        WHITELIST="$ROOT/configs/6.18/ksym-whitelist-os4.0.4.0.txt"
        ;;
    *) echo "未知 --profile: $PROFILE（可选 hmos / pure）" >&2; exit 2;;
esac

BASE_CONFIG="$ROOT/configs/6.18/dijun-os4.0.4.0.config"
VENDOR_SYMVERS="$ROOT/symvers/6.18.32-os4.0.4.0/vendor-modules.symvers"
for req in "$VMLINUX_SYMVERS" "$WHITELIST" "$BASE_CONFIG"; do
    [ -r "$req" ] || { echo "缺少仓库基线文件: $req" >&2; exit 2; }
done

if [ "$USE_VENDOR_SYMVERS" -eq 1 ]; then
    [ -r "$VENDOR_SYMVERS" ] || { echo "缺少 $VENDOR_SYMVERS" >&2; exit 2; }
    EXTRA_SYMVERS+=("$VENDOR_SYMVERS")
fi

# 绝对路径规范化外部 extra-symvers
ABS_EXTRA_SYMVERS=()
for sym in "${EXTRA_SYMVERS[@]}"; do
    [ -r "$sym" ] || { echo "extra-symvers 不存在: $sym" >&2; exit 2; }
    ABS_EXTRA_SYMVERS+=("$(readlink -f "$sym")")
done

CLANG_ROOT=$(cd "$CLANG_BIN/.." && pwd)
export LIBCLANG_PATH="${LIBCLANG_PATH:-$CLANG_ROOT/lib}"
export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-builder}"
export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-dijun-build}"
export KBUILD_GENDWARFKSYMS_STABLE=1

HAVE_RUST=0
if [ -n "${RUSTC:-}" ] && [ -x "${RUSTC:-}" ] && [ -n "${RUST_LIB_SRC:-}" ] && [ -d "${RUST_LIB_SRC:-}" ] && [ -n "${BINDGEN:-}" ]; then
    HAVE_RUST=1
    export PATH="$(dirname "$RUSTC"):$CLANG_BIN:$PATH"
    export RUSTC RUST_LIB_SRC BINDGEN
    export HOSTRUSTC="$RUSTC"
else
    export PATH="$CLANG_BIN:$PATH"
fi

TMP_BASE="${TMPDIR:-${XDG_CACHE_HOME:-$HOME/.cache}/dsh-tmp}"
mkdir -p "$TMP_BASE"
WORK=$(mktemp -d -p "$TMP_BASE" extmod-sdk.XXXXXX)
cleanup() {
    if [ -n "${WORK:-}" ] && [ -d "$WORK" ]; then
        chmod -R u+w "$WORK" 2>/dev/null || true
        find "$WORK" -depth -delete
    fi
}
trap cleanup EXIT
export TMPDIR="$WORK/tmp"
mkdir -p "$WORK/o" "$WORK/mod" "$WORK/tmp" "$WORK/out_kos" "$OUT"

KERNEL_SRC=$(readlink -f "$KERNEL_SRC")
MOD_SRC=$(readlink -f "$MOD_SRC")
OUT=$(readlink -f "$OUT")

prepare_build_tree() {
    local target_o=$1
    cp "$BASE_CONFIG" "$target_o/.config"
    "$KERNEL_SRC/scripts/config" --file "$target_o/.config" \
        --set-str LOCALVERSION "-4k" \
        --disable LOCALVERSION_AUTO \
        --set-str UNUSED_KSYMS_WHITELIST "$(readlink -f "$WHITELIST")"
    if [ "$HAVE_RUST" -eq 0 ]; then
        echo "== 未提供 Android RUSTC 工具链，在隔离配置中关闭 CONFIG_RUST（纯 C 外部模块模式）"
        "$KERNEL_SRC/scripts/config" --file "$target_o/.config" --disable RUST --disable ANDROID_BINDER_IPC_RUST
    fi
    make -C "$KERNEL_SRC" O="$target_o" ARCH=arm64 LLVM=1 LOCALVERSION="" olddefconfig >/dev/null
    make -C "$KERNEL_SRC" O="$target_o" ARCH=arm64 LLVM=1 LOCALVERSION="" -j"$JOBS" modules_prepare
    if [ -n "$SIGN_KEY" ] && [ ! -x "$target_o/scripts/sign-file" ]; then
        make -C "$KERNEL_SRC" O="$target_o" ARCH=arm64 LLVM=1 LOCALVERSION="" -j"$JOBS" scripts
    fi
}

echo "== 准备内核构建头文件 ($PROFILE, rust=$HAVE_RUST)"
if [ -n "$PREP_CACHE" ]; then
    PREP_TAG="rust${HAVE_RUST}"
    if [ -f "$PREP_CACHE/.prep_ok" ] && [ "$(cat "$PREP_CACHE/.prep_ok")" = "$PREP_TAG" ]; then
        echo "   复用准备缓存: $PREP_CACHE"
    else
        mkdir -p "$PREP_CACHE"
        prepare_build_tree "$PREP_CACHE"
        printf '%s\n' "$PREP_TAG" > "$PREP_CACHE/.prep_ok"
    fi
    cp -a "$PREP_CACHE/." "$WORK/o/"
    # 更新副本内 O=Makefile 指向隔离 $WORK/o，避免写回缓存目录
    if [ -f "$WORK/o/Makefile" ]; then
        python3 - "$WORK/o/Makefile" "$WORK/o" "$KERNEL_SRC" <<'PY'
import sys
mf, out_dir, src_dir = sys.argv[1:4]
txt = open(mf, encoding='utf-8').read()
lines = []
for line in txt.splitlines(True):
    if line.startswith('export KBUILD_OUTPUT ='):
        lines.append('export KBUILD_OUTPUT = %s\n' % out_dir)
    elif line.startswith('MAKEARGS := -C '):
        lines.append('MAKEARGS := -C %s\n' % src_dir)
    else:
        lines.append(line)
open(mf, 'w', encoding='utf-8').write(''.join(lines))
PY
        ln -sfn "$KERNEL_SRC" "$WORK/o/source"
    fi
else
    prepare_build_tree "$WORK/o"
fi

KREL=$(cat "$WORK/o/include/config/kernel.release")
if [ "$KREL" != "$EXPECTED_UTS" ]; then
    echo "错误: kernel.release='$KREL' != 期望 '$EXPECTED_UTS'" >&2
    exit 1
fi

# 锁定只读 vmlinux Module.symvers
rm -f "$WORK/o/Module.symvers"
cp "$VMLINUX_SYMVERS" "$WORK/o/Module.symvers"
chmod 0444 "$WORK/o/Module.symvers"

# 只拷贝源码文件到隔离目录，过滤原有构建残留
echo "== 复制模块源码到隔离目录（原目录只读不动）"
python3 - "$MOD_SRC" "$WORK/mod" <<'PY'
import os
import shutil
import sys

src, dst = sys.argv[1:3]
skip_dirs = {'.git', '.tmp_versions', '__pycache__'}
skip_suffixes = ('.ko', '.o', '.o.d', '.o.cmd', '.mod', '.mod.c', '.mod.cmd', '.a', '.order', '.symvers')
skip_names = {'Module.symvers', 'modules.order'}

for root, dirs, files in os.walk(src):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    rel = os.path.relpath(root, src)
    out_dir = dst if rel == '.' else os.path.join(dst, rel)
    os.makedirs(out_dir, exist_ok=True)
    for fn in files:
        if fn in skip_names or (fn.startswith('.') and fn.endswith('.cmd')) or fn.endswith(skip_suffixes):
            continue
        shutil.copy2(os.path.join(root, fn), os.path.join(out_dir, fn))
PY

EXTRA_STR=""
if [ ${#ABS_EXTRA_SYMVERS[@]} -gt 0 ]; then
    EXTRA_STR="${ABS_EXTRA_SYMVERS[*]}"
fi

echo "== 编译外部模块 (LOCALVERSION='', KBUILD_GENDWARFKSYMS_STABLE=1)"
make -C "$KERNEL_SRC" O="$WORK/o" ARCH=arm64 LLVM=1 \
    LOCALVERSION="" KBUILD_GENDWARFKSYMS_STABLE=1 \
    M="$WORK/mod" \
    ${EXTRA_STR:+KBUILD_EXTRA_SYMBOLS="$EXTRA_STR"} \
    ${EXTRA_MAKE_ARGS[@]+"${EXTRA_MAKE_ARGS[@]}"} \
    -j"$JOBS" modules

# 收集产出 .ko
mapfile -t BUILT_KOS < <(find "$WORK/mod" -name '*.ko' | sort)
if [ ${#BUILT_KOS[@]} -eq 0 ]; then
    echo "错误: 构建结束但未产出任何 .ko 文件" >&2
    exit 1
fi

for ko in "${BUILT_KOS[@]}"; do
    if [ -n "$SIGN_KEY" ]; then
        "$WORK/o/scripts/sign-file" sha512 "$SIGN_KEY" "$SIGN_CERT" "$ko"
        echo "   signed: $(basename "$ko")"
    fi
    cp "$ko" "$WORK/out_kos/"
done

echo "== 执行四重门禁验收"
python3 - "$ROOT/tools" "$WORK/out_kos" "$EXPECTED_VERMAGIC" "$EXPECTED_LAYOUT_CRC" <<'PY'
import glob
import os
import sys

tools_dir, ko_dir, exp_vm, exp_layout = sys.argv[1:5]
sys.path.insert(0, tools_dir)
from _elfmod import KoElf

exp_crc = int(exp_layout, 16)
kos = sorted(glob.glob(os.path.join(ko_dir, '*.ko')))
if not kos:
    raise SystemExit('门禁失败: 没有 .ko')
for p in kos:
    e = KoElf(p)
    vm = e.modinfo_first('vermagic')
    if vm != exp_vm:
        raise SystemExit('门禁失败 [%s]: vermagic=%r != %r' % (os.path.basename(p), vm, exp_vm))
    vers = e.versions()
    if vers.get('module_layout') != exp_crc:
        got = vers.get('module_layout')
        raise SystemExit('门禁失败 [%s]: module_layout=%s != %s' % (
            os.path.basename(p), hex(got) if got is not None else 'MISSING', exp_layout))
    print('CHECK OK %-24s vermagic="%s" module_layout=%s' % (os.path.basename(p), vm, exp_layout))
PY

GATE_ARGS=(--our-symvers "$VMLINUX_SYMVERS" --modules "$WORK/out_kos" --expect-vermagic "$EXPECTED_VERMAGIC" --out "$OUT/abi-gate.md" --json "$OUT/abi-gate.json")
for sym in "${ABS_EXTRA_SYMVERS[@]}"; do
    GATE_ARGS+=(--extra-symvers "$sym")
done
python3 "$ROOT/tools/abi-gate.py" "${GATE_ARGS[@]}"

# 导出通过门禁的产物与清单
for ko in "$WORK"/out_kos/*.ko; do
    cp "$ko" "$OUT/"
done
[ -r "$WORK/mod/Module.symvers" ] && cp "$WORK/mod/Module.symvers" "$OUT/Module.symvers"

python3 - "$ROOT/tools" "$OUT" "$PROFILE" "$VMLINUX_SYMVERS" <<'PY'
import glob
import hashlib
import json
import os
import sys

tools_dir, out_dir, profile, vmlinux_sym = sys.argv[1:5]
sys.path.insert(0, tools_dir)
from _elfmod import KoElf

items = []
for p in sorted(glob.glob(os.path.join(out_dir, '*.ko'))):
    blob = open(p, 'rb').read()
    e = KoElf(p)
    items.append({
        'name': os.path.basename(p),
        'size': len(blob),
        'sha256': hashlib.sha256(blob).hexdigest(),
        'vermagic': e.modinfo_first('vermagic'),
        'module_layout_crc': '0x%08x' % e.versions()['module_layout'],
        'exports': {k: {'crc': '0x%08x' % c, 'type': t} for k, (c, t, _ns) in sorted(e.export_details().items())},
        'signed': b'~Module signature appended~' in blob,
    })

manifest = {
    'profile': profile,
    'vmlinux_symvers': os.path.basename(vmlinux_sym),
    'modules': items,
}
with open(os.path.join(out_dir, 'build-manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print('写出清单: %s (%d 个模块)' % (os.path.join(out_dir, 'build-manifest.json'), len(items)))
PY
