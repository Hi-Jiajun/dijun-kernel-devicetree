# 平台身份命名与物理分区/槽位契约

## 1. 三层身份标识边界

在适配 `dijun` 内核、initramfs（`vendor_boot`）及第三方 OS 兼容层时，必须严格区分以下三层命名，避免跨层混用：

| 层次 | `dijun` 标准值 | 来源与出现位置 | 常见误区 |
| --- | --- | --- | --- |
| **平台 / SoC 硬件标识** | `O1_asic` | `/proc/bootconfig` 中 `androidboot.hardware = "O1_asic"`、`androidboot.hardware.platform = "O1_asic"`；原厂 `vendor_boot` ramdisk 内 `/first_stage_ramdisk/fstab.O1_asic` | 不要将机型代号 `dijun` 写入 `androidboot.hardware` / `ohos.boot.hardware`，也不要遗留供体设备平台名 |
| **设备机型代号（Device）** | `dijun` | `ro.product.device=dijun`、机型专属模块 `xiaomi_touch_dijun.ko`、硬件型号 `25042PN24C` | `dts-oss/6.6.30-android15-v/` 中的 `XiaoMi Franklin1 Basic` 仅系早期 OSS 参考标题 |
| **单板 DTBO `board_id`** | `0x090f0000` (O2S PHONE, `rev=0`) | `dtbo` 条目 [`entry05_id090f0000_rev0.dts`](../../dts-reconstructed/6.18.21-os4.0.4.0/dtbo/entry05_id090f0000_rev0.dts)（顶层软链 `o2s_phone_overlay.dts`） | 全机 8 个 DTBO entry（`0x09000001..0x09080101`）对应不同硬件版本，不能只编错别的 ID |

---

## 2. A/B 物理分区精确映射（UFS）

实际分区映射基于 `dijun` 设备实测。注意 **`sdc16..sdc19` 是 `_a` 槽，`sdc48..sdc51` 才是 `_b` 槽**；通过原始块节点读/写备份时切勿仅凭序号猜测槽位（应先读 `sysfs` `PARTNAME` 或 `/dev/block/by-name/*` 核验）。

| 逻辑分区 | `_a` 槽物理节点 | `_b` 槽物理节点 | 字节大小 | 职责说明 |
| --- | --- | --- | ---: | --- |
| `sec_dtbo` | `/dev/block/sdc12` | `/dev/block/sdc44` | 8,388,608 (8 MiB) | 安全侧设备树扩展 |
| `boot_logo` | `/dev/block/sdc15` | `/dev/block/sdc47` | 50,331,648 (48 MiB) | 开机 Splash |
| `dtbo` | `/dev/block/sdc16` | `/dev/block/sdc48` | 25,165,824 (24 MiB) | DTBO 容器（含 8 条目），**不可误认作主 `base.dtb` 载体** |
| `boot` | `/dev/block/sdc17` | `/dev/block/sdc49` | 100,663,296 (96 MiB) | header v4（含通用 `Image` 内核） |
| `init_boot` | `/dev/block/sdc18` | `/dev/block/sdc50` | 16,777,216 (16 MiB) | 一阶段通用 ramdisk（`/init` 等） |
| `vendor_boot` | `/dev/block/sdc19` | `/dev/block/sdc51` | 100,663,296 (96 MiB) | header v4：**承载主 `base.dtb`、vendor ramdisk（含 139 个早期 `.ko`）、bootconfig** |
| `vbmeta` | `/dev/block/sdc20` | `/dev/block/sdc52` | 1,048,576 (1 MiB) | AVB 根描述符 |
| `vbmeta_system` | `/dev/block/sdc21` | `/dev/block/sdc53` | 1,048,576 (1 MiB) | `system` / `system_dlkm` AVB |
| `vbmeta_vendor` | `/dev/block/sdc22` | `/dev/block/sdc54` | 1,048,576 (1 MiB) | `vendor` / `vendor_dlkm` AVB |

### 单份公共分区（非 A/B）

| 分区 | 物理节点 | 字节大小 | 说明 |
| --- | --- | ---: | --- |
| `misc` | `/dev/block/sdc66` | 4,194,304 (4 MiB) | Bootloader Control Block (BCB，如 `bootonce-bootloader`) |
| `rescue` | `/dev/block/sdc67` | 134,217,728 (128 MiB) | 恢复区 |
| `metadata` | `/dev/block/sdc69` | 73,400,320 (70 MiB) | fscrypt / snapshot 元数据 |
| `super` | `/dev/block/sdc78` | 11,274,289,152 (~10.5 GiB) | 逻辑动态分区容器（`fastbootd` 下刷写，bootloader 下不可直接刷逻辑分区） |
| `persist` | `/dev/block/sdd2` | 134,217,728 (128 MiB) | 工厂校准与持久化数据 |

---

## 3. L1 / L2 刷写安全红线

- **L1 软砖区（可救，前提是 fastboot 通道完好）**：`boot`、`init_boot`、`vendor_boot`、`dtbo`、`vbmeta*`、`super`（`fastbootd` 下）、`misc`、`metadata`。刷写上述分区时必须：先确认活跃槽位（`fastboot getvar current-slot`）、只写单槽后缀（如 `vendor_boot_b`）、保留原厂备份与 SHA-256。
- **L2 引导链绝对禁区（严禁修改）**：`xloader_{a,b}`（`sda3`/`sdb3`）、`xrse_{a,b}`（`sda4`/`sdb4`）、`xhee_{a,b}`、`xspm_{a,b}`、`xsps_{a,b}`、`bl2`、`uefi`、`tee` 与各 LUN GPT。fastboot 协议栈由 L2 引导链拉起，损坏将导致无救砖通道。
- **回锁红线**：严禁对已改动的自定义内核/兼容系统执行 `fastboot oem lock` 或线刷包内 `flash_all_lock.sh`。
