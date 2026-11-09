#!/usr/bin/env bash
# 离线验收脚本（L0–L3）。全部离线，不写设备分区。
# 退出码：0 = 全部通过；1 = 有失败项。每项都打印真实命令结果。
set -uo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
pass=0
fail=0
note() { printf '\n== %s\n' "$*"; }
ok()   { printf 'PASS  %s\n' "$*"; pass=$((pass+1)); }
ng()   { printf 'FAIL  %s\n' "$*"; fail=$((fail+1)); }

note "L0 编译：B 基线（V 基线可选，需 KERNEL）"
if [ -n "${KERNEL:-}" ]; then TARGET=all; else TARGET=b; fi
if make -s -B $TARGET >build/verify-make.log 2>&1; then ok "make $TARGET 退出码 0"; else ng "make $TARGET 失败，见 build/verify-make.log"; fi
if [ -z "${KERNEL:-}" ]; then
    printf 'SKIP  未设置 KERNEL，跳过 V 基线与结构 diff\n'
fi
for f in build/v/O1_basic.dtb build/v/o2s_phone_overlay.dtbo build/b/base.dtb build/b/o2s_phone_overlay.dtbo; do
    [ -s "$f" ] && ok "产物存在 $f ($(stat -c%s "$f") B)" || ng "缺产物 $f"
done

note "L1a B 基线回编字节一致（设备分区二进制 == DTS 重新编译）"
for pair in "build/b/base.dtb baseline/base.dtb" "build/b/o2s_phone_overlay.dtbo baseline/dtbo-device/entry05_id090f0000_rev0.dtbo"; do
    set -- $pair
    if [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$(sha256sum "$2" | cut -d' ' -f1)" ]; then
        ok "sha256 一致 $(basename "$2")"
    else
        ng "sha256 不一致 $(basename "$2")"
    fi
done

note "L1b V 基线（官方 OSS）与设备实际 B 基线结构差异（预期存在，只记录不判失败）"
python3 tools/fdtdiff.py baseline/base.dtb build/v/O1_basic.dtb --max-diff 0 >docs/reports/l1-v-vs-b-base.txt 2>&1 \
    && ok "结构 diff 已写入 report/l1-v-vs-b-base.txt" || ng "结构 diff 运行失败"
python3 tools/fdtdiff.py baseline/dtbo-device/entry05_id090f0000_rev0.dtbo build/v/o2s_phone_overlay.dtbo --overlay --max-diff 0 >docs/reports/l1-v-vs-b-overlay.txt 2>&1 \
    && ok "overlay diff 已写入 report/l1-v-vs-b-overlay.txt" || ng "overlay diff 运行失败"
grep -m1 'only in' report/l1-v-vs-b-base.txt || true

note "L1c 运行时 DT 校验：设备 vendor_boot dtb + 设备 dtbo 的 O2S entry 可合并"
if [ -r baseline/vendor_boot/extracted/dtb ] && command -v $ROOT/build/tools/fdtoverlay >/dev/null 2>&1; then
    $ROOT/build/tools/fdtoverlay -i baseline/vendor_boot/extracted/dtb -o build/merged-check.dtb baseline/dtbo-device/entry05_id090f0000_rev0.dtbo >/dev/null 2>&1 \
        && ok "fdtoverlay 合并成功（base+vendor overlay）" || ng "fdtoverlay 合并失败"
else
    printf 'SKIP  fdtoverlay 或 vendor_boot dtb 不可用（工具需自编：见 report/运行记录）\n'
fi

note "L3a dtbo.img 容器同构（用设备 8 个 entry 重打，与设备容器逐字节比较前缀）"
python3 tools/mkdtboimg.py --out build/dtbo-repacked.img $(for f in baseline/dtbo-device/*.dtbo; do printf -- '--entry %s ' "$f"; done) >build/verify-dtbo.log 2>&1
if [ ! -r baseline/device-dtbo_a.img ]; then
    printf 'SKIP  本地没有原厂 dtbo 容器（baseline/device-dtbo_a.img），跳过容器同构对比\n'
elif [ -s build/dtbo-repacked.img ] && cmp -n "$(stat -c%s build/dtbo-repacked.img)" build/dtbo-repacked.img baseline/device-dtbo_a.img; then
    ok "dtbo 重打与设备 dtbo_a 前缀一致 ($(stat -c%s build/dtbo-repacked.img) B)"
else
    ng "dtbo 重打不一致，见 build/verify-dtbo.log"
fi

note "L3b vendor_boot 重打（原厂 dtb 应逐字节复现；换 dtb 后可解析回原样）"
if [ ! -r baseline/vendor_boot/extracted/dtb ] || [ ! -r baseline/vendor_boot/extracted/bootconfig ]; then
    printf 'SKIP  本地没有 vendor_boot 解包件（baseline/vendor_boot/extracted），跳过重打验证\n'
else
OUT=$ROOT/build/tmp/dijun-vb-stock.img DTB=baseline/vendor_boot/extracted/dtb bash scripts/pack-vendor_boot.sh >build/verify-vb.log 2>&1
if [ -s $ROOT/build/tmp/dijun-vb-stock.img ] && cmp -n "$(stat -c%s $ROOT/build/tmp/dijun-vb-stock.img)" $ROOT/build/tmp/dijun-vb-stock.img baseline/vendor_boot/device-vendor_boot_a.img; then
    ok "原厂 dtb 重打与设备 vendor_boot_a 前缀一致 ($(stat -c%s $ROOT/build/tmp/dijun-vb-stock.img) B)"
else
    ng "vendor_boot 重打不一致，见 build/verify-vb.log"
fi
OUT=$ROOT/build/tmp/dijun-vb-b.img DTB=build/b/base.dtb bash scripts/pack-vendor_boot.sh >>build/verify-vb.log 2>&1
if [ -s $ROOT/build/tmp/dijun-vb-b.img ]; then
    mkdir -p build/vb-check && unpack_bootimg --boot_img $ROOT/build/tmp/dijun-vb-b.img --out build/vb-check >/dev/null 2>&1
    if [ "$(sha256sum build/vb-check/dtb | cut -d' ' -f1)" = "$(sha256sum build/b/base.dtb | cut -d' ' -f1)" ]; then
        ok "替换 dtb 后重打的 vendor_boot 可解析回同一 dtb"
    else
        ng "重打后 dtb 不一致"
    fi
else
    ng "替换 dtb 重打失败"
fi

fi

printf '\n汇总: PASS=%d FAIL=%d\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
