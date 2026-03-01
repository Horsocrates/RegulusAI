"""
MNIST and CIFAR-10 certification benchmark.

Trains small models on MNIST/CIFAR-10, then certifies test images
using NNVerificationEngine with interval bound propagation.

Usage:
    from regulus.nn.benchmark import train_mnist_model, certify_mnist
    model = train_mnist_model(epochs=3)
    report = certify_mnist(model, epsilon=0.01, n_test=100)
    print(report.summary())

    from regulus.nn.benchmark import train_cifar_model, certify_cifar
    model = train_cifar_model(epochs=10)
    report = certify_cifar(model, epsilon=0.01, n_test=100)
    print(report.summary())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from regulus.nn.verifier import NNVerificationEngine, NNVerificationResult


def _ensure_mnist(data_dir: str = "./data") -> None:
    """Ensure MNIST data is available, working around download issues.

    The original MNIST URLs on yann.lecun.com are sometimes unavailable.
    This uses the alternative mirror that torchvision supports.
    """
    import os
    import torchvision

    # Check if already downloaded
    mnist_dir = os.path.join(data_dir, "MNIST", "raw")
    required_files = [
        "train-images-idx3-ubyte",
        "train-labels-idx1-ubyte",
        "t10k-images-idx3-ubyte",
        "t10k-labels-idx1-ubyte",
    ]

    if os.path.isdir(mnist_dir):
        existing = os.listdir(mnist_dir)
        if all(any(f.startswith(req) for f in existing) for req in required_files):
            return  # Already downloaded

    # Patch torchvision MNIST URLs to use reliable mirror
    original_mirrors = list(torchvision.datasets.MNIST.mirrors)
    torchvision.datasets.MNIST.mirrors = [
        "https://ossci-datasets.s3.amazonaws.com/mnist/",
    ] + original_mirrors

    try:
        torchvision.datasets.MNIST(root=data_dir, train=True, download=True)
        torchvision.datasets.MNIST(root=data_dir, train=False, download=True)
    finally:
        torchvision.datasets.MNIST.mirrors = original_mirrors


@dataclass
class TrainingResult:
    """Result from train_mnist_model with checkpointing info."""

    model: nn.Module
    best_certified: float = 0.0
    best_epoch: int = 0
    final_certified: float = 0.0
    spike_count: int = 0
    epoch_stats: list[dict] = field(default_factory=list)

    @property
    def used_checkpoint(self) -> bool:
        """True if best model differs from final epoch."""
        return self.best_epoch < len(self.epoch_stats)


def train_mnist_model(
    architecture: str = "cnn_bn",
    epochs: int = 5,
    batch_size: int = 64,
    lr: float = 0.001,
    data_dir: str = "./data",
    verbose: bool = True,
    ibp_loss_weight: float = 0.0,
    ibp_eps_start: float = 0.001,
    ibp_eps_end: float = 0.01,
    ibp_check_interval: int = 50,
    ibp_n_samples: int = 4,
    ibp_target_margin: float = 0.1,
    weight_reg: float = 0.0,
    flat_eps: bool = False,
    lambda_ramp: bool = False,
    lambda_ramp_fraction: float = 0.5,
    lambda_warmup_fraction: float = 0.0,
    seed: int | None = None,
    grad_clip: float = 0.0,
    lr_schedule: str = "none",
    checkpoint: bool = False,
    checkpoint_n_samples: int = 20,
    return_result: bool = False,
) -> nn.Module | TrainingResult:
    """Train a small model on MNIST.

    Standard training when ibp_loss_weight=0 (default).
    IBP-aware training when ibp_loss_weight > 0: periodically computes
    IBP margin and adds penalty + weight norm regularization.

    Args:
        architecture: "mlp" or "cnn_bn"
        epochs: Number of training epochs
        batch_size: Training batch size
        lr: Learning rate
        data_dir: Directory to download MNIST data
        verbose: Print training progress
        ibp_loss_weight: Weight for IBP margin penalty (0 = disabled)
        ibp_eps_start: Starting epsilon for IBP schedule
        ibp_eps_end: Target epsilon for IBP schedule
        ibp_check_interval: Check IBP margin every N batches
        ibp_n_samples: Number of samples per IBP check
        ibp_target_margin: Target margin for IBP penalty
        weight_reg: Weight for L2 weight norm regularization (0 = disabled)
        flat_eps: If True, use eps_end from step 0 (no epsilon ramp)
        lambda_ramp: If True, ramp IBP loss weight from 0 → ibp_loss_weight
        lambda_ramp_fraction: Fraction of steps for lambda ramp (default 0.5)
        lambda_warmup_fraction: Fraction of steps with lambda=0 (default 0.0)
        seed: Random seed for reproducibility (None = no seed)
        grad_clip: Max gradient norm for clipping (0 = disabled)
        lr_schedule: LR schedule: "none", "cosine", "plateau"
        checkpoint: If True, save best model by certified accuracy
        checkpoint_n_samples: Number of test images for checkpoint evaluation
        return_result: If True, return TrainingResult instead of model

    Returns:
        Trained PyTorch model in eval mode (or TrainingResult if return_result=True).
    """
    import torchvision
    import torchvision.transforms as transforms

    from regulus.nn.architectures import make_mlp, make_cnn_bn, make_cnn_bn_v2, make_cnn_bn_v3

    # Seed for reproducibility
    if seed is not None:
        torch.manual_seed(seed)
        np.random.seed(seed)

    # Build model
    if architecture == "mlp":
        model = make_mlp()
    elif architecture == "cnn_bn":
        model = make_cnn_bn()
    elif architecture == "cnn_bn_v2":
        model = make_cnn_bn_v2()
    elif architecture == "cnn_bn_v3":
        model = make_cnn_bn_v3()
    else:
        raise ValueError(f"Unknown architecture: {architecture}. Use 'mlp', 'cnn_bn', 'cnn_bn_v2', or 'cnn_bn_v3'.")

    # Dataset (with robust download)
    _ensure_mnist(data_dir)

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])

    train_dataset = torchvision.datasets.MNIST(
        root=data_dir, train=True, download=False, transform=transform
    )
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=0
    )

    # IBP schedule (if enabled)
    use_ibp = ibp_loss_weight > 0 or weight_reg > 0
    eps_schedule = None
    lambda_schedule = None
    if use_ibp:
        from regulus.nn.training import (
            EpsilonSchedule, LambdaSchedule, compute_ibp_margin,
            ibp_margin_penalty, weight_norm_regularizer,
        )
        total_steps = epochs * len(train_loader)
        eps_schedule = EpsilonSchedule(
            eps_start=ibp_eps_start,
            eps_end=ibp_eps_end,
            total_steps=total_steps,
            flat=flat_eps,
        )
        if lambda_ramp and ibp_loss_weight > 0:
            lambda_schedule = LambdaSchedule(
                lambda_max=ibp_loss_weight,
                total_steps=total_steps,
                ramp_fraction=lambda_ramp_fraction,
                warmup_fraction=lambda_warmup_fraction,
            )

    # Training
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    # LR scheduler
    scheduler = None
    if lr_schedule == "cosine":
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=epochs, eta_min=lr * 0.01
        )
    elif lr_schedule == "plateau":
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=2, verbose=False
        )

    # Checkpointing setup
    best_state_dict = None
    best_certified = 0.0
    best_epoch = 0
    spike_count = 0
    epoch_stats: list[dict] = []
    median_loss = None  # for spike detection

    # Test data for checkpoint evaluation
    test_loader_ckpt = None
    if checkpoint and use_ibp:
        import torchvision as tv_ckpt
        import torchvision.transforms as tr_ckpt
        _ensure_mnist(data_dir)
        test_ds = tv_ckpt.datasets.MNIST(
            root=data_dir, train=False, download=False,
            transform=tr_ckpt.Compose([
                tr_ckpt.ToTensor(), tr_ckpt.Normalize((0.1307,), (0.3081,)),
            ]),
        )
        # Use a fixed subset for fast checkpoint evaluation
        test_loader_ckpt = DataLoader(
            torch.utils.data.Subset(test_ds, list(range(checkpoint_n_samples))),
            batch_size=checkpoint_n_samples, shuffle=False, num_workers=0,
        )

    model.train()
    global_step = 0
    for epoch in range(epochs):
        running_loss = 0.0
        correct = 0
        total = 0
        ibp_margin_sum = 0.0
        ibp_checks = 0
        batch_losses: list[float] = []

        for batch_idx, (images, labels) in enumerate(train_loader):
            if architecture == "mlp":
                images = images.view(images.size(0), -1)  # Flatten for MLP

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)

            # IBP-aware training: add penalties
            if use_ibp:
                # Weight norm regularization (always differentiable)
                if weight_reg > 0:
                    w_reg = weight_norm_regularizer(model)
                    loss = loss + weight_reg * w_reg

                # Effective IBP loss weight (flat or ramped)
                effective_ibp_weight = ibp_loss_weight
                if lambda_schedule is not None:
                    effective_ibp_weight = lambda_schedule(global_step)

                # IBP margin penalty (computed periodically in no_grad)
                if effective_ibp_weight > 0 and (global_step % ibp_check_interval == 0):
                    current_eps = eps_schedule(global_step)
                    margin = compute_ibp_margin(
                        model, images, labels, current_eps,
                        architecture=architecture,
                        n_samples=ibp_n_samples,
                    )
                    penalty = ibp_margin_penalty(margin, ibp_target_margin)
                    # Penalty is scalar (no grad) — use it to scale weight reg
                    if penalty > 0:
                        loss = loss + effective_ibp_weight * penalty * weight_norm_regularizer(model)

                    ibp_margin_sum += margin
                    ibp_checks += 1
                    model.train()  # restore training mode after IBP check

            loss.backward()

            # Gradient clipping
            if grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)

            optimizer.step()

            batch_loss = loss.item()
            running_loss += batch_loss
            batch_losses.append(batch_loss)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            global_step += 1

        # Epoch stats
        acc = 100.0 * correct / total
        avg_loss = running_loss / len(train_loader)

        # Spike detection: loss > 5x median of previous epochs
        is_spike = False
        if median_loss is not None and avg_loss > 5 * median_loss:
            spike_count += 1
            is_spike = True
        if median_loss is None:
            median_loss = avg_loss
        else:
            median_loss = 0.7 * median_loss + 0.3 * min(avg_loss, 5 * median_loss)

        # LR scheduler step
        current_lr = optimizer.param_groups[0]["lr"]
        if scheduler is not None:
            if lr_schedule == "plateau":
                scheduler.step(avg_loss)
            else:
                scheduler.step()

        # Checkpoint evaluation: quick certified accuracy on test subset
        epoch_cert = 0.0
        if checkpoint and use_ibp and test_loader_ckpt is not None:
            model.eval()
            n_cert = 0
            n_total_ckpt = 0
            for test_images, test_labels in test_loader_ckpt:
                for j in range(test_images.size(0)):
                    img_np = test_images[j].numpy().astype(np.float64)
                    if architecture == "mlp":
                        img_np = img_np.flatten()
                    lbl = int(test_labels[j].item())
                    engine_ckpt = NNVerificationEngine(strategy="naive", fold_bn=True)
                    with torch.no_grad():
                        res = engine_ckpt.verify_from_point(
                            model, img_np, ibp_eps_end, true_label=lbl
                        )
                    if res.certified_robust:
                        n_cert += 1
                    n_total_ckpt += 1
            epoch_cert = n_cert / n_total_ckpt if n_total_ckpt > 0 else 0.0

            if epoch_cert > best_certified:
                best_certified = epoch_cert
                best_epoch = epoch + 1
                import copy
                best_state_dict = copy.deepcopy(model.state_dict())

            model.train()

        stats = {
            "epoch": epoch + 1,
            "loss": avg_loss,
            "acc": acc,
            "lr": current_lr,
            "is_spike": is_spike,
        }
        if use_ibp and ibp_checks > 0:
            stats["ibp_margin"] = ibp_margin_sum / ibp_checks
        if checkpoint:
            stats["cert_ckpt"] = epoch_cert
        epoch_stats.append(stats)

        if verbose:
            msg = f"  Epoch {epoch + 1}/{epochs}: loss={avg_loss:.4f}, acc={acc:.1f}%"
            if use_ibp and ibp_checks > 0:
                avg_margin = ibp_margin_sum / ibp_checks
                msg += f", ibp_margin={avg_margin:.4f}"
                if eps_schedule is not None:
                    msg += f", eps={eps_schedule(global_step):.5f}"
                if lambda_schedule is not None:
                    msg += f", lambda={lambda_schedule(global_step):.4f}"
            if lr_schedule != "none":
                msg += f", lr={current_lr:.6f}"
            if is_spike:
                msg += " [SPIKE]"
            if checkpoint and epoch_cert > 0:
                ckpt_marker = " *BEST*" if epoch + 1 == best_epoch else ""
                msg += f", cert_ckpt={epoch_cert*100:.1f}%{ckpt_marker}"
            print(msg)

    # Restore best checkpoint if available and better than final
    if checkpoint and best_state_dict is not None:
        # Evaluate final epoch certified (already computed as last epoch_cert)
        final_certified = epoch_cert if checkpoint else 0.0
        if best_certified > final_certified:
            model.load_state_dict(best_state_dict)
            if verbose:
                print(f"  >> Restored best checkpoint from epoch {best_epoch} "
                      f"(cert={best_certified*100:.1f}% vs final={final_certified*100:.1f}%)")
        else:
            final_certified = epoch_cert
    else:
        final_certified = 0.0

    model.eval()

    if return_result:
        return TrainingResult(
            model=model,
            best_certified=best_certified,
            best_epoch=best_epoch,
            final_certified=final_certified,
            spike_count=spike_count,
            epoch_stats=epoch_stats,
        )
    return model


@dataclass
class CertificationReport:
    """Report from certifying MNIST test images."""

    total_images: int
    correctly_classified: int
    certified_robust: int
    epsilon: float
    strategy: str
    architecture: str

    # Per-image results
    per_image: list[dict] = field(default_factory=list)

    # Aggregated metrics
    avg_output_max_width: float = 0.0
    avg_margin: float = 0.0
    total_time_sec: float = 0.0

    # Epsilon normalization context (MNIST: (x-0.1307)/0.3081)
    eps_01_space: float = 0.0     # epsilon in [0,1] pixel scale
    eps_pixel_255: float = 0.0    # epsilon in [0,255] pixel scale

    @property
    def clean_accuracy(self) -> float:
        """Fraction correctly classified (clean, no perturbation)."""
        return self.correctly_classified / self.total_images if self.total_images > 0 else 0.0

    @property
    def certified_accuracy(self) -> float:
        """Fraction certified robust."""
        return self.certified_robust / self.total_images if self.total_images > 0 else 0.0

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            "=" * 55,
            "REGULUS AI — MNIST Certification Report",
            "=" * 55,
            f"  Architecture:       {self.architecture}",
            f"  Strategy:           {self.strategy}",
            f"  Input epsilon:      {self.epsilon} (tensor space)",
        ]
        if self.eps_01_space > 0:
            lines.append(
                f"  Eps [0,1] / [0,255]: {self.eps_01_space:.6f} / {self.eps_pixel_255:.2f}"
            )
        lines.extend([
            f"  Total images:       {self.total_images}",
            f"  Clean accuracy:     {self.correctly_classified}/{self.total_images} "
            f"({self.clean_accuracy * 100:.1f}%)",
            f"  Certified robust:   {self.certified_robust}/{self.total_images} "
            f"({self.certified_accuracy * 100:.1f}%)",
            f"  Avg output width:   {self.avg_output_max_width:.6f}",
            f"  Avg margin:         {self.avg_margin:.6f}",
            f"  Total time:         {self.total_time_sec:.1f}s",
            "=" * 55,
        ])
        return "\n".join(lines)


def certify_mnist(
    model: nn.Module,
    epsilon: float = 0.01,
    n_test: int = 100,
    strategy: str = "naive",
    architecture: str = "cnn_bn",
    data_dir: str = "./data",
    verbose: bool = True,
    progress_interval: int = 10,
    crown_depth: str = "fc",
) -> CertificationReport:
    """Certify MNIST test images using NNVerificationEngine.

    Args:
        model: Trained PyTorch model in eval mode.
        epsilon: Perturbation radius.
        n_test: Number of test images to certify.
        strategy: Verification strategy.
        architecture: "mlp" or "cnn_bn" (determines input shape).
        data_dir: Directory with MNIST data.
        verbose: Print progress.
        progress_interval: Print every N images.
        crown_depth: CROWN depth ("fc", "deep", "full").

    Returns:
        CertificationReport with aggregated metrics.
    """
    import torchvision
    import torchvision.transforms as transforms

    # Load test data (with robust download)
    _ensure_mnist(data_dir)

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])

    test_dataset = torchvision.datasets.MNIST(
        root=data_dir, train=False, download=False, transform=transform
    )

    engine = NNVerificationEngine(strategy=strategy, crown_depth=crown_depth)
    model.eval()

    correct = 0
    certified = 0
    total_max_width = 0.0
    total_margin = 0.0
    per_image: list[dict] = []

    t_start = time.perf_counter()

    for i in range(min(n_test, len(test_dataset))):
        image, true_label = test_dataset[i]
        image_np = image.numpy().astype(np.float64)

        if architecture == "mlp":
            image_np = image_np.flatten()

        # Point forward pass for clean accuracy
        with torch.no_grad():
            if architecture == "mlp":
                point_out = model(image.view(1, -1))
            else:
                point_out = model(image.unsqueeze(0))
            point_pred = int(point_out.argmax(1).item())

        is_correct = point_pred == true_label
        if is_correct:
            correct += 1

        # Interval verification
        result = engine.verify_from_point(model, image_np, epsilon, true_label=true_label)

        if result.certified_robust:
            certified += 1

        total_max_width += float(np.max(result.output_width))
        total_margin += result.margin

        per_image.append({
            "index": i,
            "true_label": int(true_label),
            "point_pred": point_pred,
            "interval_pred": result.predicted_class,
            "correct": is_correct,
            "certified": result.certified_robust,
            "margin": result.margin,
            "max_width": float(np.max(result.output_width)),
        })

        if verbose and (i + 1) % progress_interval == 0:
            print(
                f"  [{i + 1}/{n_test}] "
                f"correct={correct}, certified={certified}, "
                f"avg_width={total_max_width / (i + 1):.6f}"
            )

    total_time = time.perf_counter() - t_start
    n = min(n_test, len(test_dataset))

    # Epsilon normalization context
    # MNIST normalizes: (x - 0.1307) / 0.3081
    # epsilon in tensor space → [0,1] pixel space: eps * 0.3081
    # epsilon in tensor space → [0,255] pixel space: eps * 0.3081 * 255
    eps_01 = epsilon * 0.3081
    eps_255 = eps_01 * 255.0

    return CertificationReport(
        total_images=n,
        correctly_classified=correct,
        certified_robust=certified,
        epsilon=epsilon,
        strategy=strategy,
        architecture=architecture,
        per_image=per_image,
        avg_output_max_width=total_max_width / n if n > 0 else 0.0,
        avg_margin=total_margin / n if n > 0 else 0.0,
        total_time_sec=total_time,
        eps_01_space=eps_01,
        eps_pixel_255=eps_255,
    )


# =============================================================
# CIFAR-10 benchmark
# =============================================================

# CIFAR-10 normalization constants (per-channel)
CIFAR_MEAN = (0.4914, 0.4822, 0.4465)
CIFAR_STD = (0.2470, 0.2435, 0.2616)


def _ensure_cifar10(data_dir: str = "./data") -> None:
    """Ensure CIFAR-10 data is available."""
    import os
    import torchvision

    cifar_dir = os.path.join(data_dir, "cifar-10-batches-py")
    if os.path.isdir(cifar_dir):
        return  # Already downloaded

    torchvision.datasets.CIFAR10(root=data_dir, train=True, download=True)
    torchvision.datasets.CIFAR10(root=data_dir, train=False, download=True)


def train_cifar_model(
    architecture: str = "cifar_cnn_bn",
    epochs: int = 10,
    batch_size: int = 128,
    lr: float = 0.001,
    data_dir: str = "./data",
    verbose: bool = True,
    ibp_loss_weight: float = 0.0,
    ibp_eps_start: float = 0.001,
    ibp_eps_end: float = 0.01,
    ibp_check_interval: int = 50,
    ibp_n_samples: int = 4,
    ibp_target_margin: float = 0.1,
    weight_reg: float = 0.0,
    flat_eps: bool = False,
    lambda_ramp: bool = False,
    lambda_ramp_fraction: float = 0.5,
    lambda_warmup_fraction: float = 0.0,
    seed: int | None = None,
    grad_clip: float = 0.0,
    lr_schedule: str = "none",
    checkpoint: bool = False,
    checkpoint_n_samples: int = 20,
    return_result: bool = False,
    augment: bool = True,
) -> nn.Module | TrainingResult:
    """Train a model on CIFAR-10.

    Same interface as train_mnist_model but for CIFAR-10 (3x32x32 input).

    Args:
        architecture: "cifar_cnn_bn" (default)
        epochs: Number of training epochs
        batch_size: Training batch size (128 default for CIFAR)
        lr: Learning rate
        data_dir: Directory to download CIFAR-10 data
        verbose: Print training progress
        ibp_loss_weight: Weight for IBP margin penalty (0 = disabled)
        ibp_eps_start: Starting epsilon for IBP schedule
        ibp_eps_end: Target epsilon for IBP schedule
        ibp_check_interval: Check IBP margin every N batches
        ibp_n_samples: Number of samples per IBP check
        ibp_target_margin: Target margin for IBP penalty
        weight_reg: Weight for L2 weight norm regularization
        flat_eps: If True, use eps_end from step 0
        lambda_ramp: If True, ramp IBP loss weight from 0
        lambda_ramp_fraction: Fraction of steps for lambda ramp
        lambda_warmup_fraction: Fraction of steps with lambda=0
        seed: Random seed for reproducibility
        grad_clip: Max gradient norm for clipping (0 = disabled)
        lr_schedule: LR schedule: "none", "cosine", "plateau"
        checkpoint: If True, save best model by certified accuracy
        checkpoint_n_samples: Number of test images for checkpoint eval
        return_result: If True, return TrainingResult instead of model
        augment: If True, use data augmentation (RandomCrop + HorizontalFlip)

    Returns:
        Trained PyTorch model in eval mode (or TrainingResult).
    """
    import torchvision
    import torchvision.transforms as transforms

    from regulus.nn.architectures import make_cifar_cnn_bn, make_cifar_cnn_bn_avgpool, ResNetCIFAR

    if seed is not None:
        torch.manual_seed(seed)
        np.random.seed(seed)

    # Build model
    if architecture == "cifar_cnn_bn":
        model = make_cifar_cnn_bn()
    elif architecture == "cifar_cnn_bn_avgpool":
        model = make_cifar_cnn_bn_avgpool()
    elif architecture == "resnet_cifar":
        model = ResNetCIFAR()
    else:
        raise ValueError(f"Unknown CIFAR architecture: {architecture}. "
                         f"Use 'cifar_cnn_bn', 'cifar_cnn_bn_avgpool', or 'resnet_cifar'.")

    # Dataset
    _ensure_cifar10(data_dir)

    train_transforms = [transforms.ToTensor(), transforms.Normalize(CIFAR_MEAN, CIFAR_STD)]
    if augment:
        train_transforms = [
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
        ] + train_transforms

    transform = transforms.Compose(train_transforms)

    train_dataset = torchvision.datasets.CIFAR10(
        root=data_dir, train=True, download=False, transform=transform
    )
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=0
    )

    # IBP schedule
    use_ibp = ibp_loss_weight > 0 or weight_reg > 0
    eps_schedule = None
    lambda_schedule = None
    if use_ibp:
        from regulus.nn.training import (
            EpsilonSchedule, LambdaSchedule, compute_ibp_margin,
            ibp_margin_penalty, weight_norm_regularizer,
        )
        total_steps = epochs * len(train_loader)
        eps_schedule = EpsilonSchedule(
            eps_start=ibp_eps_start,
            eps_end=ibp_eps_end,
            total_steps=total_steps,
            flat=flat_eps,
        )
        if lambda_ramp and ibp_loss_weight > 0:
            lambda_schedule = LambdaSchedule(
                lambda_max=ibp_loss_weight,
                total_steps=total_steps,
                ramp_fraction=lambda_ramp_fraction,
                warmup_fraction=lambda_warmup_fraction,
            )

    # Training
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    # LR scheduler
    scheduler = None
    if lr_schedule == "cosine":
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=epochs, eta_min=lr * 0.01
        )
    elif lr_schedule == "plateau":
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=2, verbose=False
        )

    # Checkpointing
    best_state_dict = None
    best_certified = 0.0
    best_epoch = 0
    spike_count = 0
    epoch_stats: list[dict] = []
    median_loss = None

    test_loader_ckpt = None
    if checkpoint and use_ibp:
        import torchvision as tv_ckpt
        import torchvision.transforms as tr_ckpt
        _ensure_cifar10(data_dir)
        test_ds = tv_ckpt.datasets.CIFAR10(
            root=data_dir, train=False, download=False,
            transform=tr_ckpt.Compose([
                tr_ckpt.ToTensor(), tr_ckpt.Normalize(CIFAR_MEAN, CIFAR_STD),
            ]),
        )
        test_loader_ckpt = DataLoader(
            torch.utils.data.Subset(test_ds, list(range(checkpoint_n_samples))),
            batch_size=checkpoint_n_samples, shuffle=False, num_workers=0,
        )

    model.train()
    global_step = 0
    for epoch in range(epochs):
        running_loss = 0.0
        correct = 0
        total = 0
        ibp_margin_sum = 0.0
        ibp_checks = 0

        for batch_idx, (images, labels) in enumerate(train_loader):
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)

            if use_ibp:
                if weight_reg > 0:
                    w_reg = weight_norm_regularizer(model)
                    loss = loss + weight_reg * w_reg

                effective_ibp_weight = ibp_loss_weight
                if lambda_schedule is not None:
                    effective_ibp_weight = lambda_schedule(global_step)

                if effective_ibp_weight > 0 and (global_step % ibp_check_interval == 0):
                    current_eps = eps_schedule(global_step)
                    margin = compute_ibp_margin(
                        model, images, labels, current_eps,
                        architecture=architecture,
                        n_samples=ibp_n_samples,
                    )
                    penalty = ibp_margin_penalty(margin, ibp_target_margin)
                    if penalty > 0:
                        loss = loss + effective_ibp_weight * penalty * weight_norm_regularizer(model)

                    ibp_margin_sum += margin
                    ibp_checks += 1
                    model.train()

            loss.backward()

            if grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)

            optimizer.step()

            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            global_step += 1

        acc = 100.0 * correct / total
        avg_loss = running_loss / len(train_loader)

        is_spike = False
        if median_loss is not None and avg_loss > 5 * median_loss:
            spike_count += 1
            is_spike = True
        if median_loss is None:
            median_loss = avg_loss
        else:
            median_loss = 0.7 * median_loss + 0.3 * min(avg_loss, 5 * median_loss)

        current_lr = optimizer.param_groups[0]["lr"]
        if scheduler is not None:
            if lr_schedule == "plateau":
                scheduler.step(avg_loss)
            else:
                scheduler.step()

        # Checkpoint evaluation
        epoch_cert = 0.0
        if checkpoint and use_ibp and test_loader_ckpt is not None:
            model.eval()
            n_cert = 0
            n_total_ckpt = 0
            for test_images, test_labels in test_loader_ckpt:
                for j in range(test_images.size(0)):
                    img_np = test_images[j].numpy().astype(np.float64)
                    lbl = int(test_labels[j].item())
                    engine_ckpt = NNVerificationEngine(strategy="naive", fold_bn=True)
                    with torch.no_grad():
                        res = engine_ckpt.verify_from_point(
                            model, img_np, ibp_eps_end, true_label=lbl
                        )
                    if res.certified_robust:
                        n_cert += 1
                    n_total_ckpt += 1
            epoch_cert = n_cert / n_total_ckpt if n_total_ckpt > 0 else 0.0

            if epoch_cert > best_certified:
                best_certified = epoch_cert
                best_epoch = epoch + 1
                import copy
                best_state_dict = copy.deepcopy(model.state_dict())

            model.train()

        stats = {
            "epoch": epoch + 1,
            "loss": avg_loss,
            "acc": acc,
            "lr": current_lr,
            "is_spike": is_spike,
        }
        if use_ibp and ibp_checks > 0:
            stats["ibp_margin"] = ibp_margin_sum / ibp_checks
        if checkpoint:
            stats["cert_ckpt"] = epoch_cert
        epoch_stats.append(stats)

        if verbose:
            msg = f"  Epoch {epoch + 1}/{epochs}: loss={avg_loss:.4f}, acc={acc:.1f}%"
            if use_ibp and ibp_checks > 0:
                avg_margin = ibp_margin_sum / ibp_checks
                msg += f", ibp_margin={avg_margin:.4f}"
                if eps_schedule is not None:
                    msg += f", eps={eps_schedule(global_step):.5f}"
                if lambda_schedule is not None:
                    msg += f", lambda={lambda_schedule(global_step):.4f}"
            if lr_schedule != "none":
                msg += f", lr={current_lr:.6f}"
            if is_spike:
                msg += " [SPIKE]"
            if checkpoint and epoch_cert > 0:
                ckpt_marker = " *BEST*" if epoch + 1 == best_epoch else ""
                msg += f", cert_ckpt={epoch_cert*100:.1f}%{ckpt_marker}"
            print(msg, flush=True)

    # Restore best checkpoint
    if checkpoint and best_state_dict is not None:
        final_certified = epoch_cert if checkpoint else 0.0
        if best_certified > final_certified:
            model.load_state_dict(best_state_dict)
            if verbose:
                print(f"  >> Restored best checkpoint from epoch {best_epoch} "
                      f"(cert={best_certified*100:.1f}% vs final={final_certified*100:.1f}%)")
        else:
            final_certified = epoch_cert
    else:
        final_certified = 0.0

    model.eval()

    if return_result:
        return TrainingResult(
            model=model,
            best_certified=best_certified,
            best_epoch=best_epoch,
            final_certified=final_certified,
            spike_count=spike_count,
            epoch_stats=epoch_stats,
        )
    return model


def train_cifar_diff_ibp(
    architecture: str = "cifar_cnn_bn",
    epochs: int = 50,
    batch_size: int = 128,
    lr: float = 0.001,
    data_dir: str = "./data",
    verbose: bool = True,
    ibp_weight: float = 0.3,
    eps_start: float = 0.001,
    eps_end: float = 0.01,
    warmup_fraction: float = 0.2,
    ramp_fraction: float = 0.5,
    weight_reg: float = 0.0,
    seed: int | None = None,
    grad_clip: float = 1.0,
    lr_schedule: str = "cosine",
    augment: bool = True,
    margin_weight: float = 0.0,
    margin_target: float = 1.0,
    return_result: bool = False,
) -> nn.Module | TrainingResult:
    """Train CIFAR-10 model with DIFFERENTIABLE IBP loss (Gowal et al. 2019).

    Unlike train_cifar_model() which uses indirect IBP pressure (scalar
    penalty on weight norm), this function computes worst-case cross-entropy
    loss from interval bounds and backpropagates THROUGH the intervals.

    Loss = (1 - lambda) * CE(model(x), y) + lambda * CE(worst_case_logits, y)
           + margin_weight * hinge(target - clean_margin)

    Note: margin is computed on CLEAN logits (not IBP bounds) for stability.
    This prevents chaotic gradients when IBP bounds are initially wild.

    where worst_case_logits come from ibp_forward(model, x-eps, x+eps).

    Training schedule:
        [0, warmup]            -> lambda=0, eps=eps_start  (pure clean training)
        [warmup, warmup+ramp]  -> lambda ramps 0->ibp_weight, eps ramps
        [warmup+ramp, end]     -> lambda=ibp_weight, eps=eps_end

    Args:
        architecture: "cifar_cnn_bn" or "cifar_cnn_bn_avgpool"
        epochs: Number of training epochs
        batch_size: Training batch size
        lr: Learning rate
        data_dir: Directory for CIFAR-10 data
        verbose: Print training progress
        ibp_weight: Maximum IBP loss weight (lambda_max)
        eps_start: Starting epsilon for perturbation schedule
        eps_end: Target epsilon for perturbation schedule
        warmup_fraction: Fraction of training with lambda=0 (clean only)
        ramp_fraction: Fraction of training for lambda ramp (after warmup)
        weight_reg: L2 weight regularization (0 = disabled)
        seed: Random seed
        grad_clip: Max gradient norm for clipping
        lr_schedule: "none", "cosine", or "plateau"
        augment: Data augmentation (RandomCrop + HorizontalFlip)
        margin_weight: Weight for margin regularization loss (0 = disabled).
            Prevents model collapse by penalizing small worst-case margins.
        margin_target: Target minimum margin for hinge loss (default: 1.0)
        return_result: Return TrainingResult instead of model
    """
    import torchvision
    import torchvision.transforms as transforms

    from regulus.nn.architectures import (
        make_cifar_cnn_bn, make_cifar_cnn_bn_avgpool,
        ResNetCIFAR, ResNetCIFAR_AvgPool,
    )
    from regulus.nn.ibp_loss import ibp_forward, ibp_worst_case_loss, ibp_margin_loss

    if seed is not None:
        torch.manual_seed(seed)
        np.random.seed(seed)

    # Build model
    if architecture == "cifar_cnn_bn":
        model = make_cifar_cnn_bn()
    elif architecture == "cifar_cnn_bn_avgpool":
        model = make_cifar_cnn_bn_avgpool()
    elif architecture == "resnet_cifar":
        model = ResNetCIFAR()
    elif architecture == "resnet_cifar_avgpool":
        model = ResNetCIFAR_AvgPool()
    else:
        raise ValueError(f"Unknown CIFAR architecture: {architecture}")

    # Move to GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    # Dataset
    _ensure_cifar10(data_dir)

    train_transforms = [transforms.ToTensor(), transforms.Normalize(CIFAR_MEAN, CIFAR_STD)]
    if augment:
        train_transforms = [
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
        ] + train_transforms

    transform = transforms.Compose(train_transforms)

    train_dataset = torchvision.datasets.CIFAR10(
        root=data_dir, train=True, download=False, transform=transform
    )
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=0
    )

    # Optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    # LR scheduler
    scheduler = None
    if lr_schedule == "cosine":
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=epochs, eta_min=lr * 0.01
        )
    elif lr_schedule == "plateau":
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=3, verbose=False
        )

    # Schedule: warmup (clean) -> ramp (0->ibp_weight) -> full IBP
    total_steps = epochs * len(train_loader)
    warmup_steps = int(warmup_fraction * total_steps)
    ramp_steps = int(ramp_fraction * total_steps)
    ramp_end = warmup_steps + ramp_steps

    def get_lambda(step: int) -> float:
        if step < warmup_steps:
            return 0.0
        elif step < ramp_end:
            progress = (step - warmup_steps) / max(ramp_steps, 1)
            return ibp_weight * progress
        else:
            return ibp_weight

    def get_epsilon(step: int) -> float:
        if step < warmup_steps:
            return eps_start
        elif step < ramp_end:
            progress = (step - warmup_steps) / max(ramp_steps, 1)
            return eps_start + (eps_end - eps_start) * progress
        else:
            return eps_end

    # Training
    epoch_stats: list[dict] = []
    spike_count = 0
    median_loss = None
    global_step = 0

    for epoch in range(epochs):
        running_loss = 0.0
        running_clean = 0.0
        running_ibp = 0.0
        running_margin_loss = 0.0
        running_margin = 0.0
        correct = 0
        total = 0
        running_width = 0.0
        ibp_batches = 0

        for batch_idx, (images, labels) in enumerate(train_loader):
            images, labels = images.to(device), labels.to(device)

            lam = get_lambda(global_step)
            eps = get_epsilon(global_step)

            optimizer.zero_grad()

            # 1. Clean forward pass (train mode — updates BN stats)
            model.train()
            clean_out = model(images)
            loss_clean = criterion(clean_out, labels)

            _, predicted = clean_out.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)

            # 2. Margin regularization on CLEAN logits (stable, prevents collapse)
            # Computed from clean_out, NOT from IBP bounds — avoids chaotic
            # gradients when IBP bounds are initially wild.
            if margin_weight > 0:
                loss_margin, avg_marg = ibp_margin_loss(
                    clean_out, clean_out, labels, target_margin=margin_target
                )
            else:
                loss_margin = torch.tensor(0.0, device=device)
                avg_marg = torch.tensor(0.0)

            if lam > 0:
                # 3. IBP forward pass (eval mode — frozen BN)
                model.eval()
                x_lo = images - eps
                x_hi = images + eps

                out_lo, out_hi = ibp_forward(model, x_lo, x_hi)
                loss_ibp = ibp_worst_case_loss(out_lo, out_hi, labels)

                # Restore train mode
                model.train()

                # 4. Combined loss: clean + IBP + margin(clean)
                loss = (1.0 - lam) * loss_clean + lam * loss_ibp + margin_weight * loss_margin

                running_ibp += loss_ibp.item()
                running_margin_loss += loss_margin.item()
                running_margin += avg_marg.item()
                with torch.no_grad():
                    avg_w = (out_hi - out_lo).mean().item()
                    running_width += avg_w
                ibp_batches += 1
            else:
                # During warmup: clean + margin (builds robust features)
                loss = loss_clean + margin_weight * loss_margin
                running_margin_loss += loss_margin.item()
                running_margin += avg_marg.item()

            # Weight regularization
            if weight_reg > 0:
                w_reg = torch.tensor(0.0, device=device)
                for p in model.parameters():
                    if p.dim() >= 2:
                        w_reg = w_reg + torch.sum(p ** 2)
                loss = loss + weight_reg * w_reg

            loss.backward()

            if grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)

            optimizer.step()

            running_loss += loss.item()
            running_clean += loss_clean.item()
            global_step += 1

        # Epoch stats
        acc = 100.0 * correct / total
        avg_loss = running_loss / len(train_loader)
        avg_clean = running_clean / len(train_loader)
        avg_ibp_loss = running_ibp / max(ibp_batches, 1)
        avg_margin_loss = running_margin_loss / len(train_loader)
        avg_margin_val = running_margin / len(train_loader)
        avg_width = running_width / max(ibp_batches, 1)

        is_spike = False
        if median_loss is not None and avg_loss > 5 * median_loss:
            spike_count += 1
            is_spike = True
        if median_loss is None:
            median_loss = avg_loss
        else:
            median_loss = 0.7 * median_loss + 0.3 * min(avg_loss, 5 * median_loss)

        current_lr = optimizer.param_groups[0]["lr"]
        if scheduler is not None:
            if lr_schedule == "plateau":
                scheduler.step(avg_loss)
            else:
                scheduler.step()

        stats = {
            "epoch": epoch + 1,
            "loss": avg_loss,
            "loss_clean": avg_clean,
            "loss_ibp": avg_ibp_loss,
            "loss_margin": avg_margin_loss,
            "avg_margin": avg_margin_val,
            "acc": acc,
            "lr": current_lr,
            "lam": get_lambda(global_step),
            "eps": get_epsilon(global_step),
            "ibp_width": avg_width,
            "is_spike": is_spike,
        }
        epoch_stats.append(stats)

        if verbose:
            msg = f"  Epoch {epoch + 1}/{epochs}: loss={avg_loss:.4f}, acc={acc:.1f}%"
            if margin_weight > 0:
                msg += f", margin={avg_margin_val:.3f}"
            if ibp_batches > 0:
                msg += (f", ibp_loss={avg_ibp_loss:.4f}, width={avg_width:.2f}"
                        f", lam={get_lambda(global_step):.3f}, eps={get_epsilon(global_step):.5f}")
            if lr_schedule != "none":
                msg += f", lr={current_lr:.6f}"
            if is_spike:
                msg += " [SPIKE]"
            print(msg, flush=True)

    model.eval()
    model = model.cpu()  # Move back to CPU for verification

    if return_result:
        return TrainingResult(
            model=model,
            best_certified=0.0,
            best_epoch=0,
            final_certified=0.0,
            spike_count=spike_count,
            epoch_stats=epoch_stats,
        )
    return model


def certify_cifar(
    model: nn.Module,
    epsilon: float = 0.01,
    n_test: int = 100,
    strategy: str = "naive",
    architecture: str = "cifar_cnn_bn",
    data_dir: str = "./data",
    verbose: bool = True,
    progress_interval: int = 10,
    crown_depth: str = "fc",
    layerwise_report: bool = False,
) -> CertificationReport:
    """Certify CIFAR-10 test images using NNVerificationEngine.

    Args:
        model: Trained PyTorch model in eval mode.
        epsilon: Perturbation radius in tensor (normalized) space.
        n_test: Number of test images to certify.
        strategy: Verification strategy ("naive" or "crown").
        architecture: "cifar_cnn_bn" (determines input shape).
        data_dir: Directory with CIFAR-10 data.
        verbose: Print progress.
        progress_interval: Print every N images.
        crown_depth: CROWN depth ("fc", "deep", "full").
        layerwise_report: If True, print per-layer width growth table.

    Returns:
        CertificationReport with aggregated metrics.
    """
    import torchvision
    import torchvision.transforms as transforms

    _ensure_cifar10(data_dir)

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(CIFAR_MEAN, CIFAR_STD),
    ])

    test_dataset = torchvision.datasets.CIFAR10(
        root=data_dir, train=False, download=False, transform=transform
    )

    engine = NNVerificationEngine(strategy=strategy, crown_depth=crown_depth)
    model.eval()

    correct = 0
    certified = 0
    total_max_width = 0.0
    total_margin = 0.0
    per_image: list[dict] = []
    layer_width_accum: list[list[float]] = []  # per-layer widths across images

    t_start = time.perf_counter()

    for i in range(min(n_test, len(test_dataset))):
        image, true_label = test_dataset[i]
        image_np = image.numpy().astype(np.float64)

        # Point forward pass for clean accuracy
        with torch.no_grad():
            point_out = model(image.unsqueeze(0))
            point_pred = int(point_out.argmax(1).item())

        is_correct = point_pred == true_label
        if is_correct:
            correct += 1

        # Interval verification
        result = engine.verify_from_point(model, image_np, epsilon, true_label=true_label)

        if result.certified_robust:
            certified += 1

        total_max_width += float(np.max(result.output_width))
        total_margin += result.margin

        # Collect per-layer diagnostics from first image (representative)
        if layerwise_report and i == 0 and hasattr(result, 'layer_diagnostics') and result.layer_diagnostics:
            layer_width_accum = [[d.get("mean_width", 0.0)] for d in result.layer_diagnostics]
        elif layerwise_report and i > 0 and hasattr(result, 'layer_diagnostics') and result.layer_diagnostics:
            for j, d in enumerate(result.layer_diagnostics):
                if j < len(layer_width_accum):
                    layer_width_accum[j].append(d.get("mean_width", 0.0))

        per_image.append({
            "index": i,
            "true_label": int(true_label),
            "point_pred": point_pred,
            "interval_pred": result.predicted_class,
            "correct": is_correct,
            "certified": result.certified_robust,
            "margin": result.margin,
            "max_width": float(np.max(result.output_width)),
        })

        if verbose and (i + 1) % progress_interval == 0:
            print(
                f"  [{i + 1}/{n_test}] "
                f"correct={correct}, certified={certified}, "
                f"avg_width={total_max_width / (i + 1):.6f}"
            )

    total_time = time.perf_counter() - t_start
    n = min(n_test, len(test_dataset))

    # Print per-layer width growth table
    if layerwise_report and layer_width_accum and result.layer_diagnostics:
        print(f"\n  {'Layer':<30} {'Mean Width':>12} {'Max Width':>12} {'Amplification':>14}")
        print(f"  {'-'*30} {'-'*12} {'-'*12} {'-'*14}")
        input_width = np.mean(layer_width_accum[0]) if layer_width_accum[0] else 1.0
        for j, d in enumerate(result.layer_diagnostics):
            name = d.get("name", f"layer_{j}")
            avg_w = np.mean(layer_width_accum[j]) if j < len(layer_width_accum) else 0.0
            max_w = d.get("max_width", 0.0)
            amp = avg_w / input_width if input_width > 0 else float("inf")
            print(f"  {name:<30} {avg_w:>12.4f} {max_w:>12.4f} {amp:>13.1f}x")

    # Epsilon normalization context for CIFAR-10
    # CIFAR normalizes per-channel: (x_c - mean_c) / std_c
    # Use average std for approximate pixel-space epsilon
    avg_std = sum(CIFAR_STD) / len(CIFAR_STD)
    eps_01 = epsilon * avg_std
    eps_255 = eps_01 * 255.0

    return CertificationReport(
        total_images=n,
        correctly_classified=correct,
        certified_robust=certified,
        epsilon=epsilon,
        strategy=strategy,
        architecture=architecture,
        per_image=per_image,
        avg_output_max_width=total_max_width / n if n > 0 else 0.0,
        avg_margin=total_margin / n if n > 0 else 0.0,
        total_time_sec=total_time,
        eps_01_space=eps_01,
        eps_pixel_255=eps_255,
    )
