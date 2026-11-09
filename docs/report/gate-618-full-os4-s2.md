# ABI 回归门

- 模块 543 个；内核导出 3568；模块间导出 3000
- 内核符号 CRC 不符：**0** 条
- 无法解析导入的模块：**3**
  - wwan_gpio_pwrctl.ko 缺 2：mtk_pwrctl_slt_gpio_init, mtk_pwrctl_slt_gpio_uninit
  - xr_pmonitor.ko 缺 4：lp_mnt_counter_clear, lp_mnt_counter_get, lp_mnt_set, next_op_mode
  - rust_binder.ko 缺 60：RUST_BINDER_LAYOUT, _RINvNtCs3o2tGsuHyou_4core9panicking13assert_failedjjEB4_, _RNvMNtCsdfZWD8DztAw_6kernel5errorNtB2_5Error10from_errno, _RNvMNtCsdfZWD8DztAw_6kernel7id_poolNtB2_14ReallocRequest7realloc, _RNvMNtNtCsdfZWD8DztAw_6kernel3net7netlinkNtB2_13NetlinkSkBuff11genlmsg_put, _RNvMNtNtCsdfZWD8DztAw_6kernel3net7netlinkNtB2_13NetlinkSkBuff3new

**判定：FAIL**
