#!/usr/bin/env bash
# 重打 dijun 的 vendor_boot（设备树 base DT 实际所在分区，boot 里没有 dtb）。
#
# 依据：unpack_bootimg --format=mkbootimg 对设备 vendor_boot_a.img 给出的参数；
# 用原始部件重打后与设备镜像逐字节一致（已实测），因此替换 DTB 后重打是可靠的。
#
# 用法：
#   DTB=build/b/base.dtb bash scripts/pack-vendor_boot.sh
#   DTB=build/v/O1_basic.dtb OUT=/tmp/vb-test.img bash scripts/pack-vendor_boot.sh
#
# 注意：本脚本只产出镜像文件，不刷机；镜像大小是内容长度，设备分区会按分区尺寸填充。
set -euo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
EX=$ROOT/stock/vendor_boot/extracted
DTB=${DTB:-$ROOT/build/b/base.dtb}
OUT=${OUT:-$ROOT/build/vendor_boot-repacked.img}

for f in "$EX/dtb" "$EX/bootconfig" "$EX/vendor_ramdisk00" "$DTB"; do
    [ -r "$f" ] || { echo "缺少输入: $f" >&2; exit 2; }
done

VENDOR_CMDLINE='softlockup_panic=1 panic=30 hung_task_panic=1 hung_task_timeout_secs=20 ohos.required_mount.vendor=/dev/block/mapper/vendor@/vendor@ext4@ro,barrier=1@wait,required ohos.required_mount.sys_prod=/dev/block/mapper/sys_prod@/sys_prod@ext4@ro,barrier=1@wait,required hardware=O1_asic log_buf_len=16M firmware_class.path=/vendor/firmware,/odm/firmware, loglevel=7 fw_devlink.strict=1 workqueue.power_efficient=true erofs.reserved_pages=64 pcie_port_pm=force ftrace_dump_on_oops loop.max_part=7 launch_boost_enabled dump_display.fingerprint=dijun:OS3.0.304.0.WODCNXM/user: bootconfig'

mkbootimg \
  --header_version 4 --pagesize 4096 \
  --base 0x0 --kernel_offset 0x00200000 --ramdisk_offset 0x04400000 \
  --tags_offset 0x100 --dtb_offset 0x04200000 \
  --vendor_cmdline "$VENDOR_CMDLINE" --board '' \
  --dtb "$DTB" \
  --vendor_bootconfig "$EX/bootconfig" \
  --ramdisk_type 1 --ramdisk_name '' \
  --vendor_ramdisk_fragment "$EX/vendor_ramdisk00" \
  --vendor_boot "$OUT"

echo "写出 $OUT ($(stat -c%s "$OUT") 字节, dtb=$(stat -c%s "$DTB") 字节)"
echo "dtb sha256: $(sha256sum "$DTB" | cut -d' ' -f1)"
