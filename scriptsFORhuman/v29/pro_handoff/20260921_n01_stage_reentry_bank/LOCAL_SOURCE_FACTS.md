# 当前源码与证据事实

这些是已读事实，不是推荐结论。源码包采用本次N01工作树的当前文件；同名历史文档及旧行号不覆盖它。

## 已实现与未实现

- 当前Stage基类仍按各阶段条件前进并`stage_buf += 1`。v27旧恢复代码留在door env中，但固定C002配置没有其启用字段。
- v1.2已设计L0回Stage2、L1回Stage1再Stage2，以及依当前门状态重入Stage3/4；完整N01恢复路由、Teacher训练和Student传递尚未实施。
- **本次发布前当前工作树已经移除Stage0 arm delta强制覆盖**，涉及`delta_action_base.py`、`a2_v26_4_canonicalization.py`和door env。相对`v29-c002-baseline`的这部分现存源码变化纳入审阅，不是此次打包新做的实现。旧plan/Pro材料中“Stage0仍覆盖target”的描述已不完全符合当前源码；其余条件性命令路径仍应结合配置阅读，不能据此宣布整个stage-blind合同完成。

## Stage重入的直接判据

- 当前C002 Stage3→4要求门铰链角`>0.25 rad`＋合格握持；5个control tick，streak highwater=false。没有要求重新发生一次压柄事件。
- Stage4的stage reward condition复用3→4条件。Stage1 reward condition仍调用包含默认arm姿态的Stage0条件，恢复L1需处理这项相容性。
- 固定C002 resolved config中`push_door_handle=0`、`a2_stage3_handle_depression=0`、handle creation=6、unlatch hold=3、dont push handle=3、push hinge=6。unlatch hold只在门角小于0.1 rad有效。
- N01 plan要求当前目标可回退，预算/进展高水位单调、不给重复阶段信用；这不是当前基类自然具备的行为。

## v27 bank的实际机制

- 旧在线recovery触发时固定回Stage2，清局部stage timer和握持streak；当下不瞬移物理状态，不产生done，所以观察/RNN历史继续。
- bank capture要求`enable_staged_reset=true`，按env保存进程内GPU ring；内容来自staged状态注册，包括world root、DOF q/qd、delta target和部分任务buffer，以及额外highwater等。
- 左右侧pending按数量较少的一侧promotion。restore只取同一env自己的slot，原几何/门参数已在该env中存在；它不是任意跨env的场景迁移接口。
- bank加载发生在terminal reset之后：普通history与模型hidden重置，随后加载部分snapshot字段；旧total_time可能恢复，而新episode counter已归零。
- 当前没有bank导出/导入的持久化接口，也不含Student可直接训练的RGB、Teacher标签和完整序列。v27 readout证明capture/promotion/reset曾执行，不证明恢复收益；R1正式endpoint缺失。

## Teacher / Student

- Teacher actor133D、critic138D，学习12D高层命令，冻结A2_Base给12D腿动作后组成24D环境动作。
- 当前Student方案固定81D＋单路ego RGB（216×384），12D BC；rollout=8不等于每8tick清记忆。Teacher和Student各自按真实done reset hidden。
- 现有distill默认Teacher执行全部动作，支持显式改为Student执行；N01 plan要求S_online由Student实际控制、Teacher只shadow，不能假定默认DAgger已经满足这一点。
- N01 plan两个Teacher从相同随机高层初始化起步，不加载旧Teacher模型/RMS或将旧诊断轨迹混入scratch训练。主动bank若改变采样/数据来源，需作为新建议明确说明。

## 本次提供的运行证据边界

- 固定C002 step6000 readout为0/64自然完整成功，只是该历史固定终点；没有为交付轮询其他活跃训练，也不把它描述成外部任务的最新状态。
- v28成熟S282 step6000在原生LEFT域做了两轮0.35s掌部力诊断。强档100/60/85 N持续双指脱离8/11到窗非零案例；减半50/30/42.5 N为0/11。宽口径约束失效分别11/11、1/11；两轮0 N对照均0/4。统一短窗至t0+0.55s，不是整episode loss latch。
- −X_G方向没有完整脱离证据。独立视频运行的0 N也能出现宽口径loss，不能把弱loss直接归因于外力。
- 4秒代表视频是独立8env运行，0.4倍仿真实时播放；视频1.25–2.125秒对应0.35s力pulse。该例双指接触降为零、相对滑出约12.5cm。
- 这些证明有限掌部力可以破坏握持；没有证明B05上N01恢复图、Teacher恢复学习或Student自主恢复。

## 阅读和未随包提供的内容

checkpoint权重、巨大trace、完整训练目录、本机IsaacLab安装和完整原始视频不随包提供。诊断checkpoint/source路径只作来源说明，不能声称云端已经加载运行。随包有该v28 checkpoint的相邻config供核对原生域。

原始JSON/文档中的绝对本机路径作为出处保留；包内文件映射以BUNDLE_MANIFEST为准。历史回包提及的D061/D064等材料不是本次新的证据，当前固定C002 config/readout优先。
