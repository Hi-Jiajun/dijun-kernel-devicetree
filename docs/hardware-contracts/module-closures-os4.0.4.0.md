# OS4.0.4.0 关键子系统模块加载闭包与参数契约

本清单由本仓库 [`tools/module-inventory.py`](../../tools/module-inventory.py) 对 OS4.0.4.0（`6.18.21` 原厂模块池：`vendor_boot` 139 个 + `vendor_dlkm` 193 个 + `system_dlkm` 210 个）执行纯 Python ELF64 解析并按 `depends ∪ 模块间导出符号 ∪ softdep pre:` 拓扑排序实测导出。

> 若某模块同时存在于 `vendor_boot` 与 `vendor_dlkm`（OS4.0.4.0 共计 69 对同名模块），`vendor_boot` 中的模块拥有更高优先级并应在第一阶段按序装载。

---

## 1. `hwid.ko` 模块参数硬契约（极易踩坑）

实测 `vendor_boot/.../extra/xiaomi-modules/hwid/hwid.ko`（23,168 B）的 `.modinfo parmtype` 导出表如下：

| `.modinfo` 合法参数名 | 类型 | 对应 `/proc/bootconfig` 键 | 说明 |
| --- | --- | --- | --- |
| `hwid_value` | `uint` | `androidboot.hwid_value`（示例：`0x90000`） | 硬件版本值 |
| **`project`** | `uint` | `androidboot.hwproject`（示例：`0x1`） | **注意参数名是 `project` 而非 `hwid_project`** |
| `project_name` | `charp` | — | 可选项目名 |
| `build_adc` | `uint` | — | 构建 ADC 值 |
| `project_adc` | `uint` | — | 项目 ADC 值 |
| `hwversion` | `charp` | `androidboot.hwversion`（示例：`1.9.0`） | 可选字符串版本 |

- **错误传参的连锁后果**：若在自定义引导器或 `modules.options` 中误写成 `hwid_project=0x1`，内核 `parse_args()` 会判定为未知参数导致整个 `hwid.ko` 加载失败；下游 `xr_isp.ko` 获取版本字符串为空后触发 `strcmp(NULL, dt_string)` 空指针 Oops 崩溃（在 `PANIC_ON_OOPS=y` 下直接重启）；且即使回退也需注意：`hwid.ko` 一旦被 `xr_ufs.ko` 引用（`refcount >= 1`），运行期无法 `rmmod hwid` 重载，**必须在开机首次装载时通过 `modules.options`（如 `options hwid hwid_value=0x90000 project=0x1`）或等价的 `insmod` 参数一次性传入**。

---

## 2. 存储与平台基础闭包（`xr_ufs` + `hwid`，12 项）

按合法装载顺序排列（1 → 12）：

1. `vendor_boot/.../hwid/hwid.ko`（23,168 B）— 需按第 1 节传入参数
2. `vendor_boot/.../miev/miev.ko`（37,152 B）
3. `vendor_boot/.../rpmb/xr_rpmb.ko`（38,160 B）
4. `vendor_boot/.../spmi/xr-spmi-controller.ko`（27,920 B）
5. `vendor_boot/.../xr_arm_ffa/xr_ffa-module.ko`（79,656 B）
6. `vendor_boot/.../xsp/xsp1/xrsp_driver.ko`（16,736 B，depends/pre: `xr_ffa_module`）
7. `vendor_boot/.../pmic/xr-pmic-spmi.ko`（26,744 B，depends: `xrsp_driver`, pre: `xr_spmi_controller`）
8. `vendor_boot/.../dfx/xr_dfx.ko`（211,008 B，depends: `xr_pmic_spmi`）
9. `vendor_boot/.../tee/mitee.ko`（288,432 B，depends: `xr_ffa_module, xr_dfx, miev`，params: `bind_core_mask:ulong`, `workers_count:uint`）
10. `vendor_boot/.../securelib/securelib.ko`（32,672 B）
11. `vendor_boot/.../fbe/fbe.ko`（29,560 B，depends/pre: `mitee, securelib`）
12. `vendor_boot/.../ufs/xr_ufs.ko`（937,440 B，depends: `fbe, xr_rpmb, hwid`，params: `use_mcq_mode:bool`, `use_adaptive_txeq:bool`, `use_txeq_presets:bool`, `txeq_presets_selected:array of bool`）

---

## 3. USB / UDC Gadget 闭包（`xring_dwc3` + `xring_usb` + `xring_usb_adsp_stub`，10 项）

在早期 ramdisk 阶段单独拉起 USB Gadget（如 ConfigFS ACM/FFS/ADB）时的最小闭合依赖序：

1. `vendor_boot/.../perf/flowctrl/flowctrl.ko`（36,544 B）
2. `vendor_boot/.../usb/xring-dwc3.ko`（358,128 B）
3. `vendor_boot/.../mca/mca_hardware_ic/redriver/redriver.ko`（24,384 B）
4. `vendor_boot/.../secure/securelib/securelib.ko`（32,672 B）
5. `vendor_boot/.../timestamp/xr_timestamp.ko`（26,384 B）
6. `vendor_boot/.../vote_mng/xr_vote_mng.ko`（64,320 B）
7. `vendor_boot/.../pm_comm/xr_pm_comm.ko`（19,488 B，pre: `xr_vote_mng`）
8. `vendor_boot/.../doze/xr_doze.ko`（22,440 B，pre: `xr_pm_comm xr_timestamp`）
9. `vendor_boot/.../usb/xring_usb.ko`（162,240 B，depends: `redriver, xr_doze, flowctrl`, pre: `xr_doze`）
10. `vendor_boot/.../usb/xring_usb_adsp_stub.ko`（16,168 B，depends/pre: `xring_usb`）

> 若仅需最小 USB/ACM 诊断，必须确认 `dtbo` 节点处于 `peripheral` 模式并带上 `xring_usb_adsp_stub.ko`（或 `xring_usb_adsp_v1.ko` 配合 ADSP 服务）以完成 UDC 枚举。

---

## 4. 显示与触控闭包（`xring_drm` + `synaptics_tcm2` + `xiaomi_touch_dijun`，53 项要点）

`xring-drm.ko` 与触摸驱动 `xiaomi_touch_dijun.ko` / `synaptics_tcm2.ko` 共享 `vendor_boot` 与 `vendor_dlkm` 跨分区闭包（总计 53 个 `.ko`）：

- **关键前置 `softdep` 约束**：`xring-drm.ko` 的 `.modinfo` 声明 `softdep pre: xring_usb xr_regulator pinctrl_xr perf_monitor`；且 `xr_regulator.ko` 自身声明 `softdep pre: xring_i2c xr_timestamp`。只按硬 `depends` 加载会漏掉 `xr_regulator`、`pinctrl-xr` 与 `xring_i2c`，引发 DPU 上电/时钟 probe 失败或 SLUB 异常。
- **`vendor_dlkm` 末端触摸序列**（需在 `xring-drm.ko` 成功绑定之后依次加载）：
  - `vendor_dlkm/lib/modules/shub_boot_prepare.ko`（85,072 B）
  - `vendor_dlkm/lib/modules/shub_ipc_drv.ko`（33,800 B，depends: `xr_timestamp, xr_dfx, xr_ipc, shub_boot_prepare`）
  - `vendor_dlkm/lib/modules/tui.ko`（63,640 B，depends: `mitee, xring_drm, xr_mem_s1`）
  - `vendor_dlkm/lib/modules/xiaomi_touch_dijun.ko`（233,176 B，depends: `shub_ipc_drv, xring_drm, xr_timestamp, miev`）
  - `vendor_dlkm/lib/modules/xr_spi_mmio.ko`（78,680 B）
  - `vendor_dlkm/lib/modules/synaptics_tcm2.ko`（599,184 B，depends: `xiaomi_touch_dijun, tui, xr_doze, xr_spi_mmio`，params: `tune_debug_enable:int`）

---

## 5. 电量计与充电栈闭包（`bq27z561` + `subpmic_sc6601a` + `xm_charger`，17 项）

`bq27z561.ko`（电量计）、`subpmic_sc6601a.ko`（Sub-PMIC）与 `xm_charger.ko`（主充电管理）全部在 `vendor_boot/extra/xring-modules/mca/` 与 `vendor_dlkm/lib/modules/` 中有成套副本，共 17 个模块，关键加载链路：

1. 基础类与事件底座：`miev.ko` → `mca_platform_buckchg_class.ko`、`mca_platform_fg_ic_ops.ko`、`mca_strategy_class.ko`、`mca_strategy_fg_class.ko`、`mca_sysfs.ko` → `mca_event.ko` → `mca_log.ko`（param: `charge_boot_mode:uint`）→ `mca_charge_mievent.ko` → `mca_parse_dts.ko`
2. 电量计：`bq27z561.ko`（169,744 B，depends: `mca_sysfs, mca_log, mca_parse_dts, mca_platform_fg_ic_ops, mca_strategy_class`）
3. 协议类与充电执行：`mca_platform_cp_class.ko`、`mca_platform_wireless_class.ko`、`subpmic_sc6601a.ko`（27,816 B）→ `xm_utils.ko` → `nanosic_platform.ko` → `xm_charger.ko`（65,712 B）

> 若自建内核/极简 ramdisk 未加载这一闭包，`power_supply` 类将完全为空，充电电流与电芯温控将退回 UEFI 遗留状态而不可观测、不可调控。

---

## 6. 原厂 GPU 闭包（`mali_kbase` + `xr_gpufreq`，31 项要点）

原厂 `vendor_dlkm/lib/modules/mali_kbase.ko`（1,644,608 B）的拓扑闭包共 31 个模块（包含上述存储/TEE/IPC 基础链、`atf_shmem.ko`、`xr_gpufreq.ko`、`xring-noc.ko`、`xring-ocm.ko`、`millet.ko`、`gpu_hotplug_cdev.ko` 与 **`xr_isp.ko`**）：

- **ISP ↔ GPU 跨子系统硬耦合**：因 `mali_kbase.ko` 的 `depends` 直接列出 `xr_isp`（同时依赖 `xring_noc`、`xr_gpufreq`、`xr_mem_s1`、`xr_dfx`），所以若想在设备上加载原厂 `mali_kbase.ko`，前置闭包中 **`hwid.ko`（含合法参数）→ `xrisp_wl28661d.ko` / `xrisp_wl28681c.ko` → `xr_isp.ko`** 缺一不可。
- **`mali_kbase.ko` 主要 `.modinfo parmtype`**：`fw_name:string`、`csf_firmware_boot_timeout_ms:uint`、`large_page_conf:charp`、`kbase_page_migration_enabled:int`、`override_l2_size:byte`、`override_l2_hash:byte`、`l2_hash_values:array of uint`、`fully_backed_gpf_memory:bool`、`corestack_driver_control:bool`、`gpu_metrics_tp_emit_interval_ns:ulong`；另有可选前置 `softdep pre: memory_group_manager`。
- 自行用工具生成完整 JSON/Markdown 闭包表的方法：
  ```bash
  unset PYTHONHOME PYTHONPATH
  python3 tools/module-inventory.py \
    --tree vendor_boot:<extracted-vendor_boot-dir> \
    --tree vendor_dlkm:<extracted-vendor_dlkm-dir> \
    --closure xring_drm,synaptics_tcm2 \
    --closure-out closure-display-touch.md
  ```
