# P1 实际训练曝光报告

两来源均完成9001–9100各100新batches，总计13,107,200 transitions。无额外eval/render，无自动延长，诊断checkpoint不promotion。

核心测量结果：全体有余量B控制步=0；联合ready控制步=0。这是新进程100batch内实际训练曝光，不是natural评估能力或稳态证明。

## 集中结论

- 训练实际有1,294,760个B控制步，普通E5 snapshot确实写入9,631次、staged实际加载B 2,086次，但有余量B步/入口/已加载状态均未观察到。C/ready、clean、E6/E7新事件为0；对应release-open、clean质量和clean后persistence/tuck/open等reward激活为0。arm-tangent、arc与handoff奖励则有实际非零支付，不能将全部后段reward概括为无曝光。
- D原始状态有474,501个控制步，release首次接触转移事件2,381次；clean为0，D且clean/release的reward active步数为0。原始D和release标志不能充当合格clean释放。实际加载的phase3来自上游自动snapshot，不是成功D1/D5/D25采集。
- 默认低margin与后续行为已分开：自然出生14,565个实际暴露episode中，j2首次恢复≥0.07有13,356个，j3只有17个；六关节min恢复有16个，均在P_S1 Stage1，未形成有余量B。Stage0的j3 target均值0、近限位向外target步数0；Stage1相应比例四侧99.136%–99.788%，Stage2≥99.998%，实际q仍接近上限0。这支持调查Stage1开始的持续target与余量恢复路径，不能只把低margin归于默认姿态。
- 这些是9001–9100新进程的有限训练曝光事实，不是9000原进程的全历史，也不是natural策略能力评估。P1没有发现被P0 natural隐藏的高margin B或合格C/clean-D曝光。P1问题已得到有界回答；P2处理变量仍未选择，不自动改reward/reset比例，也不延长P1。若下一阶段立项，直接中介应包含Stage1的q/target与恢复、B入口margin及同一步联合ready，不能只看Stage4占比或E5 admission。

实际runner墙钟（含启动/退出）：P_S1=41.83分钟、P_S2=42.31分钟，合计约1.40 GPU占用小时；较原约1.2小时估计高，新增batches和transitions未超预算。四个9050/9100 checkpoint已CPU读取，global_step分别准确，均有33个optimizer states。启动日志存在GPU foundation/GLFW显示初始化报文，后续scene setup、训练和最终child/wrapper均成功；保留原日志，不将这些报文抹去或推定为policy故障。


## B/C/D与联合ready

| 来源/侧/出生 | 控制步 | B / 有余量B步 | C / D步 | ready步 / 独立episode | ready最长(步) | 有余量新E5入口 |
| --- | --- | --- | --- | --- | --- | --- |
| P_S1/left/natural | 2547674 | 230123 / 0 | 0 / 63688 | 0 / 0 | 0 | 0 |
| P_S1/left/staged | 729126 | 121917 / 0 | 0 / 21988 | 0 / 0 | 0 | 0 |
| P_S1/right/natural | 2547349 | 161382 / 0 | 0 / 65126 | 0 / 0 | 0 | 0 |
| P_S1/right/staged | 729451 | 117322 / 0 | 0 / 16918 | 0 / 0 | 0 | 0 |
| P_S2/left/natural | 2468849 | 237997 / 0 | 0 / 81333 | 0 / 0 | 0 | 0 |
| P_S2/left/staged | 807951 | 114715 / 0 | 0 / 47190 | 0 / 0 | 0 | 0 |
| P_S2/right/natural | 2540119 | 211646 / 0 | 0 / 126444 | 0 / 0 | 0 | 0 |
| P_S2/right/staged | 736681 | 99658 / 0 | 0 / 51814 | 0 / 0 | 0 | 0 |

B/C/D为stage≥4的实际subphase；D可由premature release产生，不自动等同clean释放。D且clean/release的直接对应门可查post_release_arm_default_target_quality的active_mask_steps。高margin门为六实际关节release公式min≥0.07。newE5入口排除snapshot继承事件；实际加载的B/C/D另见reset数据。独立ready episode从逐episode记录去重，不把各10batch窗口episode数直接相加。

## 上游余量恢复

| 来源/侧/出生 | 实际暴露episode | 出生已高margin | 从低恢复 | 完成且从未恢复 | 尚未恢复且右截断 | 首次恢复stage |
| --- | --- | --- | --- | --- | --- | --- |
| P_S1/left/natural | 3645 | 0 | 5 | 3266 | 374 | {'1': 5} |
| P_S1/left/staged | 2322 | 0 | 0 | 2186 | 136 | {} |
| P_S1/right/natural | 3671 | 0 | 11 | 3297 | 363 | {'1': 11} |
| P_S1/right/staged | 2312 | 0 | 0 | 2165 | 147 | {} |
| P_S2/left/natural | 3588 | 0 | 0 | 3213 | 375 | {} |
| P_S2/left/staged | 2208 | 0 | 0 | 2072 | 136 | {} |
| P_S2/right/natural | 3661 | 0 | 0 | 3294 | 367 | {} |
| P_S2/right/staged | 2338 | 0 | 0 | 2195 | 143 | {} |

| 来源/侧/出生/joint | 出生有余量episode | 从低首次恢复episode | 首次恢复age中位(控制步) | 首次恢复stage |
| --- | --- | --- | --- | --- |
| P_S1/left/natural/arm_j2 | 0 | 3373 | 93 | {'1': 3366, '2': 7} |
| P_S1/left/natural/arm_j3 | 0 | 5 | 9 | {'1': 5} |
| P_S1/left/natural/arm_j5 | 3645 | 0 | 缺失 | {} |
| P_S1/left/staged/arm_j2 | 1684 | 638 | 8.0 | {'1': 596, '4': 38, '2': 4} |
| P_S1/left/staged/arm_j3 | 0 | 0 | 缺失 | {} |
| P_S1/left/staged/arm_j5 | 1455 | 865 | 18 | {'2': 242, '3': 577, '4': 46} |
| P_S1/right/natural/arm_j2 | 0 | 3358 | 95.0 | {'1': 3356, '2': 2} |
| P_S1/right/natural/arm_j3 | 0 | 11 | 9 | {'1': 11} |
| P_S1/right/natural/arm_j5 | 3671 | 0 | 缺失 | {} |
| P_S1/right/staged/arm_j2 | 1595 | 715 | 6 | {'1': 589, '4': 124, '2': 2} |
| P_S1/right/staged/arm_j3 | 0 | 0 | 缺失 | {} |
| P_S1/right/staged/arm_j5 | 1302 | 992 | 24.0 | {'2': 420, '3': 150, '4': 422} |
| P_S2/left/natural/arm_j2 | 0 | 3268 | 94.0 | {'1': 3219, '2': 49} |
| P_S2/left/natural/arm_j3 | 0 | 0 | 缺失 | {} |
| P_S2/left/natural/arm_j5 | 3588 | 0 | 缺失 | {} |
| P_S2/left/staged/arm_j2 | 1647 | 560 | 7.0 | {'1': 548, '2': 12} |
| P_S2/left/staged/arm_j3 | 0 | 0 | 缺失 | {} |
| P_S2/left/staged/arm_j5 | 677 | 0 | 缺失 | {} |
| P_S2/right/natural/arm_j2 | 0 | 3357 | 98 | {'1': 3304, '2': 53} |
| P_S2/right/natural/arm_j3 | 0 | 1 | 104 | {'1': 1} |
| P_S2/right/natural/arm_j5 | 3661 | 0 | 缺失 | {} |
| P_S2/right/staged/arm_j2 | 1734 | 602 | 7.0 | {'1': 579, '2': 23} |
| P_S2/right/staged/arm_j3 | 0 | 0 | 缺失 | {} |
| P_S2/right/staged/arm_j5 | 795 | 0 | 缺失 | {} |

| 来源/侧/出生/stage | 控制步 | j2/j3/j5近限位向外target步 | j2/j3/j5实际q均值 | j2/j3/j5target均值 | 六关节margin≥.07步 |
| --- | --- | --- | --- | --- | --- |
| P_S1/left/natural/0 | 326827 | 0/0/0 | 0.0003/0.0001/0.5100 | 0.0000/0.0000/0.5000 | 0 |
| P_S1/left/natural/1 | 165672 | 5109/165320/109246 | 0.7931/-0.0001/-0.9163 | 0.8187/3.0746/-1.9237 | 50 |
| P_S1/left/natural/2 | 80940 | 0/80940/67870 | 1.0771/0.0000/-1.1942 | 1.0864/3.7106/-2.1616 | 0 |
| P_S1/left/staged/1 | 28639 | 677/28574/18463 | 0.7602/0.0001/-0.8957 | 0.7887/2.9732/-1.9078 | 0 |
| P_S1/left/staged/2 | 26542 | 0/26542/22214 | 1.0775/0.0000/-1.1941 | 1.0873/3.7037/-2.1068 | 0 |
| P_S1/right/natural/0 | 342725 | 0/0/0 | 0.0003/0.0001/0.5099 | 0.0000/0.0000/0.5000 | 0 |
| P_S1/right/natural/1 | 164925 | 2532/164483/92839 | 0.7403/-0.0002/-0.8960 | 0.7657/3.1179/-1.7187 | 67 |
| P_S1/right/natural/2 | 83383 | 1/83383/56200 | 0.9541/0.0001/-1.1584 | 0.9486/3.7315/-1.7020 | 0 |
| P_S1/right/staged/1 | 27304 | 435/27227/13734 | 0.6904/0.0001/-0.8660 | 0.7169/2.9782/-1.5968 | 0 |
| P_S1/right/staged/2 | 27850 | 0/27850/17799 | 0.9525/0.0001/-1.1527 | 0.9496/3.7180/-1.5931 | 0 |
| P_S2/left/natural/0 | 328742 | 0/0/0 | 0.0002/0.0001/0.5100 | 0.0000/0.0000/0.5000 | 0 |
| P_S2/left/natural/1 | 152427 | 6915/151429/85727 | 0.9602/0.0000/-0.8671 | 0.9880/1.6854/-1.9355 | 0 |
| P_S2/left/natural/2 | 78439 | 2/78439/74724 | 1.1945/0.0000/-1.2010 | 1.1982/2.4678/-2.9980 | 0 |
| P_S2/left/staged/1 | 24276 | 260/24049/13078 | 0.9537/0.0001/-0.8458 | 0.9928/1.5274/-1.8271 | 0 |
| P_S2/left/staged/2 | 25554 | 0/25554/24354 | 1.1916/0.0000/-1.1999 | 1.1948/2.3898/-2.9957 | 0 |
| P_S2/right/natural/0 | 345913 | 0/0/0 | 0.0002/0.0001/0.5099 | 0.0000/0.0000/0.5000 | 0 |
| P_S2/right/natural/1 | 155254 | 8079/153913/76241 | 0.8770/-0.0000/-0.8373 | 0.9005/1.6332/-1.6348 | 0 |
| P_S2/right/natural/2 | 81682 | 0/81681/75834 | 1.0885/0.0001/-1.1929 | 1.0825/2.3378/-2.8579 | 0 |
| P_S2/right/staged/1 | 25659 | 321/25406/12205 | 0.8654/0.0001/-0.8193 | 0.9023/1.4381/-1.5676 | 0 |
| P_S2/right/staged/2 | 29218 | 1/29218/27188 | 1.0823/0.0001/-1.1915 | 1.0771/2.2220/-2.8774 | 0 |

默认j2=0、j3=0在相应限位。低margin出生不直接说明策略错误；上表分开记录实际q、执行target、低余量且target指向限位外的步数和实际首次恢复。loaded时已高margin不算“恢复”。首次per-joint/min恢复在`upstream_and_entry_landmarks.jsonl.gz`中带age_control_steps与episode_counter；生产init_at_random_ep_len保留，不能将随机初始化的counter当真实执行时长。完成episode从未恢复与预算结束仍未恢复的右截断episode分开。

## 事件与状态持续时间

| 来源/侧/出生 | release 首次/flag步 | clean 首次/flag步 | E6 首次/flag步 | E7 首次/flag步 |
| --- | --- | --- | --- | --- |
| P_S1/left/natural | 217 / 97502 | 0 / 0 | 0 / 0 | 0 / 0 |
| P_S1/left/staged | 169 / 42056 | 0 / 0 | 0 / 0 | 0 / 0 |
| P_S1/right/natural | 181 / 96727 | 0 / 0 | 0 / 0 | 0 / 0 |
| P_S1/right/staged | 231 / 46057 | 0 / 0 | 0 / 0 | 0 / 0 |
| P_S2/left/natural | 394 / 121330 | 0 / 0 | 0 / 0 | 0 / 0 |
| P_S2/left/staged | 244 / 67274 | 0 / 0 | 0 / 0 | 0 / 0 |
| P_S2/right/natural | 533 / 189082 | 0 / 0 | 0 / 0 | 0 / 0 |
| P_S2/right/staged | 412 / 94889 | 0 / 0 | 0 / 0 | 0 / 0 |

首次发生排除reset时继承的flags；flag步数可包括继承后的状态持续，不代表新事件次数。release与clean不混同，E6/E7不以flag总步数当成功episode数。

## reset、snapshot与库存

| 来源/侧/出生 | 实际reset stage0/1/2/3/4/5 | 实际snapshot写入 |
| --- | --- | --- |
| P_S1/left/natural | 3645/0/0/0/0/0 | {'stage_entry_stage1_phase0': 3377, 'stage_entry_stage2_phase0': 3300, 'stage_entry_stage3_phase0': 3189, 'stage_entry_stage2_phase3': 30, 'stage_entry_stage3_phase3': 119, 'E5_stage4_phase1': 2567} |
| P_S1/left/staged | 0/598/590/602/533/0 | {'stage_entry_stage2_phase0': 530, 'stage_entry_stage3_phase0': 1081, 'stage_entry_stage3_phase3': 38, 'stage_entry_stage2_phase3': 4, 'E5_stage4_phase1': 6} |
| P_S1/right/natural | 3672/0/0/0/0/0 | {'stage_entry_stage1_phase0': 3362, 'stage_entry_stage2_phase0': 3305, 'stage_entry_stage3_phase0': 3179, 'stage_entry_stage3_phase3': 124, 'stage_entry_stage2_phase3': 18, 'E5_stage4_phase1': 2155} |
| P_S1/right/staged | 0/592/614/606/500/0 | {'stage_entry_stage2_phase0': 525, 'stage_entry_stage3_phase0': 1109, 'stage_entry_stage3_phase3': 29, 'E5_stage4_phase1': 3, 'stage_entry_stage2_phase3': 1} |
| P_S2/left/natural | 3589/0/0/0/0/0 | {'stage_entry_stage1_phase0': 3278, 'stage_entry_stage2_phase0': 3208, 'stage_entry_stage3_phase0': 3102, 'stage_entry_stage3_phase3': 113, 'E5_stage4_phase1': 2477, 'stage_entry_stage2_phase3': 16} |
| P_S2/left/staged | 0/552/548/560/548/0 | {'stage_entry_stage2_phase0': 499, 'stage_entry_stage3_phase0': 1011, 'E5_stage4_phase1': 89, 'stage_entry_stage3_phase3': 33, 'stage_entry_stage2_phase3': 3} |
| P_S2/right/natural | 3662/0/0/0/0/0 | {'stage_entry_stage1_phase0': 3360, 'stage_entry_stage2_phase0': 3272, 'stage_entry_stage3_phase0': 3048, 'stage_entry_stage3_phase3': 238, 'stage_entry_stage2_phase3': 35, 'E5_stage4_phase1': 2299} |
| P_S2/right/staged | 0/591/640/603/505/0 | {'stage_entry_stage3_phase0': 1085, 'stage_entry_stage2_phase0': 528, 'stage_entry_stage3_phase3': 80, 'E5_stage4_phase1': 35, 'stage_entry_stage2_phase3': 4} |

| 来源 | 实际staged加载phase及高margin次数 |
| --- | --- |
| P_S1 | {'left/staged/phase0': 1761, 'right/staged/phase0': 1781, 'left/staged/phase1': 533, 'left/staged/phase3': 29, 'right/staged/phase1': 500, 'right/staged/phase3': 31} |
| P_S2 | {'left/staged/phase0': 1636, 'right/staged/phase0': 1791, 'left/staged/phase3': 24, 'right/staged/phase1': 505, 'left/staged/phase1': 548, 'right/staged/phase3': 43} |

| 来源/侧/窗口末 | stage0..5有效槽位 | 实际写入槽位phase组成（含高margin） |
| --- | --- | --- |
| P_S1/left/9010 | [102400, 553, 556, 563, 4, 0] | {'stage1_phase0_slots': 553, 'stage2_phase0_slots': 552, 'stage3_phase0_slots': 547, 'stage2_phase3_slots': 4, 'stage3_phase3_slots': 16, 'stage4_phase1_slots': 4} |
| P_S1/left/9050 | [102400, 1818, 2042, 2304, 1238, 0] | {'stage1_phase0_slots': 1818, 'stage2_phase0_slots': 2022, 'stage3_phase0_slots': 2226, 'stage2_phase3_slots': 20, 'stage3_phase3_slots': 78, 'stage4_phase1_slots': 1238} |
| P_S1/left/9100 | [102400, 3377, 3864, 4427, 2573, 0] | {'stage1_phase0_slots': 3377, 'stage2_phase0_slots': 3830, 'stage3_phase0_slots': 4270, 'stage2_phase3_slots': 34, 'stage3_phase3_slots': 157, 'stage4_phase1_slots': 2573} |
| P_S1/right/9010 | [102400, 557, 563, 567, 1, 0] | {'stage1_phase0_slots': 557, 'stage2_phase0_slots': 559, 'stage3_phase0_slots': 545, 'stage3_phase3_slots': 22, 'stage2_phase3_slots': 4, 'stage4_phase1_slots': 1} |
| P_S1/right/9050 | [102400, 1827, 2054, 2324, 1000, 0] | {'stage1_phase0_slots': 1827, 'stage2_phase0_slots': 2045, 'stage3_phase0_slots': 2243, 'stage3_phase3_slots': 81, 'stage2_phase3_slots': 9, 'stage4_phase1_slots': 1000} |
| P_S1/right/9100 | [102400, 3362, 3849, 4441, 2158, 0] | {'stage1_phase0_slots': 3362, 'stage2_phase0_slots': 3830, 'stage3_phase0_slots': 4288, 'stage3_phase3_slots': 153, 'stage2_phase3_slots': 19, 'stage4_phase1_slots': 2158} |
| P_S2/left/9010 | [102400, 581, 567, 571, 17, 0] | {'stage1_phase0_slots': 581, 'stage2_phase0_slots': 567, 'stage3_phase0_slots': 554, 'stage3_phase3_slots': 17, 'stage4_phase1_slots': 17} |
| P_S2/left/9050 | [102400, 1796, 1976, 2213, 1227, 0] | {'stage1_phase0_slots': 1796, 'stage2_phase0_slots': 1970, 'stage3_phase0_slots': 2148, 'stage3_phase3_slots': 65, 'stage4_phase1_slots': 1227, 'stage2_phase3_slots': 6} |
| P_S2/left/9100 | [102400, 3278, 3726, 4259, 2566, 0] | {'stage1_phase0_slots': 3278, 'stage2_phase0_slots': 3707, 'stage3_phase0_slots': 4113, 'stage3_phase3_slots': 146, 'stage4_phase1_slots': 2566, 'stage2_phase3_slots': 19} |
| P_S2/right/9010 | [102400, 575, 561, 565, 10, 0] | {'stage1_phase0_slots': 575, 'stage2_phase0_slots': 556, 'stage3_phase0_slots': 527, 'stage3_phase3_slots': 38, 'stage2_phase3_slots': 5, 'stage4_phase1_slots': 10} |
| P_S2/right/9050 | [102400, 1845, 2036, 2315, 1058, 0] | {'stage1_phase0_slots': 1845, 'stage2_phase0_slots': 2020, 'stage3_phase0_slots': 2170, 'stage3_phase3_slots': 145, 'stage2_phase3_slots': 16, 'stage4_phase1_slots': 1058} |
| P_S2/right/9100 | [102400, 3360, 3839, 4451, 2334, 0] | {'stage1_phase0_slots': 3360, 'stage2_phase0_slots': 3800, 'stage3_phase0_slots': 4133, 'stage3_phase3_slots': 318, 'stage2_phase3_slots': 39, 'stage4_phase1_slots': 2334} |

实际stage抽样按每env库存mask重加权。Stage0抽到的sample index未用于加载，`sample_index=null`，另保留`drawn_sample_index`审计RNG实际抽样。`snapshot_writes.jsonl.gz`记录每次实际写入；reset文件记录真正选中slot及最后观测写入信息。有效库存按环形容量取实际有效槽位，Stage0初始化库存不计运行写入。JSON每窗口inventory按side报告，natural/staged两行重复该side库存，禁止重复求和。

## 后段奖励真实曝光

| 来源/侧/出生/reward | active步 | raw非零步 | scaled正/负步 | scaled正/负总和 |
| --- | --- | --- | --- | --- |
| P_S1/left/natural/arm_tangent_progress | 230123 | 136975 | 136975/0 | 8238.103/0 |
| P_S1/left/natural/handle_side_bonus | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/natural/arc_tracking | 230123 | 201523 | 201523/0 | 6231.623/0 |
| P_S1/left/natural/pivot_excess_penalty | 230123 | 103 | 0/103 | 0/-3.568947 |
| P_S1/left/natural/hinge_momentum | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/natural/clean_release_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/natural/premature_release_penalty | 66 | 66 | 0/66 | 0/-15.84 |
| P_S1/left/natural/post_release_persistence | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/natural/handoff_side_progress | 52206 | 20771 | 20771/0 | 4272.344/0 |
| P_S1/left/natural/handoff_hinge_momentum | 56078 | 56078 | 52206/3872 | 948.6132/-27.15211 |
| P_S1/left/natural/handoff_hinge_angle_deficit | 28999 | 28975 | 0/28975 | 0/-284.3791 |
| P_S1/left/natural/post_release_arm_default_target_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/natural/post_release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/natural/post_release_recontact_penalty | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/natural/release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/natural/post_release_lateral_command_alignment | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/natural/post_release_arm_tuck_progress | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/arm_tangent_progress | 121917 | 71810 | 71810/0 | 4209.403/0 |
| P_S1/left/staged/handle_side_bonus | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/arc_tracking | 121917 | 104063 | 104063/0 | 2552.981/0 |
| P_S1/left/staged/pivot_excess_penalty | 121917 | 1383 | 0/1383 | 0/-98.48519 |
| P_S1/left/staged/hinge_momentum | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/clean_release_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/premature_release_penalty | 49 | 49 | 0/49 | 0/-11.76 |
| P_S1/left/staged/post_release_persistence | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/handoff_side_progress | 25505 | 5179 | 5179/0 | 921.9352/0 |
| P_S1/left/staged/handoff_hinge_momentum | 38259 | 38259 | 25505/12754 | 278.3134/-133.5156 |
| P_S1/left/staged/handoff_hinge_angle_deficit | 21930 | 21930 | 0/21930 | 0/-337.1895 |
| P_S1/left/staged/post_release_arm_default_target_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/post_release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/post_release_recontact_penalty | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/post_release_lateral_command_alignment | 0 | 0 | 0/0 | 0/0 |
| P_S1/left/staged/post_release_arm_tuck_progress | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/arm_tangent_progress | 161382 | 93337 | 93337/0 | 1960.576/0 |
| P_S1/right/natural/handle_side_bonus | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/arc_tracking | 161382 | 160489 | 160489/0 | 6423.994/0 |
| P_S1/right/natural/pivot_excess_penalty | 161382 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/hinge_momentum | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/clean_release_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/premature_release_penalty | 17 | 17 | 0/17 | 0/-4.08 |
| P_S1/right/natural/post_release_persistence | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/handoff_side_progress | 17750 | 5327 | 5327/0 | 326.7816/0 |
| P_S1/right/natural/handoff_hinge_momentum | 20051 | 20051 | 17750/2301 | 234.56/-13.85538 |
| P_S1/right/natural/handoff_hinge_angle_deficit | 358 | 358 | 0/358 | 0/-5.09954 |
| P_S1/right/natural/post_release_arm_default_target_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/post_release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/post_release_recontact_penalty | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/post_release_lateral_command_alignment | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/natural/post_release_arm_tuck_progress | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/arm_tangent_progress | 117322 | 67565 | 67565/0 | 1470.837/0 |
| P_S1/right/staged/handle_side_bonus | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/arc_tracking | 117322 | 115996 | 115996/0 | 3797.641/0 |
| P_S1/right/staged/pivot_excess_penalty | 117322 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/hinge_momentum | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/clean_release_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/premature_release_penalty | 23 | 23 | 0/23 | 0/-5.52 |
| P_S1/right/staged/post_release_persistence | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/handoff_side_progress | 15626 | 1361 | 1361/0 | 70.02091/0 |
| P_S1/right/staged/handoff_hinge_momentum | 23124 | 23124 | 15626/7498 | 156.6699/-62.27836 |
| P_S1/right/staged/handoff_hinge_angle_deficit | 39 | 39 | 0/39 | 0/-0.5910277 |
| P_S1/right/staged/post_release_arm_default_target_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/post_release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/post_release_recontact_penalty | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/post_release_lateral_command_alignment | 0 | 0 | 0/0 | 0/0 |
| P_S1/right/staged/post_release_arm_tuck_progress | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/arm_tangent_progress | 237997 | 160138 | 160138/0 | 6732.412/0 |
| P_S2/left/natural/handle_side_bonus | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/arc_tracking | 237997 | 202361 | 202361/0 | 4549.843/0 |
| P_S2/left/natural/pivot_excess_penalty | 237997 | 50660 | 0/50660 | 0/-641.4627 |
| P_S2/left/natural/hinge_momentum | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/clean_release_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/premature_release_penalty | 216 | 216 | 0/216 | 0/-51.84 |
| P_S2/left/natural/post_release_persistence | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/handoff_side_progress | 145342 | 84348 | 84348/0 | 7943.194/0 |
| P_S2/left/natural/handoff_hinge_momentum | 167573 | 167573 | 145342/22231 | 2403.926/-145.8928 |
| P_S2/left/natural/handoff_hinge_angle_deficit | 131961 | 130872 | 0/130872 | 0/-1021.435 |
| P_S2/left/natural/post_release_arm_default_target_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/post_release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/post_release_recontact_penalty | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/post_release_lateral_command_alignment | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/natural/post_release_arm_tuck_progress | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/arm_tangent_progress | 114715 | 69006 | 69006/0 | 2737.835/0 |
| P_S2/left/staged/handle_side_bonus | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/arc_tracking | 114715 | 102772 | 102772/0 | 2199.015/0 |
| P_S2/left/staged/pivot_excess_penalty | 114715 | 52096 | 0/52096 | 0/-951.7717 |
| P_S2/left/staged/hinge_momentum | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/clean_release_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/premature_release_penalty | 158 | 158 | 0/158 | 0/-37.92 |
| P_S2/left/staged/post_release_persistence | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/handoff_side_progress | 42274 | 20443 | 20443/0 | 1873.293/0 |
| P_S2/left/staged/handoff_hinge_momentum | 54139 | 54139 | 42274/11865 | 552.9858/-76.11769 |
| P_S2/left/staged/handoff_hinge_angle_deficit | 47038 | 46886 | 0/46886 | 0/-442.3399 |
| P_S2/left/staged/post_release_arm_default_target_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/post_release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/post_release_recontact_penalty | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/post_release_lateral_command_alignment | 0 | 0 | 0/0 | 0/0 |
| P_S2/left/staged/post_release_arm_tuck_progress | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/arm_tangent_progress | 211646 | 109767 | 109767/0 | 3430.12/0 |
| P_S2/right/natural/handle_side_bonus | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/arc_tracking | 211646 | 210640 | 210640/0 | 8368.347/0 |
| P_S2/right/natural/pivot_excess_penalty | 211646 | 6474 | 0/6474 | 0/-32.47494 |
| P_S2/right/natural/hinge_momentum | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/clean_release_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/premature_release_penalty | 241 | 241 | 0/241 | 0/-57.84 |
| P_S2/right/natural/post_release_persistence | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/handoff_side_progress | 21014 | 7797 | 7797/0 | 588.3338/0 |
| P_S2/right/natural/handoff_hinge_momentum | 25826 | 25826 | 21014/4812 | 304.9166/-38.05375 |
| P_S2/right/natural/handoff_hinge_angle_deficit | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/post_release_arm_default_target_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/post_release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/post_release_recontact_penalty | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/post_release_lateral_command_alignment | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/natural/post_release_arm_tuck_progress | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/arm_tangent_progress | 99658 | 51765 | 51765/0 | 1695.545/0 |
| P_S2/right/staged/handle_side_bonus | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/arc_tracking | 99658 | 97015 | 97015/0 | 3467.241/0 |
| P_S2/right/staged/pivot_excess_penalty | 99658 | 7719 | 0/7719 | 0/-139.4812 |
| P_S2/right/staged/hinge_momentum | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/clean_release_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/premature_release_penalty | 158 | 158 | 0/158 | 0/-37.92 |
| P_S2/right/staged/post_release_persistence | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/handoff_side_progress | 6690 | 1048 | 1048/0 | 79.82196/0 |
| P_S2/right/staged/handoff_hinge_momentum | 20074 | 20074 | 6690/13384 | 46.55559/-129.1716 |
| P_S2/right/staged/handoff_hinge_angle_deficit | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/post_release_arm_default_target_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/post_release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/post_release_recontact_penalty | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/release_open_command_quality | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/post_release_lateral_command_alignment | 0 | 0 | 0/0 | 0/0 |
| P_S2/right/staged/post_release_arm_tuck_progress | 0 | 0 | 0/0 | 0/0 |

全部reward的raw非零、scaled正负步数及收益保存在SUMMARY。active_mask按现有v6 reward公式和stage decorator旁录，mask为真但raw为零是允许结果，不把mask、非零支付和episode能力互换。零值来自精确计数，不来自四位小数日志。

## 初期窗口与瞬态限制

| 来源/窗口末 | natural控制步 | staged控制步 | B有余量步 | C步 | D步 | ready步 |
| --- | --- | --- | --- | --- | --- | --- |
| P_S1 | 9010 | 633668 | 21692 | 0 | 0 | 12462 | 0 |
| P_S1 | 9020 | 487796 | 167564 | 0 | 0 | 17766 | 0 |
| P_S1 | 9030 | 502924 | 152436 | 0 | 0 | 16519 | 0 |
| P_S1 | 9040 | 503574 | 151786 | 0 | 0 | 17569 | 0 |
| P_S1 | 9050 | 488586 | 166774 | 0 | 0 | 17045 | 0 |
| P_S1 | 9060 | 494196 | 161164 | 0 | 0 | 18160 | 0 |
| P_S1 | 9070 | 505486 | 149874 | 0 | 0 | 17344 | 0 |
| P_S1 | 9080 | 493203 | 162157 | 0 | 0 | 19228 | 0 |
| P_S1 | 9090 | 495870 | 159490 | 0 | 0 | 16180 | 0 |
| P_S1 | 9100 | 489720 | 165640 | 0 | 0 | 15447 | 0 |
| P_S2 | 9010 | 635906 | 19454 | 0 | 0 | 15916 | 0 |
| P_S2 | 9020 | 483728 | 171632 | 0 | 0 | 25467 | 0 |
| P_S2 | 9030 | 501002 | 154358 | 0 | 0 | 31929 | 0 |
| P_S2 | 9040 | 489968 | 165392 | 0 | 0 | 28479 | 0 |
| P_S2 | 9050 | 487763 | 167597 | 0 | 0 | 30105 | 0 |
| P_S2 | 9060 | 491187 | 164173 | 0 | 0 | 32387 | 0 |
| P_S2 | 9070 | 471462 | 183898 | 0 | 0 | 36969 | 0 |
| P_S2 | 9080 | 483529 | 171831 | 0 | 0 | 37017 | 0 |
| P_S2 | 9090 | 484969 | 170391 | 0 | 0 | 36409 | 0 |
| P_S2 | 9100 | 479454 | 175906 | 0 | 0 | 32103 | 0 |

100batch是新进程初期窗口：online snapshot库存重新积累，full不恢复physics/bank/LSTM轨迹历史。不能从这个有界窗口推断旧9000训练进程的全程曝光，也不因后段事件稀少自动延长。最终裁决需按本表的来源差异、库存变化及中介读数解释；不自动选择新reward权重/reset比例。

## Provenance和验证

- 运行根：/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_rl/a2_piper_pull_v7/p1_20260908；每来源resolved_config.yaml、config_comparison.json、exposure_metadata.json、runtime_result.json、9050/9100 checkpoints，以及telemetry_source.py精确源码副本与RUN_RECEIPT.json。
- 旁录实现：scriptsFORhuman/pull_v7/p1_env.py；运行命令：run_p1_cell.sh；汇总入口：analyze_p1.py；合同：P1_CONTRACT.md。
- 已核对每来源40行(10窗口×2侧×2出生来源)、每窗口655360 transitions、每来源6553600；实际reset行数/汇总计数一致、snapshot逐条/汇总计数一致。Main已CPU核对四个checkpoint的global_step与optimizer保存状态，child/wrapper均0。
- 所有数字为训练曝光描述，不能替代新的natural评估；未运行P2、Teacher/Student、hardware或云端handoff。
