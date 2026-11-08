# ABI 回归门

- 模块 194 个；内核导出 2823；模块间导出 1759
- 内核符号 CRC 不符：**0** 条
- 无法解析导入的模块：**62**
  - btmtk_uart_unify.ko 缺 7：hci_alloc_dev_priv, hci_free_dev, hci_recv_frame, hci_register_dev, hci_unregister_dev, sys_state_doz2nor_unvote
  - cfg80211.ko 缺 7：rfkill_alloc, rfkill_blocked, rfkill_destroy, rfkill_register, rfkill_resume_polling, rfkill_set_hw_state_reason
  - cpnv.ko 缺 2：memcpy_s, memset_s
  - cpufreq_xres.ko 缺 8：cpu_util_freq_walt, get_walt_window_size, walt_sched_clock, xr_cpufreq_remove_init_limit, xr_is_rtg_freq_locked, xresgov_add_callback
  - dvfs-gov.ko 缺 2：vote_mng_get, vote_mng_msg_send
  - efuse.ko 缺 2：memcpy_s, memset_s
  - fault_report.ko 缺 5：cdev_tevent_add_int, cdev_tevent_add_str, cdev_tevent_alloc, cdev_tevent_destroy, cdev_tevent_write
  - fts_touch_spi.ko 缺 4：sys_state_doz2nor_unvote, sys_state_doz2nor_vote, xring_panel_event_notifier_register, xring_panel_event_notifier_unregister
  - hpc_cdev.ko 缺 1：xr_tsens_read_temp
  - hpc_mitee_crypto.ko 缺 2：get_model_key, memcpy_s

**判定：FAIL**
