#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# 构建 dijun 的 6.18 内核（保持与原厂一致的 ABI），并可选签名指定模块、跑 ABI 门。
#
# 用法：
#   CLANG_BIN=<clang-r584948c/bin> RUSTC=<rustc> RUST_LIB_SRC=<rustlib/src/rust/library> \
#   BINDGEN=<bindgen> scripts/build-kernel.sh \
#     --source <aosp kernel tree> --out <build dir> \
#     [--config configs/6.18/dijun-os4.config] \
#     [--whitelist configs/6.18/ksym-whitelist.txt] \
#     [--sign <module.ko>]... [--gate-modules <dir>]... [--jobs 16]
#
# 退出码：0 全部成功；非 0 表示构建/签名/门禁失败。
set -euo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SOURCE=""
OUT=""
CONFIG="$ROOT/configs/6.18/dijun-os4.config"
WHITELIST="$ROOT/configs/6.18/ksym-whitelist.txt"
JOBS=$(nproc 2>/dev/null || echo 8)
SIGN_MODULES=()
GATE_DIRS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --source) SOURCE=${2:?}; shift 2;;
        --out) OUT=${2:?}; shift 2;;
        --config) CONFIG=${2:?}; shift 2;;
        --whitelist) WHITELIST=${2:?}; shift 2;;
        --sign) SIGN_MODULES+=("${2:?}"); shift 2;;
        --gate-modules) GATE_DIRS+=("${2:?}"); shift 2;;
        --jobs) JOBS=${2:?}; shift 2;;
        -h|--help) sed -n '2,20p' "$0"; exit 0;;
        *) echo "未知参数: $1" >&2; exit 2;;
    esac
done

[ -n "$SOURCE" ] && [ -d "$SOURCE" ] || { echo "需要 --source <内核源码树>" >&2; exit 2; }
[ -n "$OUT" ] || { echo "需要 --out <构建目录>" >&2; exit 2; }
for v in CLANG_BIN RUSTC RUST_LIB_SRC BINDGEN; do
    [ -n "${!v:-}" ] || { echo "需要环境变量 $v" >&2; exit 2; }
done
[ -r "$CONFIG" ] || { echo "配置不存在: $CONFIG" >&2; exit 2; }
[ -r "$WHITELIST" ] || { echo "白名单不存在: $WHITELIST" >&2; exit 2; }
WHITELIST=$(readlink -f "$WHITELIST")

export PATH="$(dirname "$RUSTC"):$CLANG_BIN:$PATH"
export RUSTC RUST_LIB_SRC BINDGEN
export HOSTRUSTC="$RUSTC"

mkdir -p "$OUT"
cp "$CONFIG" "$OUT/.config"
"$SOURCE/scripts/config" --file "$OUT/.config" --set-str UNUSED_KSYMS_WHITELIST "$WHITELIST"

# CONFIG_MODULE_SIG_PROTECT_LIST 需要一个文件；Kleaf 会生成，纯 kbuild 下补空文件。
[ -e "$SOURCE/protected_module_names_list" ] || : > "$SOURCE/protected_module_names_list"

echo "== olddefconfig（会丢弃本树不存在的厂商私有选项）"
make -C "$SOURCE" O="$OUT" ARCH=arm64 LLVM=1 olddefconfig
python3 "$SOURCE/scripts/diffconfig" "$CONFIG" "$OUT/.config" | sed 's/^/   /' || true

echo "== 构建内核与模块（KBUILD_GENDWARFKSYMS_STABLE=1）"
make -C "$SOURCE" O="$OUT" ARCH=arm64 LLVM=1 -j"$JOBS" KBUILD_GENDWARFKSYMS_STABLE=1

echo "== 产物"
ls -l "$OUT/arch/arm64/boot/Image" "$OUT/Module.symvers"
sha256sum "$OUT/arch/arm64/boot/Image"

if [ ${#SIGN_MODULES[@]} -gt 0 ]; then
    echo "== 签名模块"
    for m in "${SIGN_MODULES[@]}"; do
        [ -r "$m" ] || { echo "模块不存在: $m" >&2; exit 1; }
        "$OUT/scripts/sign-file" sha512 "$OUT/certs/signing_key.pem" "$OUT/certs/signing_key.x509" "$m"
        echo "   signed: $m"
    done
fi

if [ ${#GATE_DIRS[@]} -gt 0 ]; then
    echo "== ABI 门"
    args=()
    for d in "${GATE_DIRS[@]}"; do args+=(--modules "$d"); done
    python3 "$ROOT/tools/abi-gate.py" --our-symvers "$OUT/Module.symvers" "${args[@]}" \
        --allow-unresolved-prefix mtk_pwrctl_slt_gpio_ || true
fi

echo "== 完成: $OUT"
