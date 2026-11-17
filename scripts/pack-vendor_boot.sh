#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# 重打 dijun 的 vendor_boot（从指定底包原镜像动态继承全部头字段、offsets、cmdline、bootconfig 与 ramdisk，
# 仅替换 DTB（以及可选的 ramdisk），避免硬编码 OS3/OS4 偏移与 cmdline 造成污染）。
#
# 用法：
#   scripts/pack-vendor_boot.sh --stock-img <vendor_boot.img> --dtb <new.dtb> \
#       [--ramdisk <new_ramdisk>] [--out <out.img>] [--pad-to-stock]
#
# 兼容环境变量：STOCK_VENDOR_BOOT / DTB / OUT
set -euo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
STOCK_IMG="${STOCK_VENDOR_BOOT:-}"
DTB="${DTB:-}"
RAMDISK=""
OUT="${OUT:-$ROOT/build/vendor_boot-repacked.img}"
PAD_TO_STOCK=0

while [ $# -gt 0 ]; do
    case "$1" in
        --stock-img) STOCK_IMG=${2:?}; shift 2;;
        --dtb) DTB=${2:?}; shift 2;;
        --ramdisk) RAMDISK=${2:?}; shift 2;;
        --out) OUT=${2:?}; shift 2;;
        --pad-to-stock) PAD_TO_STOCK=1; shift;;
        -h|--help) sed -n '2,12p' "$0"; exit 0;;
        *) echo "未知参数: $1" >&2; exit 2;;
    esac
done

[ -r "$STOCK_IMG" ] || { echo "缺少原厂或基底镜像 (--stock-img): $STOCK_IMG" >&2; exit 2; }
[ -r "$DTB" ] || { echo "缺少 DTB (--dtb): $DTB" >&2; exit 2; }
if [ -n "$RAMDISK" ] && [ ! -r "$RAMDISK" ]; then
    echo "缺少 ramdisk (--ramdisk): $RAMDISK" >&2
    exit 2
fi

for tool in unpack_bootimg mkbootimg; do
    command -v "$tool" >/dev/null 2>&1 || { echo "缺少工具: $tool" >&2; exit 2; }
done

TMP_BASE="${TMPDIR:-${XDG_CACHE_HOME:-$HOME/.cache}/dsh-tmp}"
mkdir -p "$TMP_BASE"
WORK=$(mktemp -d -p "$TMP_BASE" pack-vb.XXXXXX)
trap 'find "$WORK" -depth -delete' EXIT

mkdir -p "$WORK/stock" "$WORK/verify" "$(dirname "$OUT")"

python3 - "$STOCK_IMG" "$DTB" "$RAMDISK" "$OUT" "$WORK" "$PAD_TO_STOCK" <<'PY'
import os
import subprocess
import sys

stock_img, new_dtb, new_ramdisk, out_img, work_dir, pad_flag = sys.argv[1:7]
stock_dir = os.path.join(work_dir, 'stock')
verify_dir = os.path.join(work_dir, 'verify')

p = subprocess.run(
    ['unpack_bootimg', '--boot_img', stock_img, '--out', stock_dir, '--format=mkbootimg', '-0'],
    capture_output=True,
)
if p.returncode != 0:
    sys.stderr.write(p.stderr.decode('utf-8', 'replace'))
    raise SystemExit('unpack_bootimg 失败')

raw_parts = p.stdout.split(b'\0')
if raw_parts and raw_parts[-1] == b'':
    raw_parts = raw_parts[:-1]
args = [x.decode('utf-8') for x in raw_parts]

replaced_dtb = False
out_args = []
i = 0
while i < len(args):
    tok = args[i]
    out_args.append(tok)
    if tok == '--dtb' and i + 1 < len(args):
        out_args.append(os.path.abspath(new_dtb))
        replaced_dtb = True
        i += 2
        continue
    if tok == '--vendor_ramdisk_fragment' and new_ramdisk and i + 1 < len(args):
        out_args.append(os.path.abspath(new_ramdisk))
        i += 2
        continue
    i += 1

if not replaced_dtb:
    out_args.extend(['--dtb', os.path.abspath(new_dtb)])

out_args.extend(['--vendor_boot', os.path.abspath(out_img)])
r = subprocess.run(['mkbootimg'] + out_args, capture_output=True, text=True)
if r.returncode != 0:
    sys.stderr.write(r.stderr)
    raise SystemExit('mkbootimg 打包失败')

stock_size = os.path.getsize(stock_img)
cur_size = os.path.getsize(out_img)
if pad_flag == '1':
    if cur_size > stock_size:
        raise SystemExit('打包后镜像 (%d B) 超过原镜像尺寸 (%d B)，拒绝截断' % (cur_size, stock_size))
    if cur_size < stock_size:
        with open(out_img, 'ab') as f:
            f.write(b'\x00' * (stock_size - cur_size))

# 回环解包校验
vp = subprocess.run(['unpack_bootimg', '--boot_img', out_img, '--out', verify_dir], capture_output=True, text=True)
if vp.returncode != 0:
    sys.stderr.write(vp.stderr)
    raise SystemExit('回环解包校验失败')

expected_dtb = open(new_dtb, 'rb').read()
actual_dtb = open(os.path.join(verify_dir, 'dtb'), 'rb').read()
if expected_dtb != actual_dtb:
    raise SystemExit('回环校验失败: 写入的 dtb 与输入不一致')

exp_rd_path = new_ramdisk if new_ramdisk else os.path.join(stock_dir, 'vendor_ramdisk00')
actual_rd_path = os.path.join(verify_dir, 'vendor_ramdisk00')
if os.path.exists(exp_rd_path) and open(exp_rd_path, 'rb').read() != open(actual_rd_path, 'rb').read():
    raise SystemExit('回环校验失败: vendor_ramdisk00 与输入不一致')

exp_bc_path = os.path.join(stock_dir, 'bootconfig')
actual_bc_path = os.path.join(verify_dir, 'bootconfig')
if os.path.exists(exp_bc_path) and open(exp_bc_path, 'rb').read() != open(actual_bc_path, 'rb').read():
    raise SystemExit('回环校验失败: bootconfig 与原镜像不一致')

cmd_idx = out_args.index('--vendor_cmdline') + 1 if '--vendor_cmdline' in out_args else -1
if cmd_idx >= 0:
    print('vendor_cmdline:', out_args[cmd_idx])
print('回环校验 PASS: dtb=%d B, final_img=%d B' % (len(actual_dtb), os.path.getsize(out_img)))
PY

echo "输出镜像: $OUT"
sha256sum "$DTB" "$OUT"
