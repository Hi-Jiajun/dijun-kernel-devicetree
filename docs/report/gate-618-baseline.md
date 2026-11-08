# ABI 回归门

- 模块 404 个；内核导出 2823；模块间导出 2241
- 内核符号 CRC 不符：**9723** 条
  - binder_gki.ko:freezing_slow_path 期望 0xdad9c26d 实际 0xe25751e0
  - bq27z561.ko:i2c_register_driver 期望 0x2fb93727 实际 0xfdc08847
  - bq27z561.ko:i2c_del_driver 期望 0x7488dfce 实际 0x78dfc0ed
  - bq27z561.ko:i2c_smbus_read_word_data 期望 0x9207d876 实际 0xb95fcea4
  - bq27z561.ko:i2c_transfer 期望 0x964e6197 实际 0x31bd0f90
  - bq27z561.ko:i2c_smbus_read_byte_data 期望 0x9207d876 实际 0xb95fcea4
  - bq27z561.ko:i2c_smbus_write_word_data 期望 0x089649e7 实际 0x74ca103e
  - bq27z561.ko:i2c_smbus_write_byte_data 期望 0x036e5be7 实际 0x83d83529
  - bq27z561.ko:devm_kmalloc 期望 0x3c2a1eae 实际 0x409697ff
  - bq27z561.ko:of_get_property 期望 0x91690c67 实际 0xace3a155
- 无法解析导入的模块：**62**
  - btmtk_uart_unify.ko 缺 2：sys_state_doz2nor_unvote, sys_state_doz2nor_vote
  - cpnv.ko 缺 2：memcpy_s, memset_s
  - cpufreq_xres.ko 缺 8：cpu_util_freq_walt, get_walt_window_size, walt_sched_clock, xr_cpufreq_remove_init_limit, xr_is_rtg_freq_locked, xresgov_add_callback
  - dvfs-gov.ko 缺 2：vote_mng_get, vote_mng_msg_send
  - efuse.ko 缺 2：memcpy_s, memset_s
  - fault_report.ko 缺 5：cdev_tevent_add_int, cdev_tevent_add_str, cdev_tevent_alloc, cdev_tevent_destroy, cdev_tevent_write
  - fts_touch_spi.ko 缺 4：sys_state_doz2nor_unvote, sys_state_doz2nor_vote, xring_panel_event_notifier_register, xring_panel_event_notifier_unregister
  - hpc_cdev.ko 缺 1：xr_tsens_read_temp
  - hpc_mitee_crypto.ko 缺 2：get_model_key, memcpy_s
  - hpc_xrp_hw_boot.ko 缺 4：xr_dmabuf_kernel_account, xr_dmabuf_kernel_unaccount, xring_smmu_tbu_ctrl, xring_smmu_tcu_ctrl

**判定：FAIL**
