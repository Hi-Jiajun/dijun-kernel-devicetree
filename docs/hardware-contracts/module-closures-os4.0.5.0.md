# OS4.0.5.0 关键子系统模块加载闭包、Type-C 动态重枚举边界与参数硬契约

本清单基于 `OS4.0.5.0.XODCNXM` 原厂模块池（`vendor_boot` 139 个 + `vendor_dlkm` 193 个 = 332 个驱动模块；另有 `system_dlkm` 105 个）与现役 `6.18.32-hmos-opt2`（`6.18.32-4k`，`module_layout = 0x60801db3`）内核的 ELF64 符号/CRC 拓扑解析及真机单变量实证整理 `[已验证]`。

---

## 0. `OS4.0.4.0` → `OS4.0.5.0` 模块池变更摘要 `[已验证]`

- **`vendor_boot`（139 个 `.ko`）**：`vendor_ramdisk00`（`5,408,847` B LZ4 / `19,424,768` B cpio，423 条记录）与 `OS4.0.4.0` **逐字节 100% 相同**（0 新增、0 删除、0 修改）。
- **`vendor_dlkm`（193 个 `.ko`）**：节点数不变，仅 **2 个无线 `.ko`** 重编：
  1. `cfg80211.ko`（`2,208,048` B，`050b384262e58a8d…` → `13e86f054388ab12…`）：仅 `.BTF` 节变化，`.text`/`.data`、`vermagic` 与导入/导出符号 CRC 零变化；
  2. `wlan_drv_gen4m_eap_6639.ko`（`8,602,552` B，`1822e0f1e5ea4bae…` → `1f962c076c38c1a9…`）：同尺寸重编（驱动内置构建时间戳 `20261105192821` → `20261112191732`），导入/导出符号 CRC 零变化。
  - 其余 191 个 `.ko` 及 `modules.dep` / `modules.load` / `modules.softdep` **逐字节一致**。
- **`system_dlkm`（105 个 `.ko`）**：全部 105 个 `.ko` **逐字节一致**（仅 `/etc/build.prop` 构建指纹刷新）。
- **跨版本符号集**：332 个厂商驱动模块导入符号（3,738 条）与导出符号（`symvers/6.18.32-os4.0.5.0/vendor-modules.symvers`，2,518 条，`72982df6f6bb5798…`）相对 `OS4.0.4.0` **0 新增、0 删除、0 CRC 变化**；对 `6.18.32-hmos-opt2`（3,655 条内核导出）执行 `tools/abi-gate.py` 全量通过（`kernel_crc_mismatch=0, module_crc_mismatch=0, unresolved=0`）。

---

## 1. Safe63 零 USB 抖动安全充电闭包 vs 4 个 Type-C 动态重枚举模块边界 `[已验证]`

### 1.1 为什么完整 67 模块充电闭包在运行期动态加载会导致 USB `-32` 断连

对 `bq27z561` + `subpmic_sc6601a` + `xm_charger` + `xm_power` 全套电源/快充模块求传递闭包共得 **67 个模块**。但真机内核日志实证：当 USB 外设（如 ConfigFS ACM 串口或 HDC/ADB Gadget，`e1ac0000.dwc3` 处于 `configured` 态）已在线时，**运行期动态 `insmod` 以下 4 个 Type-C / TCPC / PD 状态机模块会立即触发端口角色重置与 DWC3 Gadget 下线（主机侧报 `-EPIPE / -32` 掉线）**：

| 拓扑序 | 隔离排除模块 | 直接依赖 | 触发 USB 掉线的内核机制 `[已验证]` |
| ---: | --- | --- | --- |
| `#34` | `ex_pd_protocol.ko` | `mca_log, external_tcpc, mca_platform_cp_class, mca_platform_subpmic_cid_class, mca_event, mca_protocol_pd_class` | 注册外部 PD 协议状态机，触发 TCPC 端口重协商 |
| `#46` | `tcpc_sc660x.ko` | `external_tcpc, mca_log` | Sub-PMIC `SC6601A` TCPC 驱动 probe 时重置 CC 状态机至 `AttachWait.SNK`，发出 `typec attach new = 0` |
| `#62` | `mca_xring_usb.ko` | `xring_usb, mca_log, mca_protocol_pd_class` | 将 MCA Type-C 事件桥接至 `xring_usb`，下发 `usb_dwork_handler queue off` 关闭 DWC3 peripheral 会话 |
| `#63` | `protocol_pd_manager.ko` | `mca_log, external_tcpc, mca_strategy_class, mca_xring_usb, xring_usb, mca_protocol_class, mca_protocol_pd_class, mca_event, mca_platform_buckchg_class` | 顶层 PD 策略管理器，依赖 `mca_xring_usb` 驱动端口角色切换 |

> **工程红线**：在维持活动 USB 调试链路（ACM / HDC / ADB）的用户态阶段，**严禁动态 `insmod` 上述 4 个模块**。若需完整 PD 快充握手，上述 4 个模块必须在早期 initramfs 建立 USB Gadget 绑定**之前**完成静态预加载，或仅在离线独立供电场景下加载。

### 1.2 Safe63（63 模块 = 27 预载 + 36 增量）零掉线安全充电闭包 `[已验证]`

从 67 模块全集中剔除上述 4 个 Type-C 动态重枚举模块后，剩余 **63 个模块**经拓扑完整性校验确认：**`missing_depends = []`、`order_violations = []`、`broken_softdeps = []`**（注意 `#20 external_tcpc.ko`、`#13 mca_protocol_class.ko`、`#33 mca_protocol_pd_class.ko` 仅导出被动数据结构与注册表符号，已在早期 `vendor_boot` 静态预载，自身不主动翻转 CC/UDC 状态）。

- **第一部分：`vendor_boot` 已静态预载的 27 个基础模块（运行期幂等跳过）**
  - `#01 hwid`、`#02 miev`、`#03 flowctrl`、`#04 xr_spmi_controller`、`#05 xr_ffa_module`、`#06 xrsp_driver`、`#07 xr_pmic_spmi`、`#08 xr_dfx`、`#09 redriver`、`#10 mca_platform_buckchg_class`、`#13 mca_protocol_class`、`#17 mca_sysfs`、`#18 mca_event`、`#19 mca_log`、`#20 external_tcpc`、`#26 mca_parse_dts`、`#33 mca_protocol_pd_class`、`#42 mca_workqueue`、`#52 securelib`、`#53 dmd`、`#54 xr_timestamp`、`#55 xr_vote_mng`、`#56 xr_pm_comm`、`#57 xr_doze`、`#58 xr_pmic`、`#59 xring_usb`、`#64 fsa4480_i2c`。

- **第二部分：运行期从 `vendor_dlkm` 按序增量加载的 36 个模块（零 USB 抖动）**

| 阶段分组 | 按拓扑序排列的模块名（`#序号`） | 暴露的关键 `/sys` 能力 |
| --- | --- | --- |
| 类与策略框架（10 项） | `#11 mca_platform_fg_ic_ops` → `#12 mca_platform_subpmic_cid_class` → `#14 mca_protocol_qc_class` → `#15 mca_strategy_class` → `#16 mca_strategy_fg_class` → `#21 mca_charge_interface` → `#22 mca_charge_mievent` → `#23 mca_common` → `#24 mca_hwid` → `#25 mca_lpd_detect` | `/sys/class/xm_power/charger/charge_interface/*`（`iin_limit`、`ichg_limit`、`charge_enable`） |
| 电量计与平台类（6 项） | `#27 bq27z561` → `#28 charger_partition` → `#29 mca_business_battery_comp` → `#30 mca_platform_cp_class` → `#31 mca_platform_loadsw_class` → `#32 mca_platform_wireless_class` | `/sys/class/power_supply/battery/*`（`capacity`、`voltage_now`、`current_now`、`temp`、`cycle_count`） |
| 温控、JEITA 与保护（8 项） | `#35 mca_platform_bc12_class` → `#36 mca_smart_charge` → `#37 mca_buckchg_jeita` → `#38 mca_charger_thermal` → `#39 mca_subpmic_sysfs` → `#40 mca_vbat_ovp_monitor` → `#41 mca_wireless_revchg` → `#43 mca_strategy_fg_comp` | `smart_charge/smart_chg`（80% 充电保护）、`charger_thermal/wired_chg_curr`、硬件 JEITA 温控 |
| Sub-PMIC 与 Buck 充电执行（12 项） | `#44 subpmic_sc6601a` → `#45 subpmic_sc6601a_cid` → `#47 xm_utils` → `#48 nanosic_platform` → `#49 xm_charger` → `#50 mca_strategy_buckchg` → `#51 xm_battmngr_init` → `#60 mca_connector_antiburn` → `#61 mca_business_charger_comp` → `#65 subpmic_sc6601a_driver` → `#66 mca_bmd` → `#67 xm_power` | `/sys/class/power_supply/usb/*`、500 mA 安全限流投票（`charge_guard`）闭环，且 `/sys/class/udc/*/state` 全程保持 `configured` |

---

## 2. GPU Stage 0 v2 自包含 7 模块闭包（解耦 `xr_isp.ko`）`[已验证]`

### 2.1 原厂耦合痛点与 Stage 0 v2 解耦方案

- 原厂 `vendor_dlkm` 中的 `mali_kbase.ko`（`1,644,608` B）在 `.modinfo depends` 硬编码依赖 `xr_isp`，迫使加载 GPU 前必须先拉起 `hwid` → `xrisp_wl286*` → `shub_*` → `xr_isp` 共 31 个模块；且原厂 `vendor_dlkm` 漏打了 `xr_gpufreq.ko` 所需的动态调频器模块 `xr_dynamic_governor.ko`，直接加载会导致 `xr_gpufreq` 无 `dynamic` governor 而使 `mali_kbase` probe 失败。
- **GPU Stage 0 v2 闭环方案**（真机实测 `0xd830` Immortalis-G925 16-core、`UK 1.30`、`coherency mode 31` 通过 `[已验证]`）：
  1. 前置总线底座（早期 `vendor_boot` 已就位）：`xring_smmu.ko`、`xr_mem_s1.ko`、`xr_regulator.ko`、`xr_vote_mng.ko`、`xring-noc.ko`、`xr_dfx.ko`；
  2. 固件前置：`/lib/firmware/mali_csffw.bin`（或 `/vendor/firmware/mali_csffw.bin`，`307,200` B，SHA-256 `30f1a912a6bc507b…`，`OS4.0.4.0` 与 `OS4.0.5.0` 逐字节一致）；
  3. **严格按序加载 7 个 GPU 模块**：

| 顺序 | 模块名 | 来源 / 角色 | 关键依赖与说明 |
| ---: | --- | --- | --- |
| 1 | `atf_shmem.ko` | `OS4.0.5.0 vendor_dlkm` | BL31 共享内存通信底座 |
| 2 | `dvfs-gov.ko` | `OS4.0.5.0 vendor_dlkm` | 玄戒通用 DVFS governor 框架 |
| 3 | `xr_dynamic_governor.ko` | 自编补齐（`44,432` B，基于开源 `xring-modules` 构建并通过 `abi-gate.py`） | 注册 `dynamic` devfreq governor（`depends: dvfs-gov`）；**必须在 `xr_gpufreq.ko` 之前加载** |
| 4 | `gpu_hotplug_cdev.ko` | `OS4.0.5.0 vendor_dlkm` | GPU 热插拔冷却设备 |
| 5 | `xr_gpufreq.ko` | `OS4.0.5.0 vendor_dlkm` | GPU DVFS 频率驱动（绑定 `gov=dynamic`，`334.23 MHz ↔ 52.225 MHz`） |
| 6 | `gpufreq_cdev.ko` | `OS4.0.5.0 vendor_dlkm` | GPU 温控频点冷却设备 |
| 7 | `mali_kbase.ko` | 解耦 `xr_isp` 版（`1,628,872` B）或满足全量前置后的原厂版 | 生成 `/dev/mali0`（`misc` 子系统动态次设备号，须配合 `ueventd` 赋权 `0666 system:graphics`） |

---

## 3. 音频与 `CS40L26A` 线性马达 12 / 20 模块两阶段解耦闭包 `[已验证]`

对 `OS4.0.5.0` `vendor_dlkm` 音频与触觉模块执行 ELF64 符号/软依赖拓扑排序，共得 **20 个 `.ko`**（其中 13 个在 `vendor_boot` 内已有同 SHA-256 副本，加载器必须先检查 `/sys/module/<norm_name>` 幂等跳过以防 `-EEXIST`）`[已验证]`。

### 3.1 Stage A（`--stage haptics`，前 12 模块，零 ISP / SensorHub 耦合）

`CS40L26A` 线性马达驱动（I2C `0-0043`，兼容串 `"cirrus,cs40l26a"`）编译在 `xring_audio_hw_third.ko` 内，模块初始化即完成 I2C probe、下载 Halo DSP 固件（`cs40l26.wmfw` `57,264` B + `cs40l26.bin` `8,432` B 等 9 个 `odm:/firmware/cs40l26*` 文件，4.0.4.0 与 4.0.5.0 逐字节一致）并注册 `cs40l26_input`（`EV_FF` `FF_PERIODIC`），**不依赖 ASoC 声卡顶层绑定**：

1. `xring_audio_hw_soc.ko`（`156,040` B，`vendor_dlkm` 独占，`softdep pre: xr_ipc`）
2. `mca_sysfs.ko`（`vendor_boot` 同源，幂等跳过）
3. `mca_event.ko`（同上）
4. `mca_log.ko`（同上）
5. `external_tcpc.ko`（同上）
6. `mca_protocol_class.ko`（同上）
7. `mca_parse_dts.ko`（同上）
8. `mca_protocol_pd_class.ko`（同上）
9. `mca_workqueue.ko`（同上）
10. `mca_platform_buckchg_class.ko`（同上）
11. `fsa4480-i2c.ko`（`76,504` B，`vendor_boot` 同源，幂等跳过）
12. **`xring_audio_hw_third.ko`**（`5,544,832` B，`vendor_dlkm` 独占，内含 `cs40l26` + `cl_dsp` + `cs35l43` + `xring-smartpa`；前置要求 `/lib/firmware/cs40l26*` 已就位）

> **`CS40L26A` 驱动硬契约**：`cs40l26_upload_effect()` 仅接受 `FF_PERIODIC`（`FF_SINE` 或 `FF_CUSTOM`），传入 `FF_RUMBLE` 或 `FF_CONSTANT` 会直接返回 `-EINVAL`；增益通过 `EV_FF / FF_GAIN` 传入 `0..100` 百分比。

### 3.2 Stage B（`--stage full-asoc`，追加 `#13..#20` 共 20 模块，完整 ASoC 声卡）

在 Stage A 基础上继续加载以下 8 个模块以注册完整 ASoC 声卡与路由总成：

13. `xrisp_wl28681c.ko`（`55,248` B，`xr_isp` `softdep pre`）
14. `xrisp_wl28661d.ko`（`33,888` B，`xr_isp` `softdep pre`）
15. `shub_boot_prepare.ko`（`85,072` B，`vendor_boot` 同源）
16. `shub_ipc_drv.ko`（`33,800` B，`vendor_boot` 同源）
17. `shub_app_router.ko`（`83,512` B，`vendor_dlkm` 独占）
18. `xring-ocm.ko`（`48,840` B，`vendor_boot` 同源）
19. `xr_isp.ko`（`1,085,000` B，依赖合法传参的 `hwid.ko`）
20. **`xring_audio_asoc.ko`**（`1,448,632` B，ASoC 声卡顶层驱动）

---

## 4. 存储、早期 USB `peripheral` 设备树契约与显示触控要点 `[已验证]`

1. **`hwid.ko` 参数硬契约**：合法参数名为 `hwid_value:uint` 与 **`project:uint`**（绝非 `hwid_project`）；传错参数会导致 `hwid.ko` 加载失败并在后续加载 `xr_isp.ko` 时因空指针崩溃。
2. **早期 USB UDC 枚举的 `dtbo` 硬前提**：原厂 `dtbo.img`（`OS4.0.4.0` 与 `OS4.0.5.0` 的 `entry05_id090f0000_rev0.dtbo` 逐字节相同）默认未在 `fragment@1`（`target = <&usb>`，即 `/soc/xr_usb@e1890000`）设置 `init-state = "peripheral"`。在未加载上述 4 个 Type-C PD 模块的自定义早期用户态环境中，若直接刷入未打补丁的原厂 `dtbo.img`，`xr_usb_state_init` 不会投递 `event 0x48` 切入 DEVICE 模式，`e1ac0000.dwc3` UDC 不会生成，导致早期 ACM/HDC 等待 UDC 超时回落 bootloader `[已验证]`。务必保持 `dtbo` 中 `&usb` 的 `init-state = "peripheral"` 增量属性。
3. **显示与触控闭包（53 项）**：`OS4.0.5.0` 中 `xring-drm.ko` 与 7 个触控/SensorHub 模块（`shub_boot_prepare.ko`、`shub_ipc_drv.ko`、`tui.ko`、`xiaomi_touch_dijun.ko`、`xr_spi_mmio.ko`、`synaptics_tcm2.ko`、`fts_touch_spi.ko`）及触控固件 `synaptics_spi_dijun.img`（`194,794` B，`edaa698e65a41d16…`）相对 `OS4.0.4.0` 全部逐字节未变，拓扑顺序参见 [`module-closures-os4.0.4.0.md`](module-closures-os4.0.4.0.md)。
