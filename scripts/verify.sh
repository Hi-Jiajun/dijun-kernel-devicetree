#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# 离线验收：两代 B 基线回编哈希、V/B 结构 diff、dtbo 容器重打（需要对应原厂容器时）。
# 退出码：0 全部通过（SKIP 不计失败）；1 有失败项。
set -uo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
pass=0; fail=0
note() { printf '\n== %s\n' "$*"; }
ok()   { printf 'PASS  %s\n' "$*"; pass=$((pass+1)); }
ng()   { printf 'FAIL  %s\n' "$*"; fail=$((fail+1)); }

note "L0 编译 B 两代基线"
if make -s -B b >build/verify-make.log 2>&1; then ok "make b 退出码 0"; else ng "make b 失败，见 build/verify-make.log"; fi

for v in 6.6.118-os3 6.18.21-os4; do
    for pair in "base.dtb" "o2s_phone_overlay.dtbo"; do
        built=build/b/$v/$pair
        base=baseline/$v/$pair
        [ -s "$built" ] && ok "产物存在 $built ($(stat -c%s "$built") B)" || ng "缺产物 $built"
        if [ -r "$base" ]; then
            if [ "$(sha256sum "$built" | cut -d' ' -f1)" = "$(sha256sum "$base" | cut -d' ' -f1)" ]; then
                ok "$v $pair 回编字节一致"
            else
                ng "$v $pair 回编不一致"
            fi
        fi
    done
done

note "L1 V 基线（官方 OSS）与 B 基线结构差异（预期存在，只记录不判失败）"
if [ -n "${KERNEL:-}" ]; then
    make -s v >build/verify-make-v.log 2>&1 && ok "make v 退出码 0" || ng "make v 失败，见 build/verify-make-v.log"
    for v in 6.6.118-os3 6.18.21-os4; do
        python3 tools/fdtdiff.py "baseline/$v/base.dtb" build/v/O1_basic.dtb --max-diff 0 \
            >"docs/reports/l1-v-vs-$v-base.txt" 2>&1 \
            && ok "结构 diff -> docs/reports/l1-v-vs-$v-base.txt" || ng "结构 diff 失败（$v）"
        python3 tools/fdtdiff.py "$(ls baseline/$v/dtbo/entry*_id090f0000_rev0.dtbo)" build/v/o2s_phone_overlay.dtbo --overlay --max-diff 0 \
            >"docs/reports/l1-v-vs-$v-overlay.txt" 2>&1 \
            && ok "overlay diff -> docs/reports/l1-v-vs-$v-overlay.txt" || ng "overlay diff 失败（$v）"
    done
else
    printf 'SKIP  未设置 KERNEL，跳过 V 基线与结构 diff\n'
fi

note "L3 dtbo 容器重打（需要原厂容器文件时才比较）"
for v in 6.6.118-os3 6.18.21-os4; do
    tag=${v#*-}
    out=build/dtbo-$v.img
    python3 tools/mkdtboimg.py --out "$out" \
        $(for f in baseline/$v/dtbo/*.dtbo; do printf -- '--entry %s ' "$f"; done) >"build/verify-dtbo-$v.log" 2>&1 \
        && ok "dtbo 重打成功 $out ($(stat -c%s "$out") B)" || ng "dtbo 重打失败（$v）"
    container=baseline/$v/dtbo.img
    if [ -r "$container" ]; then
        cmp -n "$(stat -c%s "$out")" "$out" "$container" && ok "$v 容器与基线逐字节一致" || ng "$v 容器不一致"
    else
        printf 'SKIP  未保存 %s 原厂容器（baseline/%s/dtbo.img），只校验条目回编\n' "$v" "$v"
    fi
done

printf '\n汇总: PASS=%d FAIL=%d\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
