# ABI 回归门

- 模块 543 个；内核导出 2823；模块间导出 3000
- 内核符号 CRC 不符：**0** 条
- 无法解析导入的模块：**50**
  - mi_wq_dynamic_priority.ko 缺 7：__tracepoint_android_rvh_alloc_and_link_pwqs, __tracepoint_android_rvh_create_worker, __tracepoint_android_vh_blk_mq_delay_run_hw_queue, __tracepoint_android_vh_blk_mq_kick_requeue_list, alloc_workqueue_attrs_noprof, apply_workqueue_attrs_locked
  - xr-clk.ko 缺 11：__clk_get_name, __devres_alloc_node, clk_hw_round_rate, clk_mux_determine_rate_flags, clk_restore_context, clk_save_context
  - xring_ras.ko 缺 1：__tracepoint_android_rvh_arm64_serror_panic
  - sched-walt.ko 缺 102：__balance_callbacks, __cpu_active_mask, __cpu_dying_mask, __migrate_task, __scx_enabled, __task_rq_lock
  - os_cpu_plat_common.ko 缺 1：__tracepoint_android_rvh_finish_prio_fork
  - os_cpu_vip_sched.ko 缺 13：__cpu_active_mask, __sched_proxy_exec, __scx_enabled, activate_task, available_idle_cpu, cpumask_any_distribute
  - xr_cpufreq.ko 缺 20：__tracepoint_android_vh_cpufreq_resolve_freq, __tracepoint_android_vh_freq_qos_add_request, __tracepoint_android_vh_freq_qos_remove_request, __tracepoint_android_vh_freq_qos_update_request, cpufreq_boost_enabled, cpufreq_boost_set_sw
  - xr_ddr.ko 缺 1：devfreq_remove_device
  - xr_dfx.ko 缺 10：__tracepoint_android_vh_ipi_stop, __tracepoint_android_vh_logbuf, console_printk, console_unlock, mem_section, of_address_to_resource
  - xr_bootup_stage1.ko 缺 2：memremap, memunmap

**判定：FAIL**
