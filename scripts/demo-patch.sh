#!/usr/bin/env bash
# 可证伪性演示：在 B 基线里改一个属性，验证工具链只报出这一处差异。
#
# 做法：复制 dts-reconstructed/base.dts 到临时目录，在 /chosen 节点里加一个自定义属性，
# 重新编译，与设备原厂 base.dtb 做结构比较；期望 exactly 1 处属性差异、0 处节点差异。
# 不改工程里的任何源文件，产物写 /tmp。
set -euo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
T=$(mktemp -d <home>/dijun-dts-demo.XXXXXX)
python3 - "$ROOT/dts-reconstructed/base.dts" "$T/base-demo.dts" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
lines = open(src, encoding='utf-8').read().splitlines(True)
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
open(dst, 'w', encoding='utf-8').write(''.join(out))
PY
dtc -q -@ -I dts -O dtb -o "$T/base-demo.dtb" "$T/base-demo.dts" 2>"$T/dtc.log"
python3 "$ROOT/tools/fdtdiff.py" "$ROOT/baseline/base.dtb" "$T/base-demo.dtb" --max-diff 5 >"$T/diff.txt" 2>&1
python3 - "$T/diff.txt" <<'PY'
import sys
txt = open(sys.argv[1], encoding='utf-8').read()
nodes = [l for l in txt.splitlines() if l.startswith('only in')]
props = [l for l in txt.splitlines() if l.startswith('属性差异')]
print('\n'.join(nodes + props))
ok = all('0' in l.split()[-1] for l in nodes) and props and props[0].split(':')[-1].strip() == '1'
print('RESULT:', 'OK（差异恰好 1 处，符合预期）' if ok else 'UNEXPECTED（差异数量不符）')
sys.exit(0 if ok else 1)
PY
echo "临时目录: $T"
