#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# 构建 dijun 的 6.18 内核（锁定 vermagic 与 KMI/GKI ABI），支持多线 Profile 与自动 ABI 门。
#
# 用法：
#   CLANG_BIN=<clang-r584948c/bin> RUSTC=<rustc> RUST_LIB_SRC=<rustlib/src/rust/library> \
#   BINDGEN=<bindgen> scripts/build-kernel.sh \
#     --source <aosp 6.18 tree> --out <build dir> \
#     [--profile stock-abi|pidns|hmos|panthor] \
#     [--baseline os4.0.4.0|os4.0.0.19] \
#     [--apply-patches] [--localversion -4k] \
#     [--config <override.config>] [--whitelist <override.txt>] \
#     [--sign <module.ko>]... [--gate-modules <dir>]... [--jobs 16]
#
# 退出码：0 全部成功；非 0 表示配置/补丁/构建/vermagic/门禁失败。
set -euo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SOURCE=""
OUT=""
PROFILE="stock-abi"
BASELINE="os4.0.4.0"
CONFIG=""
WHITELIST=""
LOCALVER="-4k"
APPLY_PATCHES=0
BUILD_USER="${KBUILD_BUILD_USER:-builder}"
BUILD_HOST="${KBUILD_BUILD_HOST:-dijun-build}"
JOBS=$(nproc 2>/dev/null || echo 8)
SIGN_MODULES=()
GATE_DIRS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --source) SOURCE=${2:?}; shift 2;;
        --out) OUT=${2:?}; shift 2;;
        --profile) PROFILE=${2:?}; shift 2;;
        --baseline) BASELINE=${2:?}; shift 2;;
        --config) CONFIG=${2:?}; shift 2;;
        --whitelist) WHITELIST=${2:?}; shift 2;;
        --localversion) LOCALVER=${2:?}; shift 2;;
        --apply-patches) APPLY_PATCHES=1; shift;;
        --sign) SIGN_MODULES+=("${2:?}"); shift 2;;
        --gate-modules) GATE_DIRS+=("${2:?}"); shift 2;;
        --jobs) JOBS=${2:?}; shift 2;;
        -h|--help) sed -n '2,17p' "$0"; exit 0;;
        *) echo "未知参数: $1" >&2; exit 2;;
    esac
done

[ -n "$SOURCE" ] && [ -d "$SOURCE" ] || { echo "需要 --source <内核源码树>" >&2; exit 2; }
[ -n "$OUT" ] || { echo "需要 --out <构建目录>" >&2; exit 2; }
for v in CLANG_BIN RUSTC RUST_LIB_SRC BINDGEN; do
    [ -n "${!v:-}" ] || { echo "需要环境变量 $v" >&2; exit 2; }
done

if [ -z "$CONFIG" ]; then
    case "$BASELINE" in
        os4.0.4.0) CONFIG="$ROOT/configs/6.18/dijun-os4.0.4.0.config";;
        os4.0.0.19) CONFIG="$ROOT/configs/6.18/dijun-os4.config";;
        *) echo "未知 --baseline: $BASELINE（可选 os4.0.4.0 / os4.0.0.19）" >&2; exit 2;;
    esac
fi

FRAGMENTS=()
PATCH_DIR=""
if [ -z "$WHITELIST" ]; then
    case "$BASELINE" in
        os4.0.4.0) WHITELIST="$ROOT/configs/6.18/ksym-whitelist-os4.0.4.0.txt";;
        os4.0.0.19) WHITELIST="$ROOT/configs/6.18/ksym-whitelist-os4.0.0.19.txt";;
    esac
fi

case "$PROFILE" in
    stock-abi) ;;
    pidns) FRAGMENTS+=("$ROOT/configs/6.18/fragments/pidns.config");;
    hmos)
        FRAGMENTS+=("$ROOT/configs/6.18/fragments/hmos-ipc.config")
        PATCH_DIR="$ROOT/patches/6.18/hmos"
        if [ "$BASELINE" = "os4.0.4.0" ] && [ "$WHITELIST" = "$ROOT/configs/6.18/ksym-whitelist-os4.0.4.0.txt" ]; then
            WHITELIST="$ROOT/configs/6.18/ksym-whitelist-hmos.txt"
        fi
        ;;
    panthor)
        FRAGMENTS+=("$ROOT/configs/6.18/fragments/panthor-builtin.config")
        PATCH_DIR="$ROOT/patches/6.18/panthor"
        ;;
    *) echo "未知 --profile: $PROFILE（可选 stock-abi / pidns / hmos / panthor）" >&2; exit 2;;
esac

[ -r "$CONFIG" ] || { echo "配置不存在: $CONFIG" >&2; exit 2; }
[ -r "$WHITELIST" ] || { echo "白名单不存在: $WHITELIST" >&2; exit 2; }
WHITELIST=$(readlink -f "$WHITELIST")

if [ "$PROFILE" = "hmos" ] && [ ! -f "$SOURCE/drivers/android/dijun_hmos_ipc_exports.c" ]; then
    if [ "$APPLY_PATCHES" -eq 1 ]; then
        echo "== 应用 patches/6.18/hmos/*.patch 到 $SOURCE"
        for p in "$PATCH_DIR"/*.patch; do
            [ -r "$p" ] || continue
            patch -d "$SOURCE" -p1 < "$p"
        done
    else
        echo "错误: $SOURCE 尚未包含 drivers/android/dijun_hmos_ipc_exports.c；请先复制独立源码树并传入 --apply-patches" >&2
        exit 2
    fi
fi

CLANG_ROOT=$(cd "$CLANG_BIN/.." && pwd)
export PATH="$(dirname "$RUSTC"):$CLANG_BIN:$PATH"
export LIBCLANG_PATH="${LIBCLANG_PATH:-$CLANG_ROOT/lib}"
export RUSTC RUST_LIB_SRC BINDGEN
export HOSTRUSTC="$RUSTC"
export KBUILD_BUILD_USER="$BUILD_USER"
export KBUILD_BUILD_HOST="$BUILD_HOST"
export KBUILD_GENDWARFKSYMS_STABLE=1

mkdir -p "$OUT"
cp "$CONFIG" "$OUT/.config"
for frag in "${FRAGMENTS[@]}"; do
    [ -r "$frag" ] || { echo "缺少配置片段: $frag" >&2; exit 2; }
    printf '\n# merged fragment: %s\n' "$(basename "$frag")" >> "$OUT/.config"
    cat "$frag" >> "$OUT/.config"
done

"$SOURCE/scripts/config" --file "$OUT/.config" \
    --set-str LOCALVERSION "$LOCALVER" \
    --disable LOCALVERSION_AUTO \
    --set-str UNUSED_KSYMS_WHITELIST "$WHITELIST"

# CONFIG_MODULE_SIG_PROTECT_LIST 需要一个文件；Kleaf 会生成，纯 kbuild 下补空文件。
[ -e "$SOURCE/protected_module_names_list" ] || : > "$SOURCE/protected_module_names_list"

echo "== olddefconfig (profile=$PROFILE baseline=$BASELINE)"
make -C "$SOURCE" O="$OUT" ARCH=arm64 LLVM=1 LOCALVERSION="" olddefconfig
python3 "$SOURCE/scripts/diffconfig" "$CONFIG" "$OUT/.config" | sed 's/^/   /' || true

echo "== 构建内核与模块 (KBUILD_GENDWARFKSYMS_STABLE=1, LOCALVERSION='')"
make -C "$SOURCE" O="$OUT" ARCH=arm64 LLVM=1 LOCALVERSION="" -j"$JOBS" KBUILD_GENDWARFKSYMS_STABLE=1

KREL=$(cat "$OUT/include/config/kernel.release")
echo "== kernel.release = $KREL"
case "$KREL" in
    *+*|*-dirty*)
        echo "错误: kernel.release 包含 '+' 或 '-dirty' ($KREL)，违反 vermagic 契约！" >&2
        exit 1
        ;;
esac

echo "== 产物"
ls -l "$OUT/arch/arm64/boot/Image" "$OUT/Module.symvers"
sha256sum "$OUT/arch/arm64/boot/Image" "$OUT/Module.symvers"

if [ ${#SIGN_MODULES[@]} -gt 0 ]; then
    echo "== 签名模块"
    for m in "${SIGN_MODULES[@]}"; do
        [ -r "$m" ] || { echo "模块不存在: $m" >&2; exit 1; }
        "$OUT/scripts/sign-file" sha512 "$OUT/certs/signing_key.pem" "$OUT/certs/signing_key.x509" "$m"
        echo "   signed: $m"
    done
fi

if [ ${#GATE_DIRS[@]} -gt 0 ]; then
    echo "== ABI 门（严格模式，不吞非零退出码）"
    args=()
    for d in "${GATE_DIRS[@]}"; do args+=(--modules "$d"); done
    if [ -r "$OUT/drivers/android/binder/rust_binder.ko" ]; then
        args+=(--replace "rust_binder.ko=$OUT/drivers/android/binder/rust_binder.ko")
    fi
    python3 "$ROOT/tools/abi-gate.py" \
        --our-symvers "$OUT/Module.symvers" \
        "${args[@]}" \
        --allow-unresolved-prefix mtk_pwrctl_slt_gpio_ \
        --allow-dead-module xr_pmonitor.ko
fi

echo "== 完成: $OUT"
