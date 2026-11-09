# ABI 回归门

- 模块 542 个；内核导出 3990；模块间导出 3000
- 内核符号 CRC 不符：**0** 条
- 无法解析导入的模块：**1**
  - xr_pmonitor.ko 缺 4：lp_mnt_counter_clear, lp_mnt_counter_get, lp_mnt_set, next_op_mode

**判定：FAIL**
