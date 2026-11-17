#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# 将自编内核 Image 打包为 dijun 可用的 header v4 boot.img（仅含 kernel，无 ramdisk/cmdline），
# 并在临时目录自动回环 unpack_bootimg 校验内核载荷逐字节一致。
#
# 用法：
#   scripts/pack-boot.sh --kernel <Image> --out <boot.img> [--pad-size <bytes>]
#
# 说明：dijun OS4 原厂 boot 分区为 100663296 B (96 MiB)，一般快速刷写也可保持内容实际大小（~42 MB）。
set -euo pipefail
unset PYTHONHOME PYTHONPATH

KERNEL_IMG=""
OUT=""
PAD_SIZE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --kernel) KERNEL_IMG=${2:?}; shift 2;;
        --out) OUT=${2:?}; shift 2;;
        --pad-size) PAD_SIZE=${2:?}; shift 2;;
        -h|--help) sed -n '2,10p' "$0"; exit 0;;
        *) echo "未知参数: $1" >&2; exit 2;;
    esac
done

[ -r "$KERNEL_IMG" ] || { echo "缺少内核 Image (--kernel): $KERNEL_IMG" >&2; exit 2; }
[ -n "$OUT" ] || { echo "缺少输出路径 (--out)" >&2; exit 2; }

for tool in unpack_bootimg mkbootimg; do
    command -v "$tool" >/dev/null 2>&1 || { echo "缺少工具: $tool" >&2; exit 2; }
done

TMP_BASE="${TMPDIR:-${XDG_CACHE_HOME:-$HOME/.cache}/dsh-tmp}"
mkdir -p "$TMP_BASE"
WORK=$(mktemp -d -p "$TMP_BASE" pack-boot.XXXXXX)
trap 'find "$WORK" -depth -delete' EXIT

mkdir -p "$(dirname "$OUT")" "$WORK/verify"
mkbootimg --header_version 4 --kernel "$KERNEL_IMG" --output "$OUT"

if [ "$PAD_SIZE" -gt 0 ]; then
    cur_size=$(stat -c%s "$OUT")
    if [ "$cur_size" -gt "$PAD_SIZE" ]; then
        echo "错误: boot.img ($cur_size B) 大于目标 --pad-size ($PAD_SIZE B)" >&2
        exit 1
    fi
    if [ "$cur_size" -lt "$PAD_SIZE" ]; then
        truncate -s "$PAD_SIZE" "$OUT"
    fi
fi

unpack_bootimg --boot_img "$OUT" --out "$WORK/verify" >/dev/null
cmp "$KERNEL_IMG" "$WORK/verify/kernel"

echo "回环校验 PASS: kernel=$(stat -c%s "$KERNEL_IMG") B, boot=$(stat -c%s "$OUT") B"
sha256sum "$KERNEL_IMG" "$OUT"
