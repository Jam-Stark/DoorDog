# 机器人开门设计,gripper zone讨论
对 **A2 + PiPER 持续握住门把手开门**，我建议不要把“gripper 舒适区”设计成一个固定目标点，而是设计成：

> **PiPER 底座坐标系中的软舒适区域 + 关节余量 + 当前开门力方向下的扭矩可行性。**

位置区域负责让 A2 跟着门把手“让路”，力/扭矩项负责避免出现“位置看起来还行，但机械臂已经很费劲”的情况。

PiPER 是 6 自由度机械臂，标称工作半径为 626.75 mm，但各关节限位明显不同，因此“离机械臂底座距离适中”并不等价于“构型舒适”。`piper.pdf` `piper.pdf`

---

# 1. 舒适区一定要定义在 PiPER 底座坐标系

设：

- $\mathcal W$：世界坐标系；
- $\mathcal B$：A2 `base_link`；
- $\mathcal A$：PiPER 安装底座坐标系；
- $\mathcal G$：gripper 坐标系。

使用：

$$
{}^{A}p_G
=
{}^{A}T_W\,{}^{W}p_G
$$

也就是 gripper 相对于 PiPER 底座的位置。

不要用世界坐标中的 gripper 位置作为舒适区，因为门打开时，gripper 本来就应该在世界中沿圆弧移动。真正需要保持相对稳定的是：

$$
{}^{A}p_G
$$

它表示当前 arm 是伸得太远、太偏、太高，还是处于容易施力的区域。

这会自然产生你想要的 base guidance：

- 门把手沿世界圆弧移动；
- A2 不动时，${}^{A}p_G$ 会逐渐漂向 arm workspace 边缘；
- comfort penalty 增大；
- policy 通过后退、侧移、转向或调高度，把 gripper 拉回相对舒适区。

全程不需要显式 base trajectory。

---

# 2. 不要奖励 gripper 回到一个点，要使用“平台区 + 软边界”

最不推荐的是：

$$
r_{\mathrm{comfort}}
=
-\|{}^{A}p_G-p_c\|^2
$$

因为这会不断把 gripper 拉向一个精确中心点，即使当前已经足够舒服，也会驱动 A2 做不必要的小动作，甚至和门的闭链约束打架。

更合适的是一个椭球形 deadband。

设舒适区中心：

$$
p_c=[c_x,c_y,c_z]^\top
$$

三个方向的半轴：

$$
a=[a_x,a_y,a_z]^\top
$$

定义归一化距离：

$$
\rho_p
=
\sqrt{
\left(\frac{x-c_x}{a_x}\right)^2+
\left(\frac{y-c_y}{a_y}\right)^2+
\left(\frac{z-c_z}{a_z}\right)^2
}
$$

舒适区 penalty：

$$
P_{\mathrm{zone}}
=
\left[
\max(0,\rho_p-1)
\right]^2
$$

它的含义是：

$$
\rho_p\leq1
\quad\Rightarrow\quad
P_{\mathrm{zone}}=0
$$

只要 gripper 在区域内部，就不要求继续靠近中心。

当它离开区域：

$$
\rho_p>1
$$

才平滑增加 penalty。

建议再设置一个硬边界：

$$
\rho_p>\rho_{\mathrm{hard}}
$$

持续若干步后触发大惩罚或 episode termination，例如：

$$
\rho_{\mathrm{hard}}\approx1.3\sim1.5
$$

这样形成：

- 内部：完全自由；
- warning shell：引导 base 开始让路；
- hard shell：避免 arm 彻底伸直、折叠或失去抓握。

---

# 3. A2 + PiPER 的三个方向不要设置成一样宽

这个 comfort zone 应该是各向异性的。

假设 PiPER 安装后，机械臂前方是 $x_A$，左右是 $y_A$，竖直是 $z_A$。

## 前后方向 $x_A$

需要防止两种状态：

- 伸得过远，接近 arm 最大工作半径；
- 离底座太近，arm 严重折叠、自碰撞或肘部姿态很差。

所以严格来说，前后方向更适合“舒适壳层”，而不是只设一个上限：

$$
P_x
=
\max(0,x_{\min}-x)^2+
\max(0,x-x_{\max})^2
$$

PiPER 标称工作半径为 626.75 mm。第一版仿真可以把高质量构型大致集中在最大伸展的 $50\%\sim80\%$ 范围内，再通过 URDF 扫描修正；这个比例只能作为 warm start，不应直接当作实机安全值。`piper.pdf`

## 左右方向 $y_A$

建议比前后方向更窄。

因为较大的 $|y_A|$ 往往意味着：

- arm 底座关节 J1 扭转较大；
- wrist 为了保持门把手姿态产生额外旋转；
- A2 本体没有正确侧移或转向。

因此把 $a_y$ 设得稍小，会自然引导 A2：

- 转向门把手；
- 侧移；
- 让 handle 保持在 arm 的主要工作平面附近。

如果 PiPER 不是安装在 A2 中线，而是偏左或偏右安装，则 $c_y$ 不应为零，而应根据安装偏置设定。

## 高度方向 $z_A$

如果 policy 能控制 A2 机身高度，那么 $z_A$ 区域可以稍窄，让 A2 主动升降以适配不同门把手高度。A2 文档给出的可调机身高度范围为约 $0.3\sim0.5$ m。`05-a2_remote_control.html`

如果你目前的 dog policy 不开放高度 command，就不要把 $z_A$ 设得太窄，否则 policy 会承受一个无法通过动作消除的 penalty。

---

# 4. 单纯的 task-space 舒适区还不够

同一个 gripper 位置，PiPER 可以有不同 IK 构型。

其中一种可能：

- elbow 弯曲合理；
- J4/J5/J6 余量较大；
- 当前开门方向容易施力。

另一种可能：

- 某个 wrist joint 接近限位；
- arm 接近奇异；
- 同样的开门力需要很大关节扭矩。

所以完整的 arm comfort 最好写成：

$$
P_{\mathrm{comfort}}
=
w_pP_{\mathrm{zone}}
+
w_qP_{\mathrm{jlimit}}
+
w_fP_{\mathrm{force\_feas}}
+
w_wP_{\mathrm{wrist}}
$$

---

# 5. 关节限位舒适项

PiPER 各关节范围并不对称，例如 J2 是 $0^\circ\sim195^\circ$，J3 是 $-175^\circ\sim0^\circ$，J5 只有 $-75^\circ\sim75^\circ$。`piper.pdf`

对每个关节定义归一化位置：

$$
\bar q_i
=
\frac{2q_i-(q_i^{\max}+q_i^{\min})}
{q_i^{\max}-q_i^{\min}}
$$

于是：

$$
\bar q_i=0
$$

表示位于关节范围中间，

$$
|\bar q_i|=1
$$

表示位于硬限位。

使用 deadband penalty：

$$
P_{\mathrm{jlimit}}
=
\frac{1}{6}
\sum_i
\left[
\max(0,|\bar q_i|-\beta_q)
\right]^2
$$

建议第一版：

$$
\beta_q=0.7\sim0.8
$$

也就是只有关节进入最后约 $20\%\sim30\%$ 的限位区域后，才明显惩罚。

对持续握门把手任务，可以给 J4、J5、J6 更高权重，因为门转动过程中最容易出现 wrist winding：

$$
P_{\mathrm{jlimit}}
=
\sum_i w_i
\left[
\max(0,|\bar q_i|-\beta_i)
\right]^2
$$

例如：

$$
w_{4,5,6}>w_{1,2,3}
$$

但 J1 如果承担大量左右旋转，也应监控。

---

# 6. 最重要的一项：沿当前开门方向的 force-feasibility

真正意义上的“舒服”，不是 arm 没伸直，而是：

> 在当前构型下，能够以足够大的余量产生所需开门力。

设当前门把手圆弧的切向单位向量为：

$$
d_t
$$

径向单位向量为：

$$
d_r
$$

期望开门力：

$$
f^\star
=
F_t^\star d_t+
F_r^\star d_r
$$

通常：

$$
F_r^\star\approx0
$$

利用 arm Jacobian：

$$
\tau_{\mathrm{req}}
=
\tau_g(q)+J_v(q)^\top f^\star
$$

其中：

- $\tau_g$：当前姿态的重力补偿扭矩；
- $J_v$：arm 的线速度 Jacobian；
- $f^\star$：期望施加的门把手力。

定义归一化所需扭矩：

$$
\rho_\tau
=
\max_i
\frac{|\tau_{\mathrm{req},i}|}
{\tau_{i,\mathrm{soft}}}
$$

然后：

$$
P_{\mathrm{force\_feas}}
=
\left[
\max(0,\rho_\tau-\beta_\tau)
\right]^2
$$

例如从：

$$
\beta_\tau=0.6\sim0.7
$$

开始预警，而不是等到接近 $100\%$ 扭矩后才惩罚。

这里有一个非常关键的设计：

## 用期望力计算构型代价，不要只用实际力矩

如果直接奖励：

$$
-\|\tau_{\mathrm{actual}}\|
$$

policy 可能学会：

> 少用一点力，门开慢一点甚至不开，这样 arm torque 就小了。

因此用于评价“这个姿态是否适合开门”的主要量应是：

$$
\tau_{\mathrm{req}}
=
\tau_g+J^\top f^\star
$$

也就是在该构型下完成目标力所需的预测扭矩。

实际测量扭矩：

$$
\tau_{\mathrm{actual}}
$$

主要作为 safety penalty：

- 瞬时超过 soft limit：惩罚；
- 持续接近 hard limit：终止；
- 不把它作为唯一舒适指标。

这样 policy 无法通过“不出力”来作弊。

---

# 7. 不要给 gripper 一个世界固定姿态 comfort reward

持续握住门把手时，gripper 的姿态受到 handle 和门板运动约束。

因此不建议使用：

$$
\|R_G^W-R_{\mathrm{neutral}}^W\|
$$

否则 policy 会试图让 gripper 在世界中保持一个固定朝向，和门的旋转约束冲突。

应当分成两项：

## 抓握保持

保持 gripper 与 handle 的相对变换：

$$
T_{GH}\approx T_{GH}^{\mathrm{grasp}}
$$

例如：

$$
P_{\mathrm{grasp\_pose}}
=
\frac{\|p_{GH}-p_{GH}^{\star}\|^2}{\sigma_p^2}
+
\frac{\|\log(R_{GH}^{\star\top}R_{GH})\|^2}{\sigma_R^2}
$$

并加：

- 两侧接触保持；
- slip penalty；
- 抓握丢失 termination；
- gripper opening 不应异常增大。

## wrist comfort

不要固定 gripper 世界姿态，而是惩罚 J4/J5/J6 接近限位或持续扭转。

这会让 base yaw 和 base side-step 来释放 wrist winding。

PiPER 选配两指夹爪的开合范围为 0-70 mm，额定夹合力 40 N、最大夹合力 50 N。需要注意，这些数值是夹爪的夹合力，不等于机械臂能够持续施加的门把手切向拉力。`piper.pdf`

---

# 8. comfort reward 必须是开门任务的 secondary objective

你最不希望发生的是：

> policy 为了保持 arm 舒服，选择不打开门。

所以开门主任务必须排在 comfort 前面。

推荐形式：

$$
r_t
=
r_{\mathrm{task}}
-
\alpha_t
P_{\mathrm{comfort}}
-
P_{\mathrm{base}}
-
P_{\mathrm{safety}}
$$

其中：

$$
r_{\mathrm{task}}
=
w_\theta r_{\mathrm{door\ progress}}
+
w_{\dot\theta}r_{\mathrm{door\ speed}}
+
w_h r_{\mathrm{hold}}
$$

例如：

$$
r_{\mathrm{door\ progress}}
=
\theta_{t+1}-\theta_t
$$

$$
r_{\mathrm{door\ speed}}
=
\exp\left[
-\frac{(\dot\theta-\dot\theta^\star)^2}{\sigma_{\dot\theta}^2}
\right]
$$

$$
r_{\mathrm{hold}}
=
\exp(-P_{\mathrm{grasp\_pose}})
$$

comfort gate 可以写成：

$$
\alpha_t
=
\mathbf 1[\text{stage=OPEN\_HOLD}]
\cdot
\mathbf 1[\text{grasp stable}]
\cdot
\sigma
\left(
\frac{\epsilon_F-\|F_{\mathrm{est}}-F^\star\|}
{k_F}
\right)
$$

含义是：

- 没抓稳时，先抓稳；
- 力完全没做出来时，先完成开门主任务；
- 已经能够稳定开门后，再比较哪种全身构型更舒服。

这相当于把 comfort 作为 tie-breaker：

> 在都能开门的行为中，选择 arm 更舒适的那个。

---

# 9. 还要加 minimal base movement，否则 A2 会过度追求舒适中心

如果只有 comfort penalty，policy 可能一直调整 A2，努力把 gripper 放在 comfort zone 的“最优位置”。

所以需要：

$$
P_{\mathrm{base}}
=
w_v\|v_b\|^2
+
w_\omega\|\omega_b\|^2
+
w_{\Delta u}\|u_{b,t}-u_{b,t-1}\|^2
$$

如果还控制高度：

$$
+
w_h(h_b-h_{\mathrm{anchor}})^2
$$

这样形成正确的权衡：

$$
\text{arm 越不舒服}
\Rightarrow
\text{越值得移动 base}
$$

但：

$$
\text{arm 已经足够舒服}
\Rightarrow
\text{base 保持不动}
$$

这就是“最小必要让路”。

---

# 10. A2 + PiPER 的 comfort zone 最好通过离线扫描得到

不要直接手拍一个中心和椭球尺寸。建议用 URDF/仿真离线生成。

## 第一步：采样 arm 构型

在 PiPER 关节范围内随机采样：

$$
q\sim[q_{\min}+\delta_q,\ q_{\max}-\delta_q]
$$

先留出约 $10\%\sim15\%$ 的 joint range margin。

拒绝：

- arm 自碰撞；
- arm 与 A2 body 碰撞；
- gripper 朝向无法抓 handle；
- 接近明显奇异点的构型。

## 第二步：为每个构型计算 score

对每个 $q$ 计算：

$$
{}^{A}p_G(q)
$$

以及：

$$
m_q(q)
$$

$$
m_{\mathrm{force}}(q,d_t)
$$

$$
\sigma_{\min}(J_v(q))
$$

$$
\|\tau_g(q)\|
$$

一个离线 score 可以是：

$$
S(q,d_t)
=
w_qm_q
+
w_fm_{\mathrm{force}}
+
w_\sigma m_\sigma
-
w_g\|\tau_g\|
-
w_c C_{\mathrm{collision}}
$$

其中 $d_t$ 要覆盖不同的水平开门方向。

## 第三步：保留高质量构型

保留 score 最高的约 $20\%\sim30\%$ 样本。

将这些样本对应的：

$$
{}^{A}p_G
$$

拟合成：

- 一个椭球；
- 多个高斯；
- occupancy grid；
- task-space signed distance field。

第一版用一个椭球就够。

如果左右开门差异明显，可以分别拟合：

$$
\mathcal C_{\mathrm{left}}
$$

和：

$$
\mathcal C_{\mathrm{right}}
$$

或者用门打开方向作为条件：

$$
\mathcal C(d_t)
$$

这会比简单固定球形区域可靠得多。

---

# 11. 推荐的第一版 reward

所有项先归一化到接近 $[0,1]$，可以从下面的比例开始：

$$
\begin{aligned}
r_t={}&
4.0\,r_{\mathrm{door\ progress}}
+
3.0\,r_{\mathrm{hold}}
+
1.0\,r_{\mathrm{door\ speed}}
\\
&-
\alpha_t\Big(
0.4\,P_{\mathrm{zone}}
+
0.8\,P_{\mathrm{force\_feas}}
+
0.3\,P_{\mathrm{jlimit}}
+
0.2\,P_{\mathrm{wrist}}
\Big)
\\
&-
0.05\|v_b\|^2
-
0.03\|\omega_b\|^2
-
0.02\|u_{b,t}-u_{b,t-1}\|^2
-
P_{\mathrm{safety}}
\end{aligned}
$$

这里这些只是初始比例，真正关键的是优先级：

$$
\text{抓稳并打开门}
>
\text{force feasibility}
>
\text{task-space comfort}
>
\text{少动 base}
$$

安全项建议部分做 hard constraints：

- gripper 丢失 handle；
- A2 跌倒；
- body 与门板严重碰撞；
- arm 持续高扭矩；
- arm 硬 joint-limit；
- 持续滑移。

---

# 12. 这个 reward 最终会学出什么行为

开始时：

$$
{}^{A}p_G\in\mathcal C
$$

且 torque margin 足够，A2 基本不动。

门逐渐打开后：

- gripper 相对 arm base 向侧面/前方漂移；
- task-space comfort penalty 开始出现；
- wrist 和 J1 余量下降；
- 当前切向开门力所需扭矩上升。

policy 会学会：

- 先轻微转向；
- 再侧移或后退；
- 必要时调机身高度；
- 同时保持 gripper-handle 相对姿态；
- 让 arm 回到有弯曲、有扭矩余量的区域。

如果门更重，即使 gripper 还没到几何边缘：

$$
P_{\mathrm{force\_feas}}
$$

也会提前增大，于是 A2 会更早让路。

所以最终形成的是：

> **几何 comfort 负责 nominal base guidance，方向相关的 force/torque margin 负责提前修正和 residual adaptation。**

这正适合你当前没有显式 trajectory planner、由一个 policy 完成持续握把开门的方案。