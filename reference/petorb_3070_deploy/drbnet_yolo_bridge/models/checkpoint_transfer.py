"""Transfer only the original DRBNet_single encoder parameters."""

from __future__ import annotations

from pathlib import Path

import torch

from models.drb_encoder import DRBEncoder
from third_party.drbnet.DRBNet import DRBNet_single


def pretraining_model() -> DRBNet_single:
    """Original encoder + deblurring decoder for the separate pretraining stage."""
    return DRBNet_single()


def load_pretrained_encoder(encoder: DRBEncoder, checkpoint: str | Path) -> None:
    """Copy matching encoder tensors; decoder tensors are intentionally ignored.

    The bundled checkpoint is the upstream single-image deblurring checkpoint.
    This is weight transfer, not evidence of PetOrb-specific pretraining.
    """
    raw = torch.load(checkpoint, map_location="cpu", weights_only=True)
    state = raw.get("state_dict", raw) if isinstance(raw, dict) else raw
    state = {key.removeprefix("module."): value for key, value in state.items()}
    expected = encoder.state_dict()
    copied = {key: state[key] for key in expected if key in state and state[key].shape == expected[key].shape}
    missing = sorted(set(expected) - set(copied))
    if missing:
        raise ValueError(f"DRBNet checkpoint does not cover the encoder: {missing[:8]}")
    encoder.load_state_dict(copied, strict=True)
