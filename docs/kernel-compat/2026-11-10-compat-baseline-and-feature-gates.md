# 运行记录 2026-11-10：兼容基线复现与功能开关验证

## 1. 准备

```
# 模块来源（全部离线）
os3-vendor_boot  385 个 .ko  ← OS3.0.304 vendor_boot.img 解包（lz4 → cpio）
vendor_dlkm      201 个 .ko  ← dijun-blobs/root/vendor_dlkm
system_dlkm      本地无镜像，未纳入
```

模块清单与依赖图：`module-inventory.py`（586 个模块、3,044 个模块间导出符号、4,385 条依赖边）。
白名单：`stock-symbols.txt`（原厂 `Module.symvers` 的 9,090 个符号），仅用于 `UNUSED_KSYMS_WHITELIST` 指向，保持 `TRIM_UNUSED_KSYMS=y` 的原厂语义。

## 2. 构建矩阵（全部 `make ... ARCH=arm64 LLVM=1 -j16 KBUILD_MODULES= vmlinux`，clang r510928）

| 目录 | 配置 | 退出码 | 耗时 | CRC 相同/交集 |
| --- | --- | --- | --- | --- |
| out | 关 DEBUG_INFO/BTF、TRIM、PROTECT | 0 | 1m49s | 2,115 / 9,090 |
| out2 | 原厂配置（仅换白名单路径） | 0 | 2m09s | **9,090 / 9,090** |
| out3 | out2 + 关 TRIM | 0 | — | 9,090 / 9,090 |
| out4 | out3 + 关 DEBUG_INFO/BTF（增量） | 0 | — | 2,115 / 9,090 |
| out5 | out4 配置、干净目录重编 | 0 | — | 2,115 / 9,090 |
| out7_pidns | out2 + `PID_NS=y`（干净目录） | 0 | — | 9,090 / 9,090 |
| out7_cgpids | out2 + `CGROUP_PIDS=y`（干净目录） | 0 | — | 5,948 / 9,090 |

## 3. 根因定位

- 对比 out2 与 out5 的 `#SYMVER` 记录：同一符号（如 `_dev_info`：`0x2137b691` vs `0x523e56c6`）在对象级就不同。
- 用两次构建各自的 `.cmd` 还原 `clang -E -D__GENKSYMS__` 输入并 diff：差异是 `__user` 的展开——有 BTF 时是 `__attribute__((btf_type_tag("user")))`，无 BTF 时为空。
- 依据：`include/linux/compiler_types.h:11-16` 的 `BTF_TYPE_TAG` 条件；设备配置里 `DEBUG_INFO_BTF=y`、`PAHOLE_HAS_BTF_TAG=y`。

## 4. 功能开关

- `PID_NS=y`：CRC 100%，无新增导出，ABI 无影响。
- `CGROUP_PIDS=y`：`enum cgroup_subsys_id` 中间插入 `pids_cgrp_id`，后续 ID 后移；3,142 个导出符号 CRC 变化。genksyms 输入 diff 只显示三处新增（enum 成员、`extern struct cgroup_subsys pids_cgrp_subsys`、`static_key_true ..._enabled_key`），说明是枚举值/声明顺序引起的类型字符串变化。

## 5. 未做与限制

- 未刷机、未验证模块实际加载与运行时行为。
- `system_dlkm` 未纳入；`wwan_gpio_pwrctl` 的 2 个符号仍无提供方。
- KCFI 只做了 836 条共有 typeid 的比对，未覆盖全部间接调用。
- `out*` 目录共约 3 GB，位于本实验目录，可清理。
