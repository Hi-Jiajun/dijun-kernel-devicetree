#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# 可证伪性演示：在 B 基线里改一个属性，验证工具链只报出这一处差异。
#
# 做法：复制 dts-reconstructed/<baseline>/base.dts 到临时目录，在 /chosen 节点里加一个自定义属性，
# 重新编译，与对应 baseline/<baseline>/base.dtb 做结构比较；期望 0 处节点差异、恰好 1 处属性差异。
# 不改工程里的任何源文件，产物放于 TMPDIR 或 ~/.cache/dsh-tmp 下并在退出时清理。
set -euo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BASELINE_VER="6.18.21-os4.0.5.0"
KEEP_TMP=0

while [ $# -gt 0 ]; do
    case "$1" in
        --baseline) BASELINE_VER=${2:?}; shift 2;;
        --keep) KEEP_TMP=1; shift;;
        -h|--help) sed -n '2,9p' "$0"; exit 0;;
        *) echo "未知参数: $1" >&2; exit 2;;
    esac
done

SRC_DTS="$ROOT/dts-reconstructed/$BASELINE_VER/base.dts"
REF_DTB="$ROOT/baseline/$BASELINE_VER/base.dtb"
[ -r "$SRC_DTS" ] || { echo "缺少 DTS: $SRC_DTS" >&2; exit 2; }
[ -r "$REF_DTB" ] || { echo "缺少基线 DTB: $REF_DTB" >&2; exit 2; }

TMP_BASE="${TMPDIR:-${XDG_CACHE_HOME:-$HOME/.cache}/dsh-tmp}"
mkdir -p "$TMP_BASE"
T=$(mktemp -d -p "$TMP_BASE" dijun-dts-demo.XXXXXX)
cleanup() {
    if [ "$KEEP_TMP" -eq 0 ] && [ -n "${T:-}" ] && [ -d "$T" ]; then
        find "$T" -depth -delete
    fi
}
trap cleanup EXIT

python3 - "$SRC_DTS" "$T/base-demo.dts" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding='utf-8') as f:
    lines = f.read().splitlines(True)
out = []
done = False
for line in lines:
    out.append(line)
    if not done and line.strip().endswith('chosen {'):
        indent = line[:len(line) - len(line.lstrip())] + '\t'
        out.append('%sdijun,demo = "device-tree-workshop";\n' % indent)
        done = True
if not done:
    raise SystemExit('没找到 /chosen 节点，源文件格式变了？')
with open(dst, 'w', encoding='utf-8') as f:
    f.write(''.join(out))
PY

dtc -q -@ -I dts -O dtb -o "$T/base-demo.dtb" "$T/base-demo.dts" 2>"$T/dtc.log"
python3 "$ROOT/tools/fdtdiff.py" "$REF_DTB" "$T/base-demo.dtb" --max-diff 5 >"$T/diff.txt" 2>&1
python3 - "$T/diff.txt" <<'PY'
import sys
txt = open(sys.argv[1], encoding='utf-8').read()
nodes = [l for l in txt.splitlines() if l.startswith('only in')]
props = [l for l in txt.splitlines() if l.startswith('属性差异')]
print('\n'.join(nodes + props))
ok = (
    len(nodes) == 2
    and all(l.split()[-1] == '0' for l in nodes)
    and len(props) == 1
    and props[0].split(':')[-1].strip() == '1'
)
print('RESULT:', 'OK（差异恰好 1 处，符合预期）' if ok else 'UNEXPECTED（差异数量不符）')
sys.exit(0 if ok else 1)
PY
if [ "$KEEP_TMP" -eq 1 ]; then
    echo "临时目录保留: $T"
fi
