#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# 离线全量验收：
#   L0  编译全部三代 B 基线（base.dtb + 全部 8 个 dtbo）与自定义 overlays
#   L0h 校验三代 27 个产物的回编一致（dtc >= 1.8 要求逐字节相等；旧版 dtc 回退零结构差异校验）
#   L1  若传入 KERNEL=<树>，编译 V 基线并输出结构 diff
#   L2  fdtoverlay 验证 overlays/custom/*.dtbo 可干净合并到 6.18.21-os4.0.4.0 base.dtb
#   L3  mkdtboimg.py 重打三代 dtbo.img 并用 dtbo-extract.py 校验 8 条目
#   L4  运行 demo-patch.sh、校验 symvers 格式，并扫描仓库确认无敏感字符串/路径泄露
# 退出码：0 全部通过（SKIP 不计失败）；1 有失败项。
set -uo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
pass=0; fail=0
note() { printf '\n== %s\n' "$*"; }
ok()   { printf 'PASS  %s\n' "$*"; pass=$((pass+1)); }
ng()   { printf 'FAIL  %s\n' "$*"; fail=$((fail+1)); }

DTC_VER=$(dtc --version 2>/dev/null | sed -n 's/.*DTC v\{0,1\}\([0-9.]*\).*/\1/p')
DTC_MAJOR=${DTC_VER%%.*}
DTC_MINOR=${DTC_VER#*.}; DTC_MINOR=${DTC_MINOR%%.*}
STRICT_OVERLAY_BYTES=0
if [ -n "$DTC_MAJOR" ] && [ -n "$DTC_MINOR" ]; then
    if [ "$DTC_MAJOR" -gt 1 ] || { [ "$DTC_MAJOR" -eq 1 ] && [ "$DTC_MINOR" -ge 8 ]; }; then
        STRICT_OVERLAY_BYTES=1
    fi
fi
printf 'INFO  dtc=%s (strict_overlay_bytes=%d)\n' "${DTC_VER:-unknown}" "$STRICT_OVERLAY_BYTES"

note "L0 编译三代 B 基线与自定义 overlays"
mkdir -p build
if make -s -B b overlays >build/verify-make.log 2>&1; then
    ok "make b overlays 退出码 0"
else
    ng "make b overlays 失败，见 build/verify-make.log"
fi

for v in 6.6.118-os3 6.18.21-os4.0.0.19 6.18.21-os4.0.4.0; do
    built_base="build/b/$v/base.dtb"
    stock_base="baseline/$v/base.dtb"
    if [ -s "$built_base" ] && [ "$(sha256sum "$built_base" | cut -d' ' -f1)" = "$(sha256sum "$stock_base" | cut -d' ' -f1)" ]; then
        ok "$v/base.dtb 回编字节一致 ($(stat -c%s "$built_base") B)"
    else
        ng "$v/base.dtb 回编不一致"
    fi

    dtbo_byte_eq=0
    dtbo_struct_eq=0
    dtbo_bad=0
    for stock_dtbo in baseline/"$v"/dtbo/*.dtbo; do
        fn=$(basename "$stock_dtbo")
        built_dtbo="build/b/$v/dtbo/$fn"
        if [ ! -s "$built_dtbo" ]; then
            dtbo_bad=$((dtbo_bad + 1))
            continue
        fi
        if [ "$(sha256sum "$built_dtbo" | cut -d' ' -f1)" = "$(sha256sum "$stock_dtbo" | cut -d' ' -f1)" ]; then
            dtbo_byte_eq=$((dtbo_byte_eq + 1))
        elif [ "$STRICT_OVERLAY_BYTES" -eq 0 ] && python3 tools/fdtdiff.py "$stock_dtbo" "$built_dtbo" --overlay >"build/diff-$v-$fn.txt" 2>&1 \
             && grep -q '^only in .* 0$' "build/diff-$v-$fn.txt" \
             && grep -q '^属性差异: 0$' "build/diff-$v-$fn.txt"; then
            dtbo_struct_eq=$((dtbo_struct_eq + 1))
        else
            dtbo_bad=$((dtbo_bad + 1))
        fi
    done
    if [ "$dtbo_bad" -eq 0 ]; then
        ok "$v/dtbo/*.dtbo 8 条目全部通过 (byte_eq=$dtbo_byte_eq, struct_0diff=$dtbo_struct_eq)"
    else
        ng "$v/dtbo/*.dtbo 有 $dtbo_bad 条不匹配 (byte_eq=$dtbo_byte_eq, struct_0diff=$dtbo_struct_eq)"
    fi

    if [ -L "build/b/$v/o2s_phone_overlay.dtbo" ] && [ -s "build/b/$v/o2s_phone_overlay.dtbo" ]; then
        ok "$v/o2s_phone_overlay.dtbo 软链有效"
    else
        ng "$v/o2s_phone_overlay.dtbo 缺失或无效"
    fi
done

note "L1 V 基线（官方 OSS）与 B 基线结构差异（预期存在，只记录不判失败）"
if [ -n "${KERNEL:-}" ]; then
    make -s v >build/verify-make-v.log 2>&1 && ok "make v 退出码 0" || ng "make v 失败，见 build/verify-make-v.log"
    for v in 6.6.118-os3 6.18.21-os4.0.0.19 6.18.21-os4.0.4.0; do
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

note "L2 自定义 overlays 合并验证 (fdtoverlay -> 6.18.21-os4.0.4.0/base.dtb)"
if command -v fdtoverlay >/dev/null 2>&1; then
    for ovl in build/overlays/*.dtbo; do
        [ -s "$ovl" ] || continue
        bn=$(basename "$ovl" .dtbo)
        if fdtoverlay -i build/b/6.18.21-os4.0.4.0/base.dtb -o "build/merged-$bn.dtb" "$ovl" >"build/fdtoverlay-$bn.log" 2>&1; then
            ok "fdtoverlay $bn 合并成功"
        else
            ng "fdtoverlay $bn 合并失败，见 build/fdtoverlay-$bn.log"
        fi
    done
else
    printf 'SKIP  缺少 fdtoverlay，跳过合并检查\n'
fi

note "L3 dtbo 容器重打与条目校验"
for v in 6.6.118-os3 6.18.21-os4.0.0.19 6.18.21-os4.0.4.0; do
    out=build/dtbo-$v.img
    python3 tools/mkdtboimg.py --out "$out" \
        $(for f in baseline/$v/dtbo/*.dtbo; do printf -- '--entry %s ' "$f"; done) >"build/verify-dtbo-$v.log" 2>&1 \
        && python3 tools/dtbo-extract.py --img "$out" --info >>"build/verify-dtbo-$v.log" 2>&1 \
        && grep -q "entries=8" "build/verify-dtbo-$v.log" \
        && ok "dtbo-$v.img 重打并校验 8 条目成功 ($(stat -c%s "$out") B)" \
        || ng "dtbo-$v.img 重打或校验失败"
done

note "L4 工具自检、symvers 格式校验与脱敏门禁"
if bash scripts/demo-patch.sh >build/verify-demo.log 2>&1; then
    ok "demo-patch.sh 精确检出单属性差异"
else
    ng "demo-patch.sh 失败，见 build/verify-demo.log"
fi

if grep -q $'^0x60801db3\tmodule_layout\tvmlinux' symvers/6.18.32-os4.0.4.0/vmlinux-pure.symvers \
   && grep -q $'^0xcf4c0200\tdijun_hmos_ipc_api_v2\tvmlinux' symvers/6.18.32-os4.0.4.0/vmlinux-hmos.symvers \
   && grep -q $'^0x39bc4e1a\tedr_drv_submit_api_sync\t' symvers/6.18.32-os4.0.4.0/vendor-modules.symvers; then
    ok "symvers/6.18.32-os4.0.4.0 三份符号表关键契约齐全"
else
    ng "symvers/6.18.32-os4.0.4.0 缺少关键符号契约"
fi

# 检查所有相对软链无断链
broken_links=$(find . -path ./.git -prune -o -type l ! -exec test -e {} \; -print)
if [ -z "$broken_links" ]; then
    ok "仓库内全部相对软链有效"
else
    ng "存在断链: $broken_links"
fi

if unset PYTHONHOME PYTHONPATH && python3 tools/module-inventory.py --help >/dev/null 2>&1; then
    ok "module-inventory.py CLI 可调用"
else
    ng "module-inventory.py CLI 自检失败"
fi

# 运行完整公开合规与脱敏门禁（仅工作区，CI/make audit 可加 --check-history）
audit_args=()
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    audit_args+=(--check-history)
fi
if bash scripts/audit-public-ready.sh "${audit_args[@]}" >build/verify-sanitize.log 2>&1; then
    ok "公开合规与敏感历史脱敏审计 PASS"
else
    cat build/verify-sanitize.log >&2 || true
    ng "公开合规与脱敏审计失败，见 build/verify-sanitize.log"
fi

printf '\n汇总: PASS=%d FAIL=%d\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
