# ABI 回归门

- 模块 404 个；内核导出 2823；模块间导出 2241
- 内核符号 CRC 不符：**6377** 条
  - 6lowpan.ko:register_netdevice 期望 0xf6011eda 实际 0x25b4e1ec
  - 6lowpan.ko:unregister_netdevice_queue 期望 0x15fc0dc5 实际 0xfa0e282d
  - 6lowpan.ko:addrconf_add_linklocal 期望 0xeb08e084 实际 0x11f4cb0a
  - 6lowpan.ko:skb_pull 期望 0x0efe08e4 实际 0x05641b1d
  - 6lowpan.ko:pskb_expand_head 期望 0x2772acda 实际 0x51c7f0be
  - 6lowpan.ko:skb_push 期望 0x0efe08e4 实际 0x05641b1d
  - 6lowpan.ko:__pskb_pull_tail 期望 0x439f7f0a 实际 0x4e16e5df
  - 6lowpan.ko:netdev_warn 期望 0xe492b2d4 实际 0x2da7e7cf
  - 6lowpan.ko:__ndisc_fill_addr_option 期望 0x91348d22 实际 0x4c4c3c99
  - 6lowpan.ko:addrconf_prefix_rcv_add_addr 期望 0x5b5d8b38 实际 0x48261a8d
- 无法解析导入的模块：**62**
  - rust_binder.ko 缺 60：RUST_BINDER_LAYOUT, _RINvNtCs3o2tGsuHyou_4core9panicking13assert_failedjjEB4_, _RNvMNtCsdfZWD8DztAw_6kernel5errorNtB2_5Error10from_errno, _RNvMNtCsdfZWD8DztAw_6kernel7id_poolNtB2_14ReallocRequest7realloc, _RNvMNtNtCsdfZWD8DztAw_6kernel3net7netlinkNtB2_13NetlinkSkBuff11genlmsg_put, _RNvMNtNtCsdfZWD8DztAw_6kernel3net7netlinkNtB2_13NetlinkSkBuff3new
  - btmtk_uart_unify.ko 缺 2：sys_state_doz2nor_unvote, sys_state_doz2nor_vote
  - cpnv.ko 缺 2：memcpy_s, memset_s
  - cpufreq_xres.ko 缺 8：cpu_util_freq_walt, get_walt_window_size, walt_sched_clock, xr_cpufreq_remove_init_limit, xr_is_rtg_freq_locked, xresgov_add_callback
  - dvfs-gov.ko 缺 2：vote_mng_get, vote_mng_msg_send
  - efuse.ko 缺 2：memcpy_s, memset_s
  - fault_report.ko 缺 5：cdev_tevent_add_int, cdev_tevent_add_str, cdev_tevent_alloc, cdev_tevent_destroy, cdev_tevent_write
  - fts_touch_spi.ko 缺 4：sys_state_doz2nor_unvote, sys_state_doz2nor_vote, xring_panel_event_notifier_register, xring_panel_event_notifier_unregister
  - hpc_cdev.ko 缺 1：xr_tsens_read_temp
  - hpc_mitee_crypto.ko 缺 2：get_model_key, memcpy_s

**判定：FAIL**
