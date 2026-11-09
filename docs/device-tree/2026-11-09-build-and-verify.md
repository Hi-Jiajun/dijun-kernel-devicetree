# 运行记录 2026-11-09：dijun 设备树工程搭建

结果：`make all` 通过，`bash scripts/verify.sh` 13 项 PASS / 0 FAIL。全程只读设备，未写任何分区。

## 1. 素材来源

设备在线（`adb devices` 见 `<device-serial>`），root 可用（SukiSU）。三个只读取件动作：

```
adb exec-out su -c 'dd if=/dev/block/by-name/dtbo_a bs=1M'        > stock/device-dtbo_a.img      # 25,165,824 B, exit 0
adb exec-out su -c 'dd if=/dev/block/by-name/vendor_boot_a bs=1M' > stock/vendor_boot/device-vendor_boot_a.img  # 100,663,296 B, exit 0
adb exec-out su -c 'cat /sys/firmware/fdt'                         > stock/runtime.fdt            # 621,392 B, exit 0
```

旁证：`<nas>/backup/dijun-pdump-20261016/{boot_a,dtbo_a}.img.gz` 解压后的 sha256 与仓库里 `work/ota_capture/fw_419/` 的同名镜像一致（`8563cbf6…`、`9bcf9753…`），说明那批是 OS4 的镜像，不是设备当前 OS3 的分区；OS3 的取件只能从设备上读。

## 2. 解析 DTBO 容器

`scripts/mkdtboimg.py --info` 读出头部（大端）：`magic=0xd7b7ab1e total=2819691 header=32 entry=32 count=8 entries_off=32 page=2048 version=0`。8 个 entry 连续排布、不按页填充，`total_size = 288 + Σ载荷`，与设备容器逐字节吻合。导出后得到 `baseline/dtbo-device/` 下 8 个 `.dtbo`，其中 `0x090f0000` 那份 437,616 B。

`vendor_boot` 解包（`unpack_bootimg`，需先 `unset PYTHONHOME PYTHONPATH`）：header v4、`dtb size: 180674`、vendor_ramdisk 一表一项、bootconfig 206 B、`dtb address 0x08200000`。**boot.img 解包后没有 dtb 段**（`kernel 42,936,832 B`、无 ramdisk），这也印证「设备树不在 boot」。

## 3. 还原与回编（L0/L1）

```
dtc -I dtb -O dts -o dts-reconstructed/base.dts baseline/base.dtb                         # exit 0
dtc -I dtb -O dts -o dts-reconstructed/o2s_phone_overlay.dts baseline/dtbo-device/entry05_id090f0000_rev0.dtbo   # exit 0
dtc -q -@ -I dts -O dtb -o build/b/base.dtb dts-reconstructed/base.dts                 # exit 0
dtc -q -@ -I dts -O dtb -o build/b/o2s_phone_overlay.dtbo dts-reconstructed/o2s_phone_overlay.dts             # exit 0
```

回编结果与设备二进制 sha256 完全一致：base `5ddc32ef…`（180,674 B）、overlay `74ff62ab…`（437,616 B）。反编译会丢注释和 include 结构，但节点/属性/标签（`__symbols__`、`__fixups__`）都保留，所以"无损"是字节级的，不只是语义级。

V 基线一开始编不过：`fatal error: dt-bindings/xring/platform-specific/common/reset/xr_reset_common.h: 没有那个文件或目录`（cpp exit 2）。查 `git ls-files | grep -ci platform-specific` 为 0，确认 OSS 发布缺这一层绑定；11 个缺失头在 `platform/O1/<同路径>` 全部存在，按目标路径拷进工程 `include/dt-bindings/xring/platform-specific/` 后 cpp/dt c 均为 exit 0，产出 175,903 B / 432,669 B。dtc 会刷 `label ... already exists in /__symbols__` 告警（反编译源自带 `__symbols__`，`-@` 又生成一遍），`-q` 压不住，改为重定向到 `build/**/*.dtc.log`，产物字节不变（重编前后 sha 一致）。

## 4. 运行时合并校验

内核树的 `fdtoverlay` 目标直接 `make` 会链接失败（`undefined reference to util_usage/util_version`，exit 2），手工编译通过：

```
gcc -O2 -DNO_YAML -I libfdt -o /tmp/fdtoverlay fdtoverlay.c util.c libfdt/fdt*.c   # exit 0
/tmp/fdtoverlay -i stock/vendor_boot/extracted/dtb -o build/merged-check.dtb baseline/dtbo-device/entry05_id090f0000_rev0.dtbo  # exit 0
```

合并结果 590,286 B，与设备 `/sys/firmware/fdt` 621,392 B 相比：只有 11 个节点多出来（`/ddr-opp-table/opp-0…9`、`/memory@0/superinfo`，引导期注入）和 2 个 OPP 节点少掉，1032 处属性差里绝大多数是 `__symbols__`。用 OS4 的 dtb+overlay 做同样操作则报 `FDT_ERR_NOTFOUND`（版本错配的直接证据），这也反证"必须用同一世代的分区件"。

## 5. 打包（L3）

`scripts/mkdtboimg.py --out build/dtbo-repacked.img --entry baseline/dtbo-device/*.dtbo` → 2,819,691 B，与设备 `dtbo_a` 前缀逐字节一致（`cmp` exit 0）。

`scripts/pack-vendor_boot.sh`（参数取自 `unpack_bootimg --format=mkbootimg`）用原厂 dtb 重打 23,379,968 B，与设备 `vendor_boot_a` 前缀逐字节一致；换 `build/b/base.dtb` 重打后再解包，dtb sha 与输入一致。

## 6. 环境坑

- 所有 python 与内核构建前必须 `unset PYTHONHOME PYTHONPATH`，否则 `/tmp/.mount_DSH-*/usr` 的注入让 python3 起不来（`ModuleNotFoundError: No module named 'encodings'`）。
- AOSP 的 `mkdtimg` 在本机被判 `not allowed to be used`（PATH 保护），所以容器打包自己写，已用设备容器验证等价。
- `unpack_bootimg` 默认解压 vendor_ramdisk（5,408,349 B → 23,181,178 B），重打时直接喂解压后的文件反而与设备镜像逐字节一致；不要自作聪明先压缩。
- `make -C scripts/dtc fdtoverlay` 在这棵 ACK 上缺 `util.c` 的链接规则，需手工编译。

## 7. 未做

真机验证（刷 `vendor_boot` / `dtbo`）按确认范围未执行。设备 `PANIC_ON_OOPS=y`、verity enforcing，且 dtbo 写坏后 BROM 无救砖通道；若要验证，建议只动 `dtbo_a` 并保留 `dtbo_b` 原厂作为退路。

## 8. L2：同一套 DTS 挂进两棵内核树

ACK 6.6.118（`<home>/ack-66118/src`）与 OSS 6.6.30（`<home>/dijun-kernel-oss/common-gki`）都跑了 `make dtbs`，rc 均为 0，dtb-y 三个目标全出，A/B 产物逐字节相同。两次失败与修正都记在 `report/L2-kbuild-挂载验证.md`：`DTC_INCLUDE` 必须带该树自己的 `scripts/dtc/include-prefixes`（否则 cpp 阶段缺 `arm-gic.h`，rc=2）；kbuild 默认不加 `-@`（否则 base 无 `__symbols__`）。修正后工程 `dts/Makefile` 已补 `DTC_FLAGS += -@`，`make kbuild-v/b` 实跑 rc=0，产物在外部 dtstree 的源目录而不是 `O=`。

B 基线 overlay 用树内 dtc 1.6.1 编出 449,808 B，host dtc 1.8.1 编出 437,616 B（与设备一致），base 两边都是 180,674 B；差异原因未查清，已记入风险。

## 9. 可证伪性演示

`bash scripts/demo-patch.sh` 在临时副本的 `/chosen` 里加一个自定义属性，重编后与设备原厂 base.dtb 比：`only in` 两侧均为 0、`属性差异: 1`，RESULT OK（exit 0）。说明"改一处、只报一处"这条回归路径是可信的。
