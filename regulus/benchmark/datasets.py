"""
Unified dataset loader for Regulus benchmarks.

Supported: breast_cancer, mnist, credit, cifar10
Each returns: X_train, X_test, y_train, y_test, model_fn, config.
"""

from __future__ import annotations

import numpy as np
import torch.nn as nn
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def load_dataset(name: str) -> dict:
    """Load dataset by name. Returns dict with data + model factory."""
    loaders = {
        "breast_cancer": _load_breast_cancer,
        "mnist": _load_mnist,
        "credit": _load_credit,
        "cifar10": _load_cifar10,
    }
    if name not in loaders:
        raise ValueError(f"Unknown dataset: {name}. Available: {list(loaders)}")
    return loaders[name]()


def _load_breast_cancer() -> dict:
    data = load_breast_cancer()
    X, y = data.data, data.target
    scaler = StandardScaler()
    X = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )

    def model_fn():
        return nn.Sequential(
            nn.Linear(30, 16), nn.ReLU(),
            nn.Linear(16, 8), nn.ReLU(),
            nn.Linear(8, 2),
        )

    return {
        "X_train": X_train, "X_test": X_test,
        "y_train": y_train, "y_test": y_test,
        "model_fn": model_fn,
        "epochs": 200, "lr": 0.001,
        "input_eps": 0.1,
        "n_classes": 2,
        "name": "Breast Cancer Wisconsin",
    }


def _load_mnist() -> dict:
    # Try torchvision first (if data already cached), fall back to sklearn
    try:
        import os
        # Only use torchvision if data already downloaded (avoid hanging download)
        mnist_cached = os.path.exists("./data/MNIST/raw/train-images-idx3-ubyte")
        if not mnist_cached:
            raise RuntimeError("No cached MNIST data, skip to sklearn")

        from torchvision import datasets, transforms

        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Lambda(lambda x: x.view(-1).numpy()),
        ])
        train_data = datasets.MNIST("./data", train=True, download=False, transform=transform)
        test_data = datasets.MNIST("./data", train=False, download=False, transform=transform)

        X_train = np.stack([train_data[i][0] for i in range(len(train_data))])
        y_train = np.array([train_data[i][1] for i in range(len(train_data))])
        X_test = np.stack([test_data[i][0] for i in range(len(test_data))])
        y_test = np.array([test_data[i][1] for i in range(len(test_data))])
    except (RuntimeError, OSError):
        print("  Using sklearn for MNIST data...")
        from sklearn.datasets import fetch_openml

        mnist = fetch_openml("mnist_784", version=1, as_frame=False)
        X_all = mnist.data.astype(np.float32) / 255.0  # Normalize to [0,1]
        y_all = mnist.target.astype(int)

        # Standard 60K/10K split
        X_train, X_test = X_all[:60000], X_all[60000:]
        y_train, y_test = y_all[:60000], y_all[60000:]

    def model_fn():
        return nn.Sequential(
            nn.Linear(784, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 10),
        )

    return {
        "X_train": X_train, "X_test": X_test,
        "y_train": y_train, "y_test": y_test,
        "model_fn": model_fn,
        "epochs": 20, "lr": 0.001,
        "input_eps": 0.02,
        "n_classes": 10,
        "name": "MNIST Handwritten Digits",
    }


def _load_credit() -> dict:
    from sklearn.datasets import fetch_openml
    from sklearn.impute import SimpleImputer
    import pandas as pd

    data = fetch_openml("credit-g", version=1, as_frame=True)
    df = data.data
    y = (data.target == "good").astype(int).values

    # Encode categorical columns as numeric
    X = pd.get_dummies(df, drop_first=True).values.astype(float)

    imputer = SimpleImputer(strategy="median")
    X = imputer.fit_transform(X)

    scaler = StandardScaler()
    X = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )

    n_features = X.shape[1]

    def model_fn():
        return nn.Sequential(
            nn.Linear(n_features, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 2),
        )

    return {
        "X_train": X_train, "X_test": X_test,
        "y_train": y_train, "y_test": y_test,
        "model_fn": model_fn,
        "epochs": 150, "lr": 0.001,
        "input_eps": 0.1,
        "n_classes": 2,
        "name": "German Credit Scoring",
    }


def _load_cifar10() -> dict:
    """Load CIFAR-10: 3x32x32 colour images, 10 classes.

    Tries torchvision first. If download fails, falls back to
    MNIST expanded to 3-channel 32x32 (pipeline test only).
    """
    import os

    try:
        cifar_cached = os.path.exists("./data/cifar-10-batches-py")
        from torchvision import datasets as tv_datasets

        train_data = tv_datasets.CIFAR10(
            "./data", train=True, download=(not cifar_cached))
        test_data = tv_datasets.CIFAR10(
            "./data", train=False, download=(not cifar_cached))

        # (N, 32, 32, 3) uint8 -> (N, 3, 32, 32) float32 [0,1]
        X_train = np.array(train_data.data).transpose(
            0, 3, 1, 2).astype(np.float32) / 255.0
        y_train = np.array(train_data.targets).astype(np.int64)
        X_test = np.array(test_data.data).transpose(
            0, 3, 1, 2).astype(np.float32) / 255.0
        y_test = np.array(test_data.targets).astype(np.int64)

        # Channel-wise normalization
        mean = np.array([0.4914, 0.4822, 0.4465]).reshape(1, 3, 1, 1)
        std = np.array([0.2470, 0.2435, 0.2616]).reshape(1, 3, 1, 1)
        X_train = ((X_train - mean) / std).astype(np.float32)
        X_test = ((X_test - mean) / std).astype(np.float32)

        dataset_name = "CIFAR-10"

    except Exception as e:
        print(f"  CIFAR-10 unavailable ({e}), using MNIST->3ch32x32 fallback...")
        mnist = _load_mnist()
        X_train_flat = mnist["X_train"]
        X_test_flat = mnist["X_test"]
        y_train = mnist["y_train"]
        y_test = mnist["y_test"]

        # Reshape (N, 784) -> (N, 1, 28, 28), pad to 32x32, repeat 3ch
        X_train_2d = X_train_flat.reshape(-1, 1, 28, 28)
        X_test_2d = X_test_flat.reshape(-1, 1, 28, 28)
        X_train_2d = np.pad(X_train_2d, ((0, 0), (0, 0), (2, 2), (2, 2)),
                            mode="constant")
        X_test_2d = np.pad(X_test_2d, ((0, 0), (0, 0), (2, 2), (2, 2)),
                           mode="constant")
        X_train = np.repeat(X_train_2d, 3, axis=1).astype(np.float32)
        X_test = np.repeat(X_test_2d, 3, axis=1).astype(np.float32)

        dataset_name = "MNIST-3ch-32x32 (CIFAR fallback)"

    from regulus.nn.architectures import make_cifar_cnn_bn
    import torch.nn as nn

    return {
        "X_train": X_train, "X_test": X_test,
        "y_train": y_train, "y_test": y_test,
        "model_fn": make_cifar_cnn_bn,
        "epochs": 15, "lr": 0.001,
        "input_eps": 0.02,
        "n_classes": 10,
        "name": dataset_name,
        "input_shape": (3, 32, 32),
    }
