# How DoorMan Uses GRPO: From a DAgger Vision Student to a Deployable RGB Whole-Body Policy

> Paper: **Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer (DoorMan)**<br>
> arXiv: 2512.01061<br>
> Focus: DoorMan **Phase 3 — GRPO bootstrapping / fine-tuning**<br>
> Goal of this document: expand the paper's relatively concise GRPO description into an implementation-oriented technical note while strictly separating **facts explicitly reported by the paper**, **the current state of the official open-source repository**, and **engineering choices that must be decided independently when reproducing the method**.

---

## 0. Executive Summary

DoorMan does **not** learn door opening directly from scratch with GRPO. The complete training pipeline has three stages:

```text
Phase 1: Privileged Teacher
    PPO + privileged simulator state
              ↓
Phase 2: Vision Student
    DAgger distillation
    RGB + proprioception + recurrence
              ↓
Phase 3: Bootstrap Student
    GRPO on student's own rollouts
    mostly binary task-success reward
              ↓
        final RGB policy
```

GRPO has a very specific role in DoorMan:

> **It repairs the observability gap between a privileged teacher and a partially observable RGB student that pure imitation cannot eliminate.**

The teacher has access to exact simulator information such as the door pose, handle transform, contact wrench, root velocity, and other privileged state. At deployment time, the student mainly has RGB, proprioception, and temporal memory. Consequently, even perfect action imitation does not necessarily produce the optimal closed-loop behavior under the student's own observation distribution.

DoorMan therefore lets the DAgger student roll out its **own** policy in simulation and then applies GRPO so that complete trajectories that lead to higher task success become more likely. The paper reports that the student consequently learns **active-perception / compensatory behaviors** that the teacher does not need and therefore does not explicitly demonstrate, for example:

- moving the body so that the door handle or manipulated region remains visible;
- adjusting end-effector posture to preserve visibility;
- recovering when camera pose drifts outside the usual distribution;
- jointly managing perception, balance, and articulated constraints during traversal.

The reported trend is that the teacher typically reaches roughly **80–90%** success, while the DAgger student initially remains around **50–70%**. After GRPO, the three door subtasks reach approximately **80.8–85.8%**, largely closing the teacher–student gap.

The project page summarizes this phase as approximately a **20–30% success-rate improvement**.

---

# 1. Where GRPO Fits in DoorMan

## 1.1 Phase 1: Train a Privileged Teacher First

DoorMan first trains a teacher with standard PPO:

\[
\pi_T(a_t\mid s_t)
\]

The teacher can observe privileged information that is not directly available at real-world deployment. Examples listed in the paper include:

- robot-root-to-door transform;
- ground-truth transforms from the left/right hand to the door handle;
- net contact wrench on 18 hand bodies;
- root linear velocity;
- simulator-accessible door articulation state and related task state.

The teacher itself is trained with a six-stage door-opening curriculum / stage-conditioned reward system:

1. Walk to door
2. Pre-grasp
3. Grasp
4. Open
5. Swing
6. Pass through door

To make later stages reachable during PPO exploration, DoorMan also uses **staged-reset exploration**: when the environment reaches a later stage for the first time, a simulator snapshot can be cached, and resets can probabilistically resume from these intermediate-stage states.

This part of DoorMan solves the question:

> **How can the teacher learn a long-horizon, contact-rich manipulation skill in the first place?**

It is not GRPO itself.

---

## 1.2 Phase 2: Distill the Teacher into an RGB Student with DAgger

The teacher is then distilled into a vision-based student:

\[
\pi_S(a_t\mid o_t)
\]

The student does not receive privileged door state. Its observations primarily include:

- RGB images;
- joint positions \(q\);
- joint velocities \(\dot q\);
- root angular velocity;
- temporal context / recurrent state.

The student architecture described in the paper is:

```text
RGB image
   │
   ▼
ResNet vision encoder
   │
   ├──────────────┐
   │              │
vision latent   proprioception
   │              │
   └──── concat ──┘
          │
          ▼
2-layer LSTM
512 hidden units / layer
          │
          ▼
MLP: 512 → 256 → 128
          │
          ▼
target joint positions
```

The vision encoder is fine-tuned jointly with the student policy during student training.

DoorMan uses DAgger rather than only offline behavior cloning so that the teacher can provide supervision on the **states / observations actually visited by the student**, thereby reducing covariate shift.

However, DAgger still has a fundamental ceiling:

> The teacher's optimal action is conditioned on privileged information unavailable to the student. Therefore, “imitating the teacher” is not equivalent to being optimal in the student's POMDP.

This is exactly the motivation for Phase 3.

---

# 2. Why DoorMan Needs GRPO After DAgger

The paper explicitly frames the problem as **partial observability**.

For the same underlying physical state \(s_t\), the teacher may know:

\[
s_t \supset \{
\text{door pose},
\text{handle pose},
\text{articulation state},
\text{contact},
\text{velocity},\ldots
\}
\]

whereas the student only receives something like:

\[
o_t = \{I_t^{RGB}, q_t, \dot q_t, \omega_t, h_{t-1}, \ldots\}.
\]

Therefore:

\[
H(S_t\mid O_{\le t}) > 0.
\]

Even with an LSTM, the student may not be able to uniquely infer all privileged task state from observation history. Typical examples include:

- the handle being occluded by the robot's own hand;
- the camera not revealing the current latch state;
- RGB providing only an imprecise estimate of door distance;
- hinge forces or spring behavior needing to be inferred through interaction;
- camera pose shifting because of humanoid gait and contact disturbances.

If training continues with imitation only, the student is still encouraged to satisfy:

\[
\pi_S(a\mid o) \approx \pi_T(a\mid s).
\]

But the actual deployment objective is:

\[
\max_{\pi_S}\;J(\pi_S),
\]

where \(J\) is the task return obtained by the **student under its own visual observations and its own closed-loop rollouts**.

GRPO performs this transition from an imitation objective to a task objective.

---

# 3. Mathematical Form of DoorMan GRPO

Section 2.3 of the paper gives a concise formulation.

Sample a group of \(G\) rollouts from the current student policy:

\[
\{\tau_i\}_{i=1}^{G} \sim \pi_S.
\]

The \(i\)-th rollout is:

\[
\tau_i=(o_{i,0},a_{i,0},o_{i,1},a_{i,1},\ldots,o_{i,T_i}),
\]

with a scalar trajectory return:

\[
R_i.
\]

## 3.1 Group-Relative Advantage

DoorMan does not train a value function. Instead, it normalizes trajectory returns within the rollout group:

\[
\boxed{
\hat A_i
=
\frac{R_i-\operatorname{mean}(R)}
{\operatorname{std}(R)}
}
\]

where:

\[
\operatorname{mean}(R)
=
\frac{1}{G}\sum_{j=1}^{G}R_j.
\]

Thus \(\hat A_i\) does not mean “how much better is this action than the critic's value estimate?” It means:

> **How much better or worse is the entire \(i\)-th robot rollout than the average rollout in the current group?**

This is the most important conceptual difference between DoorMan GRPO and standard PPO.

---

## 3.2 PPO-Style Importance Ratio

For every timestep in a rollout:

\[
r_{i,t}(\theta)
=
\frac{\pi_\theta(a_{i,t}\mid o_{i,t})}
{\pi_{\text{old}}(a_{i,t}\mid o_{i,t})}.
\]

Using log probabilities:

\[
r_{i,t}
=
\exp\left(
\log \pi_\theta(a_{i,t}\mid o_{i,t})
-
\log \pi_{\text{old}}(a_{i,t}\mid o_{i,t})
\right).
\]

---

## 3.3 DoorMan's Clipped GRPO Objective

The paper gives the following objective:

\[
\boxed{
\mathcal L_{\text{GRPO}}(\theta)
=
\mathbb E_{i,t}
\left[
\min\left(
 r_{i,t}(\theta)\hat A_i,
 \operatorname{clip}
 \big(r_{i,t}(\theta),1-\epsilon,1+\epsilon\big)\hat A_i
\right)
\right]
}
\]

A PyTorch implementation would normally minimize its negative:

\[
L_{policy}=-\mathcal L_{GRPO}.
\]

### A Crucial Detail

The paper writes:

\[
\hat A_i
\]

rather than:

\[
\hat A_{i,t}.
\]

Therefore, the DoorMan formulation uses a **trajectory-level advantage**.

```text
trajectory i:

(o0,a0) ─ (o1,a1) ─ (o2,a2) ─ ... ─ (oT,aT)
    │         │         │                 │
    └─────────┴─────────┴─────────────────┘
                    │
              same A_hat_i
```

If a trajectory performs better than the group average, all sampled actions in that trajectory receive a positive policy-gradient direction. If it performs worse, the whole trajectory receives a negative direction.

This differs fundamentally from PPO + GAE, where advantages are typically timestep-specific.

---

# 4. What Reward Does DoorMan Actually Use in GRPO?

This is one of the easiest parts to misread when reproducing the method.

## 4.1 GRPO Does Not Primarily Reuse the Teacher's Complex Stage Reward

Appendix A describes many dense teacher-PPO reward terms, including:

- approach;
- pre-grasp pose;
- grasp force;
- handle rotation;
- hinge rotation;
- root target;
- stage progress;
- task completion;
- various contact, posture, and action penalties.

However, in the GRPO description in Section 2.3, the paper specifically states that fine-tuning relies mainly on a **binary task-success signal**, together with a small set of simple shaping / regularization terms.

The regularizers explicitly named are:

- joint-velocity penalty;
- joint-acceleration penalty;
- action-rate penalty.

A trajectory return consistent with the paper can therefore be conceptualized as:

\[
R_i
=
R_i^{success}
-
\lambda_v C_i^{joint\ velocity}
-
\lambda_a C_i^{joint\ acceleration}
-
\lambda_{\Delta u} C_i^{action\ rate},
\]

where:

\[
R_i^{success}\in\{0,1\}
\]

or an equivalent scaled version.

**The paper does not report the exact GRPO weights of these terms.**

Therefore, the dense teacher reward weights in Appendix A should not be treated as GRPO reward weights.

---

## 4.2 Why “Mostly Binary” Is Actually Appropriate Here

GRPO is not initialized from a random policy.

It begins from a student already distilled through Teacher → DAgger:

\[
P(\text{success}\mid \pi_{S,0}) > 0.
\]

The paper even notes that this can serve as a drop-in refinement method for a loco-manipulation base policy that already has a **non-zero success rate**.

GRPO therefore does not need to discover from sparse reward that “the hand should first approach the handle.” The teacher and DAgger have already supplied the basic skill.

Instead, it searches locally around the existing behavior for things such as:

- body poses relative to the camera that are more reliable;
- grasp trajectories that cause less visual occlusion;
- whole-body compensation strategies that improve final success;
- visual closed-loop recovery behaviors that turn failures into successes.

This changes sparse reward from a difficult exploration signal into a relatively clean **policy-selection signal**.

---

# 5. What GRPO Computes Under Binary Success

Ignoring the small regularizers for a moment, suppose:

\[
R_i\in\{0,1\}.
\]

If \(k\) out of \(G\) rollouts in a group succeed, then:

\[
p=\frac{k}{G}.
\]

The group mean is:

\[
\mu=p.
\]

Using the population standard deviation:

\[
\sigma=\sqrt{p(1-p)}.
\]

The normalized advantage of a successful trajectory becomes:

\[
\hat A_{success}
=
\frac{1-p}{\sqrt{p(1-p)}}
=
\boxed{\sqrt{\frac{1-p}{p}}}.
\]

The advantage of a failed trajectory becomes:

\[
\hat A_{fail}
=
\frac{-p}{\sqrt{p(1-p)}}
=
\boxed{-\sqrt{\frac{p}{1-p}}}.
\]

This has an interesting consequence.

### When Success Is Rare

For example:

\[
G=8,\quad k=1,\quad p=0.125,
\]

then:

\[
\hat A_{success}=\sqrt 7\approx 2.646,
\]

while failed rollouts have:

\[
\hat A_{fail}\approx -0.378.
\]

So:

> A rare successful rollout receives a strong positive gradient, while many ordinary failures receive relatively weak negative gradients.

### When Success Is Already High

If:

\[
p=0.875,
\]

then:

\[
\hat A_{success}\approx 0.378,
\qquad
\hat A_{fail}\approx -2.646.
\]

Now the few remaining failures become very strong negative examples.

Group normalization therefore induces a natural curriculum:

```text
Low-success regime:
    strongly amplify rare success

High-success regime:
    strongly suppress rare failure
```

This is one reason GRPO is attractive for sparse-success robotics refinement.

---

# 6. A Boundary Case That Must Be Handled: All-Success or All-Failure Groups

If all rollout returns in a group are identical:

\[
R_1=R_2=\cdots=R_G,
\]

then:

\[
\operatorname{std}(R)=0.
\]

The paper's formula does not specify numerical stabilization.

At minimum, an implementation needs something such as:

```python
adv = (returns - returns.mean()) / (returns.std() + eps)
```

or:

```python
if returns.std() < threshold:
    skip_policy_update_for_this_group()
```

If continuous joint/action regularizers are included, returns may still differ slightly even when every rollout has the same binary success bit, so the standard deviation may not be exactly zero. Nevertheless, epsilon protection remains necessary.

**This is an engineering requirement, not a DoorMan-specific implementation detail reported by the paper.**

---

# 7. How Is the DoorMan “Group” Constructed?

The paper only explicitly states that a batch of \(G\) rollouts is sampled from the current policy and that each receives a return \(R_i\).

It does **not** specify:

- the exact value of \(G\);
- whether rollouts in a group share the same door asset;
- whether they share the same initial pose;
- whether they share the same domain-randomization seed;
- whether each task type forms a separate group or tasks are mixed;
- whether group statistics are synchronized globally across GPUs.

Therefore, one should not mechanically import the LLM-GRPO convention of “sample \(G\) completions for the exact same prompt” and claim:

> “DoorMan must sample \(G\) trajectories from the exact same initial environment state.”

The paper does not say that.

## 7.1 Most Literal DoorMan Interpretation

The most conservative reproduction is:

```text
current policy
     │
     ├── rollout 1 → R1
     ├── rollout 2 → R2
     ├── rollout 3 → R3
     │       ...
     └── rollout G → RG

normalize R1...RG together
```

The trajectories can simply come from the ordinary randomized training distribution.

## 7.2 A Potentially Lower-Variance Extension

If one wants to control task difficulty more tightly, trajectories within a group could share similar conditions:

```text
same door family
same/similar initial robot pose
same physical parameters
different stochastic actions / visual noise
```

Then the group compares policies under approximately matched difficulty.

This is closer to matched-prompt logic in LLM GRPO, but it is a **reasonable extension**, not something that should be presented as a fact from DoorMan.

---

# 8. What One DoorMan-Style GRPO Iteration Should Do

The following workflow is consistent with the equations in the paper.

## Step 0: Load the DAgger Student

```python
policy = load_dagger_student_checkpoint()
```

The policy is not randomly initialized and is not initialized from the teacher PPO actor.

The student must retain:

- vision encoder;
- proprioception processing;
- recurrent memory;
- actor head;
- action-distribution parameters.

---

## Step 1: Freeze an Old-Policy Snapshot

At the beginning of a rollout/update cycle:

```python
old_policy.load_state_dict(policy.state_dict())
old_policy.eval()
```

or cache old log probabilities when sampling:

```python
old_logp_t = dist.log_prob(action_t)
```

The current policy may then undergo multiple optimization epochs, but the denominator in the importance ratio must correspond to the behavior policy \(\pi_{old}\) that actually generated the rollout.

---

## Step 2: Sample Complete Trajectories in Parallel

Run the student in parallel IsaacLab environments:

```text
env 0 ───────────────── terminal

env 1 ─────────── terminal

env 2 ───────────────────── terminal
...
```

Each trajectory should store at least:

```python
Trajectory:
    observations
    recurrent_hidden_states
    actions
    old_log_probs
    rewards / regularizer costs
    dones
    success
    valid_mask
```

Because the DoorMan student is recurrent, the rollout buffer cannot be treated merely as a bag of independent feed-forward PPO transitions.

---

## Step 3: Produce One Scalar Return per Trajectory

Conceptually:

```python
R_i = success_reward
R_i -= joint_velocity_penalty
R_i -= joint_acceleration_penalty
R_i -= action_rate_penalty
```

The quantity normalized across the group is a **trajectory scalar**.

If regularizers are defined per timestep, aggregate them over the episode first:

\[
C_i=\sum_{t=0}^{T_i}c_{i,t},
\]

and then form:

\[
R_i=R_i^{success}-\lambda C_i.
\]

The paper does not report whether these costs are discounted or normalized by episode length, so these details must be designed explicitly in a reproduction.

---

## Step 4: Normalize Returns Within the Group

```python
returns = torch.tensor([R_1, ..., R_G])
mu = returns.mean()
sigma = returns.std(unbiased=False)
adv = (returns - mu) / (sigma + eps)
```

This produces:

```text
A_1, A_2, ..., A_G
```

---

## Step 5: Broadcast the Trajectory Advantage to Every Timestep

```python
for trajectory_i in group:
    trajectory_i.advantages[:] = A_i
```

Equivalently:

\[
\forall t\in\tau_i:\quad
\hat A_{i,t}\leftarrow \hat A_i.
\]

This is the core rollout-processing difference between DoorMan-style GRPO and ordinary PPO.

---

## Step 6: Recompute Current-Policy Log Probabilities

For the actions stored in the rollout buffer:

```python
new_dist = policy(obs, hidden_state)
new_logp = new_dist.log_prob(action)
ratio = torch.exp(new_logp - old_logp)
```

For continuous control, the action distribution is typically a factorized Gaussian. If log probabilities are returned separately per DoF, sum over action dimensions before forming the joint-action importance ratio:

\[
\log\pi(a_t\mid o_t)
=
\sum_d\log\pi(a_{t,d}\mid o_t).
\]

---

## Step 7: Compute the Clipped Surrogate

```python
surr1 = ratio * advantage
surr2 = torch.clamp(ratio, 1-eps_clip, 1+eps_clip) * advantage
policy_loss = -torch.mean(torch.minimum(surr1, surr2))
```

Then:

```python
optimizer.zero_grad()
policy_loss.backward()
torch.nn.utils.clip_grad_norm_(policy.parameters(), max_grad_norm)
optimizer.step()
```

---

## Step 8: Repeat Rollout → Update

The student continuously generates new data from its **current** distribution:

```text
DAgger student
   │
   ▼
rollout group #1
   │
   ▼
GRPO update
   │
   ▼
rollout group #2
   │
   ▼
GRPO update
   │
   ▼
...
```

This is what the paper means by **bootstrapping the student on its own rollouts**.

---

# 9. Full Pseudocode

The following is **DoorMan-faithful pseudocode derived from the paper's equations**. It is not a line-by-line reconstruction of unreleased NVIDIA GRPO code.

```python
# ----------------------------------------------------------
# DoorMan-style GRPO for recurrent visuomotor policy
# ----------------------------------------------------------

policy = load_dagger_student()
optimizer = Adam(policy.parameters(), lr=LR)

for iteration in range(num_iterations):

    # pi_old is the behavior policy that generates this batch
    old_policy = deepcopy(policy).eval()

    trajectories = []

    # ------------------------------------------------------
    # 1. collect G complete rollouts
    # ------------------------------------------------------
    while len(trajectories) < G:
        obs = env.reset()
        hidden = policy.initial_hidden_state()

        traj = []
        done = False

        while not done:
            with torch.no_grad():
                dist, next_hidden = old_policy(obs, hidden)
                action = dist.sample()
                old_logp = dist.log_prob(action).sum(-1)

            next_obs, reward_terms, done, info = env.step(action)

            traj.append({
                "obs": obs,
                "hidden": hidden,
                "action": action,
                "old_logp": old_logp,
                "regularizers": reward_terms,
            })

            obs = next_obs
            hidden = next_hidden

        success = float(info["success"])

        # Paper: mainly binary success + simple behavior regularization
        R = success
        R -= lambda_qd   * sum(x["regularizers"]["joint_velocity"]
                               for x in traj)
        R -= lambda_qdd  * sum(x["regularizers"]["joint_acceleration"]
                               for x in traj)
        R -= lambda_du   * sum(x["regularizers"]["action_rate"]
                               for x in traj)

        trajectories.append({
            "steps": traj,
            "return": R,
            "success": success,
        })

    # ------------------------------------------------------
    # 2. group-relative trajectory advantages
    # ------------------------------------------------------
    returns = torch.tensor(
        [tau["return"] for tau in trajectories],
        device=device,
    )

    mean_R = returns.mean()
    std_R = returns.std(unbiased=False)
    group_advantages = (returns - mean_R) / (std_R + ADV_EPS)

    # ------------------------------------------------------
    # 3. optimize clipped actor objective
    # ------------------------------------------------------
    for epoch in range(num_policy_epochs):
        for sequence_batch in recurrent_minibatches(trajectories):

            losses = []

            for i, tau in sequence_batch:
                A_i = group_advantages[i]

                # IMPORTANT:
                # replay as a recurrent sequence, preserving LSTM state
                dist_seq = policy.forward_sequence(
                    obs_seq=tau.obs,
                    initial_hidden=tau.initial_hidden,
                    masks=tau.valid_masks,
                )

                new_logp = dist_seq.log_prob(tau.actions).sum(-1)
                ratio = torch.exp(new_logp - tau.old_logp)

                surr1 = ratio * A_i
                surr2 = torch.clamp(
                    ratio,
                    1.0 - CLIP_EPS,
                    1.0 + CLIP_EPS,
                ) * A_i

                actor_obj = torch.minimum(surr1, surr2)
                losses.append(-masked_mean(actor_obj, tau.valid_masks))

            loss = torch.stack(losses).mean()

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                policy.parameters(), MAX_GRAD_NORM
            )
            optimizer.step()
```

---

# 10. What Actually Disappears Compared with PPO?

Standard PPO usually needs:

```text
actor
critic
rollout rewards
value prediction
bootstrap V(s_T)
GAE
returns-to-go
value loss
policy loss
entropy loss
```

DoorMan-style GRPO reduces this to:

```text
actor only
complete trajectory scores
within-group normalization
clipped policy loss
```

| Component | PPO | DoorMan GRPO |
|---|---|---|
| Actor | ✓ | ✓ |
| Critic / value network | ✓ | **not required** |
| GAE | ✓ | **not required** |
| Timestep value target | ✓ | **not required** |
| Advantage | \(\hat A_t^{GAE}\) | \(\hat A_i=(R_i-\mu_R)/\sigma_R\) |
| Advantage granularity | timestep | **trajectory** |
| PPO importance ratio | ✓ | ✓ |
| Clipping | ✓ | ✓ |
| Sparse success reward | difficult from scratch | well suited to warm-start refinement |
| Recurrent policy | optional | required by DoorMan student |

If converting an existing PPO trainer:

### Remove

- critic forward pass;
- value buffer;
- GAE computation;
- value target;
- value loss;
- critic optimizer.

### Keep

- stochastic actor;
- old log probability;
- PPO importance ratio;
- clipped surrogate;
- policy optimizer;
- gradient clipping;
- rollout / distributed collection infrastructure.

### Add

- episode / trajectory boundary bookkeeping;
- scalar trajectory return;
- group construction;
- group mean/std computation;
- trajectory-to-timestep advantage broadcasting.

---

# 11. How DoorMan GRPO Differs from the Original DeepSeekMath GRPO

DoorMan borrows the core group-relative idea, but a robotics implementation should not be treated as mechanically identical to an LLM trainer.

## DeepSeekMath Setting

```text
same prompt q
  ├─ completion 1 → reward
  ├─ completion 2 → reward
  ├─ ...
  └─ completion G → reward
```

## DoorMan Setting

```text
robot policy
  ├─ continuous-control trajectory 1 → task return
  ├─ continuous-control trajectory 2 → task return
  ├─ ...
  └─ continuous-control trajectory G → task return
```

Main differences:

1. **token → robot timestep**;
2. **completion → physical trajectory**;
3. reward comes from simulator task outcomes rather than a reward model / verifier;
4. the policy is an RGB + proprioception + LSTM continuous controller;
5. the DoorMan equation does not include the reference-policy KL penalty commonly associated with some LLM GRPO implementations;
6. DoorMan normalizes a trajectory-level return.

Therefore, one should not directly use an autoregressive-language-model `GRPOTrainer` as if it were a drop-in trainer for DoorMan.

The optimization idea is related, but the data structure, probability distribution, sequence handling, and rollout engine are fundamentally different.

---
# 12. Why DoorMan GRPO Does Not Need a Critic

In PPO, the critic primarily provides a baseline for the policy gradient:

\[
A_t = Q(s_t,a_t)-V(s_t).
\]

DoorMan instead uses the other rollouts in the current group to define a baseline:

\[
b=\operatorname{mean}\{R_1,\ldots,R_G\}.
\]

Then:

\[
R_i-b
\]

directly tells the policy:

> “Was this complete attempt better or worse than the average attempt produced by the current policy under the same training distribution?”

Dividing by the group standard deviation:

\[
\hat A_i=\frac{R_i-b}{\sigma_R}
\]

also normalizes the scale of the learning signal across iterations with different return distributions.

This is especially suitable for DoorMan Phase 3 because the goal is no longer to learn an entirely new long-horizon skill. It is to refine a student that already has substantial task competence.

---

# 13. Why Coarse Trajectory-Level Credit Assignment Can Still Work

At first glance, rewarding every action in a successful trajectory with the same positive advantage may seem extremely coarse.

It is.

DoorMan GRPO does not solve the general temporal-credit-assignment problem of long-horizon RL. Its practicality comes largely from three properties.

## 13.1 The Policy Is Already Warm-Started

The student already knows how to:

- walk to the door;
- reach;
- grasp;
- rotate the handle;
- push or pull the door;
- traverse through the doorway.

GRPO is therefore not trying to infer which timestep in a zero-skill trajectory first contains a useful behavior.

## 13.2 The Search Region Is Restricted by PPO Clipping

The policy is encouraged to remain near the behavior policy because the update is clipped around:

\[
r_t\in[1-\epsilon,1+\epsilon].
\]

Thus, a single successful trajectory should not cause an arbitrarily large move away from the DAgger initialization.

## 13.3 The Missing Behavior Is Often a Closed-Loop Strategy

The behavior that needs to be learned is often not one isolated action but an entire feedback pattern, for example:

```text
handle becomes hard to see
    ↓
move torso / root
    ↓
recover visual contact
    ↓
adjust hand pose
    ↓
maintain grasp
    ↓
continue swing / traversal
```

Such behavior is inherently trajectory-level. A terminal task-success signal applied to the whole strategy chain is therefore not entirely unreasonable.

---

# 14. The Recurrent Student Is One of the Largest Reproduction Pitfalls

The DoorMan student contains a two-layer LSTM. Consequently, sampled data cannot simply be flattened, fully shuffled, and trained as independent timesteps in the way one might train a feed-forward MLP PPO policy.

Incorrect:

```python
# bad for LSTM policy
flat_transitions = random_shuffle(all_timesteps)
policy(flat_transitions.obs)
```

That destroys the recurrence relation:

\[
h_t=f(h_{t-1},o_t).
\]

There are two reasonable implementation directions.

## 14.1 Save Hidden State During Rollout

For each sequence chunk, store:

```text
initial hidden state
obs[t:t+L]
action[t:t+L]
old_logp[t:t+L]
mask[t:t+L]
```

During optimization, replay the sequence beginning from the stored hidden state.

## 14.2 Use Full Episodes or Truncated BPTT

If episodes are too long, split them into fixed-length chunks, but ensure that:

- each chunk keeps its correct initial hidden state;
- hidden state is reset at terminal boundaries;
- padded timesteps are excluded with a mask;
- every chunk still inherits the trajectory-level \(A_i\) of the episode to which it belongs.

---

# 15. Should the Vision Encoder Be Trained During GRPO?

The student-architecture description explicitly states that the vision encoder is jointly fine-tuned with the student policy.

For Phase 3 specifically, however, the paper does not provide a separate ablation or an explicit sentence saying whether the vision encoder is frozen or unfrozen during GRPO.

Given the wording “fine-tune the student policy with GRPO,” the most natural implementation is:

```text
vision encoder + LSTM + actor head
               ↑
          jointly updated
```

But a strict reproduction should treat this as an implementation detail worth checking or ablating rather than claiming that “the Phase-3 vision encoder is definitely unfrozen” as a separately confirmed hyperparameter.

Useful comparisons include:

```text
A. full-policy GRPO
B. freeze vision backbone, update LSTM + head
C. use a lower LR for the vision backbone
```

For sim-to-real, full fine-tuning can help adapt perception to closed-loop control, but it also risks moving the DAgger-learned visual representation away from a stable region.

---

# 16. Role of Domain Randomization During GRPO

The complete DoorMan pipeline is built on large-scale simulator randomization.

### Physical Randomization

- door type;
- door dimensions;
- handle location;
- hinge damping;
- handle resistive torque;
- latch mechanics;
- spring-loaded effects.

### Visual Randomization

- PBR material;
- texture;
- lighting;
- 5,233 dome-light textures;
- camera intrinsics/extrinsics;
- motion blur / rendering variation.

The goal of GRPO is not to fit one fixed simulated door to 100% success. It is to self-refine under a broad randomized simulation distribution.

From the overall method and the paper's sim-to-real discussion, GRPO fine-tuning and extensive domain randomization should be viewed as complementary. Without broad randomization, there is a substantial risk of:

\[
\pi_{GRPO}
\rightarrow
\text{overfit to a narrow simulator configuration}.
\]

---

# 17. Which GRPO Hyperparameters Does the DoorMan Paper Actually Report?

This distinction is important.

| Item | Reported? | What can be confirmed from the paper/project page |
|---|---:|---|
| Policy initialization | ✓ | DAgger vision student |
| Algorithm | ✓ | actor-only GRPO / PPO-style clipping |
| Advantage | ✓ | group-normalized trajectory return |
| Reward | partial | mainly binary success + joint velocity / acceleration / action-rate regularization |
| Group size \(G\) | **✗** | not given |
| Clip \(\epsilon\) | **✗** | appears in equation, numerical value not given |
| GRPO learning rate | **✗** | not given |
| Policy epochs per update | **✗** | not given |
| Minibatch size | **✗** | not given |
| Entropy coefficient | **✗** | not given |
| Explicit reference-policy KL penalty | absent from equation | DoorMan Eq. 5 has no reference-policy KL term |
| Advantage epsilon | **✗** | not given |
| Exact regularizer weights | **✗** | not given |
| Group-matching rule | **✗** | not given |
| Phase-3 compute | ✓ | project page: 64 × L40S, about 12 h |

Therefore, a reproduction that claims “DoorMan GRPO uses \(G=X\), LR=Y” should not present those values as facts from the paper unless they come from additional author-provided information.

---

# 18. Current State of the Official Open-Source Repository

The DoorMan project page points to NVIDIA's official repository:

```text
NVlabs/GR00T-VisualSim2Real
```

The current public main branch contains infrastructure such as:

- PPO trainers;
- distillation trainers;
- PPO configuration;
- DAgger / vision-distillation configuration;
- IsaacLab loco-manipulation infrastructure.

At present, the public `gr00t/rl/trl/trainer/` directory contains files such as:

```text
distill_trainer.py
distill_trainer_obj_pred.py
distill_trainer_obj_pred_homie_api.py
ppo_trainer.py
ppo_trainer_homie_api.py
```

and `gr00t/rl/config/algo/` publicly exposes PPO / DAgger-related configuration rather than a standalone `grpo_trainer.py` / `grpo.yaml`.

Therefore:

> **The complete implementation and exact hyperparameters of Paper Phase 3 cannot currently be reconstructed one-for-one from the public main branch.**

This is why this document separates paper-confirmed facts from recommended implementation choices.

---

# 19. Minimal Modification Path from the Official PPO Trainer to GRPO

The public PPO configuration can be used as engineering scaffolding, but its PPO hyperparameters should not automatically be interpreted as the DoorMan GRPO hyperparameters.

A minimal conversion would look approximately as follows.

## 19.1 Actor-Critic → Actor-Only

Original:

```python
actor_out = actor(actor_obs)
value = critic(critic_obs)
```

Change to:

```python
dist = actor(student_obs)
```

Remove the critic graph and critic optimizer.

---

## 19.2 Add Episode Indices to Rollout Storage

```python
storage.add(
    obs,
    hidden,
    action,
    old_logp,
    done,
    episode_id,
    regularizer_terms,
)
```

The trainer must be able to answer:

```text
Which trajectory does this timestep belong to?
```

---

## 19.3 Remove GAE

Original PPO:

```python
advantages, returns = compute_gae(
    rewards,
    values,
    next_values,
    gamma,
    lam,
)
```

GRPO:

```python
episode_returns = aggregate_episode_return(storage)
A_episode = group_normalize(episode_returns)
advantages = broadcast_to_timesteps(A_episode, episode_ids)
```

---

## 19.4 Remove Value Loss

Original:

```python
loss = actor_loss + value_coef * value_loss - entropy_coef * entropy
```

Minimal paper-faithful GRPO:

```python
loss = actor_loss
```

If entropy regularization is retained, it becomes an additional implementation choice rather than a term explicitly written in DoorMan Eq. 5.

---

## 19.5 Keep PPO Clipping

```python
ratio = exp(new_logp - old_logp)
loss = -mean(min(
    ratio * A,
    clip(ratio, 1-eps, 1+eps) * A
))
```

This is a core part of the objective and should not be removed.

---

# 20. Suggested GRPO Configuration Skeleton

The following is **not** the original DoorMan configuration. It simply makes the fields required for an implementation explicit.

```yaml
algo:
  name: grpo

  # exact DoorMan value NOT REPORTED
  clip_param: ???
  actor_learning_rate: ???
  num_learning_epochs: ???
  num_mini_batches: ???
  max_grad_norm: ???

  # GRPO-specific
  group_size: ???            # paper does not report G
  advantage_eps: 1.0e-8     # numerical safeguard; engineering choice
  normalize_advantage: true
  advantage_level: trajectory

  # No critic
  use_critic: false
  use_gae: false
  value_loss_coef: 0.0

  # reward
  reward:
    task_success: 1.0        # scale not reported
    joint_velocity_coef: ???
    joint_acceleration_coef: ???
    action_rate_coef: ???

  # recurrent policy
  recurrent:
    enabled: true
    preserve_hidden_state: true
    sequence_minibatches: true

  # visual policy
  vision:
    train_encoder: ???       # likely joint fine-tuning, but phase-3 detail not explicit

  # rollout
  rollout:
    complete_episodes: true
    domain_randomization: true
```

Every `???` should be determined from additional author code/materials or through your own ablations rather than replaced with an invented “official DoorMan value.”

---

# 21. Can the Official PPO `clip_param=0.2` Be Reused Directly?

The current public PPO configuration does contain values such as:

```yaml
clip_param: 0.2
gamma: 0.99
lam: 0.95
num_learning_epochs: 5
num_mini_batches: 4
actor_learning_rate: 1.e-3
max_grad_norm: 1.0
```

However, these are values from the **public PPO configuration**.

The DoorMan paper does not state that Phase-3 GRPO uses exactly the same \(\epsilon\), learning rate, and number of epochs.

The correct interpretation is therefore:

- `0.2` is a reasonable implementation starting point;
- it should not be reported as “DoorMan's GRPO clipping epsilon is 0.2.”

Likewise, if `gamma` and `lambda` are only used to compute PPO-GAE advantages, they are unnecessary in a pure implementation of DoorMan Eq. 4–5 because GRPO does not use GAE.

---

# 22. How GRPO Can Produce the “Keep the Handle Visible” Behavior

This is one of the most important aspects of DoorMan.

The privileged teacher receives an exact handle transform. Therefore, even if the handle is visually occluded:

```text
Teacher:
    I know exactly where the handle is.
    → no need to move camera/body just to see it.
```

The student does not have that information:

```text
Student:
    handle disappears from RGB
    → state uncertainty rises
    → subsequent action becomes unreliable
```

DAgger can only tell the student:

```text
what action the teacher took in this true simulator state
```

GRPO, in contrast, can tell the student:

```text
your own closed-loop trajectory that slightly shifts the body and keeps the
handle visible eventually succeeds more often
```

Therefore:

\[
R_{visible\ strategy}
>
R_{occluded\ strategy},
\]

which leads to:

\[
\hat A_{visible}>0,
\quad
\hat A_{occluded}<0.
\]

Across repeated iterations, the policy can develop an active visual-feedback strategy.

In this sense, DoorMan GRPO is not primarily teaching a new symbolic subskill. It is directly optimizing the loop:

> **perception uncertainty → embodied motion → better future observation**.

---

# 23. Why the GRPO Student Mostly Reaches the Teacher Ceiling Instead of Greatly Exceeding It

The trend in Figure 6(a) is approximately:

```text
Teacher: ~80–90%

Student after DAgger: ~50–70%

Student after GRPO: ~80.8–85.8%
```

The paper notes that the student curves plateau around the teacher upper bound.

A useful interpretation is:

1. the teacher defines the initial skill manifold;
2. DAgger transfers most of the motor skill and task structure into the student;
3. the main GRPO gain comes from compensating for partial observability;
4. GRPO is not a complete re-training phase detached from the teacher.

Thus, the evidence in DoorMan more strongly supports:

> **GRPO closes the observability gap**

than:

> **GRPO causes the student to greatly exceed the teacher's task competence.**

That distinction is important when interpreting the contribution.

---
# 24. Why Not Simply Continue DAgger?

Continuing DAgger still optimizes an objective approximately of the form:

\[
L_{BC}
=
\mathbb E
\left[
\|a_S(o)-a_T(s)\|^2
\right].
\]

It rewards action similarity.

GRPO instead rewards:

\[
\text{task success under the student's own closed loop}.
\]

When those objectives conflict, for example:

```text
Teacher:
knows the exact handle location → reach directly

Student:
handle is almost leaving the camera frame → better to adjust torso first
```

continued DAgger tends to pull the student back toward the teacher action.

GRPO allows the student to take an action the teacher never needed, if that action is better under the student's own observation constraints.

That is the meaning of bootstrapping beyond imitation.

---

# 25. Potential Failure Modes of Sparse-Reward GRPO

## 25.1 Base Success Rate Is Too Low

If the base student has:

\[
P(success)\approx 0,
\]

then almost every group contains only failures, and GRPO receives little meaningful task ranking.

DoorMan itself emphasizes starting from a base policy with non-zero success.

**Mitigation:** train DAgger / BC until a meaningful fraction of tasks succeeds before enabling GRPO.

---

## 25.2 Success Rate Is Too High and the Group Is Too Small

If:

\[
P(success)\approx1,
\]

small groups frequently contain only successful trajectories, so the binary part of the return has zero variance.

Behavior regularizers then carry more of the ranking signal.

**Mitigation:** increase group size, increase domain-randomization difficulty, or add a secondary score that remains discriminative without turning the method back into heavy task shaping.

---

## 25.3 A Group Mixes Trajectories with Very Different Difficulty

Suppose:

```text
trajectory A: easy push door → success
trajectory B: very hard pull door → failure
```

If these are normalized relative to one another, the policy may confuse **task difficulty** with **action quality**.

The paper does not report a group-matching rule.

Engineering options include stratifying groups by:

- task family;
- door type;
- initial-distance bucket;
- physical-difficulty bucket.

This is a particularly valuable ablation for robotics GRPO.

---

## 25.4 Sparse GRPO Destabilizes the Vision Encoder

If a large learning rate is applied to the entire ResNet, a small amount of terminal-reward signal may disrupt a visual feature space that DAgger has already trained successfully.

One possible mitigation is:

```text
vision LR < recurrent/head LR
```

or temporarily freezing the backbone.

Again, this is an engineering recommendation rather than a reported DoorMan setting.

---

## 25.5 Recurrent Off-Policy Drift

If the same rollout is reused for many optimization epochs, the policy may move substantially while the stored recurrent hidden states came from the old behavior policy.

PPO clipping reduces action-distribution drift, but recurrent hidden-state distribution mismatch can still remain.

Therefore, rollout reuse should not be increased without bound.

---

# 26. Recommended Metrics to Monitor

The paper does not publish a complete logging schema. For a stable implementation, at minimum monitor the following.

## Task Metrics

```text
success_rate
success_rate / door_type
success_rate / randomization bucket
episode_length
completion_time
```

## GRPO Group Metrics

```text
group_return_mean
group_return_std
num_success_per_group
advantage_mean
advantage_std
max_abs_advantage
zero_std_group_fraction
```

## PPO-Style Optimization Metrics

```text
approx_kl
clip_fraction
importance_ratio_mean
importance_ratio_max
policy_entropy
action_std
grad_norm
```

## Robot-Behavior Regularization

```text
joint_velocity_cost
joint_acceleration_cost
action_rate_cost
fall_rate
undesired_contact_rate
```

## Vision / Active-Perception Diagnostics

If simulator ground truth is available, it can be used **only for diagnostics and not provided to the student**:

```text
handle_in_fov_fraction
handle_pixel_distance_to_image_center
handle_occlusion_fraction
camera_to_handle_distance_error
```

These metrics are especially useful for directly testing the paper's interpretation:

> Does GRPO actually learn motions that improve observability?

---

# 27. Recommended Ablations

If the goal is not merely to reproduce DoorMan but to study DoorMan-style GRPO, the following comparisons are particularly informative.

### A. DAgger Only vs DAgger + GRPO

This is the paper's main comparison and should be reproduced first.

### B. Binary Success Only vs Binary + Regularizers

Tests whether the simple shaping terms are mainly preserving natural behavior and providing numerical ranking.

### C. Global Group vs Matched-Condition Group

Studies what the correct definition of a “group” should be in robotics GRPO.

### D. Trajectory-Level \(A\) vs Timestep-Return \(A\)

Tests whether DoorMan's coarse credit assignment is a necessary or useful simplification.

### E. Full Vision Fine-Tuning vs Frozen Vision Encoder

Determines whether gains come from changing perception representations or mainly from changing recurrent/control behavior.

### F. Different Group Sizes \(G\)

In particular, measure:

```text
zero-variance group frequency
gradient variance
rare-success amplification
wall-clock efficiency
```

### G. PPO Critic Fine-Tuning vs Actor-Only GRPO

This is the cleanest methodological comparison:

```text
same DAgger checkpoint
same reward
same simulator randomization
same rollout budget
```

Change only:

```text
PPO: critic + GAE
GRPO: group-relative return
```

That experiment directly tests whether GRPO itself provides value in partially observable loco-manipulation.

---

# 28. Minimal Mental Model of DoorMan-Style GRPO

The three stages can be summarized as:

```text
Teacher PPO:
    “What is the correct door-opening skill when full state is available?”

DAgger:
    “Transfer as much of that skill as possible into the RGB student.”

GRPO:
    “Now stop asking the teacher.
     Let the student act on its own,
     observe which complete closed-loop strategies actually succeed,
     and increase their probability.”
```

Mathematically:

\[
\text{Teacher skill prior}
\xrightarrow{DAgger}
\pi_{S,0}
\xrightarrow{\text{GRPO on own rollouts}}
\pi_{S,*}.
\]

The central methodological insight of DoorMan is:

> **In privileged-to-vision distillation, the final gap is not entirely imitation error; part of it is an information mismatch.**
>
> **That part cannot necessarily be repaired by a stronger BC loss alone. The vision student must re-optimize behavior inside its own POMDP.**

GRPO is the lightweight mechanism DoorMan uses for this:

- no critic needs to be trained;
- no new complex dense reward shaping is required;
- no real-world RL is needed;
- all refinement uses simulator rollouts;
- the task signal is mainly binary success;
- group-relative baselines reduce policy-gradient variance;
- PPO clipping helps keep optimization near the DAgger initialization.

---

# 29. One-Page Reproduction Checklist

## Before Starting Phase 3

- [ ] Teacher PPO has converged
- [ ] RGB student has completed DAgger
- [ ] Student has a clearly non-zero task success rate
- [ ] Student recurrent state is maintained correctly during simulator rollouts
- [ ] Visual / physics domain randomization works under parallel simulation

## GRPO Rollout

- [ ] Roll out the student's own actions
- [ ] Save old action log probabilities
- [ ] Save episode boundaries
- [ ] Save LSTM hidden state / sequence masks
- [ ] Produce one scalar return for each complete trajectory
- [ ] Make task success the dominant return component
- [ ] Add only simple behavior regularizers

## Group Processing

- [ ] Form groups of \(G\) rollouts
- [ ] Compute group mean
- [ ] Compute group standard deviation
- [ ] Add an epsilon safeguard to the standard deviation
- [ ] Compute trajectory-level \(\hat A_i\)
- [ ] Broadcast \(\hat A_i\) to every timestep in its trajectory

## Optimization

- [ ] Actor only
- [ ] No critic
- [ ] No value loss
- [ ] No GAE
- [ ] Recompute current-policy log probability
- [ ] Compute \(\pi_\theta/\pi_{old}\)
- [ ] Apply PPO-style clipping
- [ ] Replay recurrent sequences correctly
- [ ] Apply gradient clipping

## Evaluation

- [ ] Success rate versus DAgger baseline
- [ ] Per-door-type statistics
- [ ] Unseen visual randomization
- [ ] Active-perception diagnostics
- [ ] Sim-to-real zero-shot test

---

# 30. What Comes Directly from DoorMan, and What Is Derived or Recommended Here?

## Explicitly Reported by DoorMan

- three-stage Teacher → DAgger Student → GRPO pipeline;
- teacher trained with PPO;
- student is an RGB/proprioception/recurrent vision policy;
- GRPO is an actor-only PPO variant;
- no value function is used;
- a group of \(G\) rollouts is sampled;
- trajectory returns are normalized using group mean/std;
- Eq. 4 defines a trajectory-level advantage;
- Eq. 5 uses a PPO clipped objective;
- the fine-tuning reward is mainly binary success;
- joint-velocity, joint-acceleration, and action-rate regularization are added;
- the student learns compensatory behaviors such as keeping the manipulated region visible;
- DAgger student success is roughly 50–70%, rising to about 80.8–85.8% after GRPO;
- the project page reports roughly 64 L40S GPUs for about 12 h for Phase 3.

## Directly Derived from the Reported Formula

- closed-form success/failure advantages under a binary reward;
- rare success automatically receives a large positive advantage;
- rare failure receives a large negative advantage once success rate is high;
- explicit rollout-buffer logic for broadcasting a trajectory advantage to timesteps.

## Engineering Recommendations / Not Publicly Reported

- numerical epsilon for standard deviation;
- matched-condition group sampling;
- exact group size;
- exact GRPO learning rate;
- exact clip epsilon;
- exact regularizer weights;
- differential learning rate for the vision backbone;
- recurrent minibatch sequence length;
- entropy bonus;
- diagnostic and ablation design.

---

# 31. An Easy-to-Miss Paper Detail: The Action-Dimension Text Appears Inconsistent

Section 2.1 states that the Unitree G1 has:

```text
29 body joints + 14 hand joints
```

which gives:

\[
29+14=43.
\]

However, the same sentence reportedly refers to an action-space dimension of 33.

The official repository README describes the relevant robot configuration as:

```text
G1 43-DOF
```

Therefore, the “33” should be treated as an apparent textual inconsistency / likely typo rather than as a reason to implement a 33-dimensional action policy.

The actual action vector should ultimately follow the G1 + hand + HOMIE interface used in the code configuration.

---

# 32. References

1. **DoorMan paper — HTML full text**<br>
   https://arxiv.org/html/2512.01061v1

2. **DoorMan arXiv page**<br>
   https://arxiv.org/abs/2512.01061

3. **DoorMan project page — NVIDIA GEAR Lab**<br>
   https://doorman-humanoid.github.io/

4. **Official code repository — NVlabs/GR00T-VisualSim2Real**<br>
   https://github.com/NVlabs/GR00T-VisualSim2Real

5. **DeepSeekMath — original GRPO paper**<br>
   https://arxiv.org/abs/2402.03300

---

# 33. The Entire Phase in One Formula

DoorMan Phase 3 can be compressed into:

\[
\boxed{
\text{DAgger Student}
+
\text{own-policy simulation rollouts}
+
\frac{R_i-\mu_R}{\sigma_R}
+
\text{PPO clipping}
-
\text{critic}
\;\Longrightarrow\;
\text{closed-loop RGB policy refinement}
}
\]

The important point is not the name “GRPO” itself. It is the shift in what defines a good behavior:

> **Use the student's own task outcomes to redefine which behaviors are desirable, allowing the student to move from “imitating a teacher with privileged state” to “actively finding closed-loop strategies that succeed under its own partial observations.”**
