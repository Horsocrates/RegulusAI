# Regulus AI — Phase D Brief: Breaking the Clean/Certified Frontier

## Context

Regulus AI is a deterministic reasoning verification system implementing the Theory of Systems framework. The NN module provides **formal mathematical certificates** that neural network outputs are correct for ALL inputs within ε-perturbation.

## Current Results (CIFAR-10, merged to main)

We built a differentiable IBP training pipeline and achieved:

| Config | λ | ε | Clean Acc | CROWN Cert | Width |
|--------|---|---|-----------|------------|-------|
| E3 (cert-focused) | 0.20 | 0.005 | 29% | **74.5%** | 0.24 |
| v4B (balanced) | 0.30 | 0.01 | 33% | 71% | 0.24 |
| F2 (clean-focused) | 0.10 | 0.005 | 35% | 60% | 0.44 |

**Starting point**: 0% certified, width=22,000
**Now**: 74.5% certified, width=0.24 (90,000× improvement)

### Architecture
- `cifar_cnn_bn`: 2×Conv2d(BN+ReLU+MaxPool) → 2×Linear — ~50K parameters
- Training: differentiable IBP loss (Gowal et al. 2019)
- Verification: IBP (interval bound propagation) + CROWN (linear relaxation)

### What we learned (12 configs, 5 experiment rounds)
1. **Margin loss is counterproductive** — inflates weights during warmup → IBP bounds explode at transition
2. **λ dead zone at 0.12-0.15** — bounds stay wide (~1.57), model gets stuck
3. **Sweet spots**: λ=0.10 (clean) and λ=0.20 (cert)
4. **Architecture is the bottleneck** — ~50K params can't be simultaneously discriminative AND IBP-tight

### Key technical components
```
regulus/nn/ibp_loss.py     — ibp_forward(), ibp_worst_case_loss(), ibp_margin_loss()
regulus/nn/benchmark.py    — train_cifar_diff_ibp() with warmup/ramp/full schedule
regulus/nn/verifier.py     — NNVerificationEngine (IBP + CROWN)
regulus/nn/architectures.py — cifar_cnn_bn, cifar_cnn_bn_avgpool, ResNetCIFAR
```

## Phase D Goal

Break through the **35% clean accuracy ceiling** while maintaining ≥40% CROWN certification.

Target: **clean ≥ 50%** AND **CROWN cert ≥ 40%** at ε=0.005

## Questions for Review

### 1. Architecture scaling
Our current model (~50K params) is capacity-limited. Options:
- **WideResNet** (WRN-28-10, ~36M params) — standard in certified training literature
- **CNN-7** (7-layer CNN, ~2M params) — Gowal et al. used this
- **Our ResNetCIFAR** (already in architectures.py, untested with IBP)

Which architecture should we prioritize? Trade-off: larger model = potentially better clean/cert, but IBP bounds scale poorly with depth.

### 2. CROWN-IBP training
Currently we train with IBP bounds (loose) but verify with CROWN (tighter). Literature suggests training with CROWN bounds ("CROWN-IBP") gives better results. This requires:
- Computing CROWN bounds during training (expensive)
- Gradually transitioning from CROWN to IBP bounds
- Implementation in ibp_loss.py

Is CROWN-IBP training worth the implementation cost, or should we focus on architecture first?

### 3. Progressive training strategies
- **ε-scheduling**: start at ε=0.001, gradually increase to ε=0.005
- **Layer-wise training**: freeze early layers, train later layers with IBP
- **Knowledge distillation**: train clean model first, distill into IBP-trained model
- **Mixup / adversarial augmentation**: complement IBP with adversarial examples

Which strategies are most promising for breaking the clean/cert frontier?

### 4. Integration with Regulus
The NN verification module should connect to the broader Regulus pipeline:
- IBP_width as a D6 (Reflection) diagnostic metric
- Certification status as a Zero-Gate signal
- Verified NN as a D5 (Inference) subsystem

How should we architect this integration?

### 5. Coq formalization timing
We have 11 proven theorems in PInterval.v (interval arithmetic). Should we:
- Formalize CROWN soundness NOW (proves current verifier is correct)
- Wait until we have better results (formalize a more capable system)
- Formalize incrementally (start with IBP soundness, add CROWN later)

## Constraints
- GPU: Vast.ai rental (RTX 3090, ~$0.14/hr)
- Local: Windows, Python 3.14, torch broken (DLL issue) — all GPU work on server
- Coq: Rocq 9.0.1 on Windows, all files compile
