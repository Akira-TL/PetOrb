"""Architecture sketch: DRBNet encoder -> YOLO11m pyramid -> OBB head.

This module wires real PyTorch modules and the copied PetOrb YOLO weights.
It does not define a training loop, loss, data pipeline, or deployment path.
The newly introduced feature adapter has random weights until trained.
"""

from __future__ import annotations

from pathlib import Path

import torch
from torch import nn
from ultralytics import YOLO

from models.checkpoint_transfer import load_pretrained_encoder
from models.drb_encoder import DRBEncoder


def conv_block(in_channels: int, out_channels: int, stride: int = 1) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.SiLU(inplace=True),
    )


class DRBToYOLOPyramid(nn.Module):
    """Map DRBNet's 1/4 and 1/8 features to YOLO11m's P3/P4/P5 inputs.

    P3, P4 and P5 have strides 8, 16 and 32 and 512 channels each, matching
    layers 4, 6 and 10 of the copied PetOrb YOLO11m-OBB checkpoint.
    """

    def __init__(self) -> None:
        super().__init__()
        self.from_s8 = conv_block(256, 512)
        self.from_s4 = conv_block(128, 512, stride=2)
        self.to_p4 = conv_block(512, 512, stride=2)
        self.to_p5 = conv_block(512, 512, stride=2)

    def forward(self, features: dict[str, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        p3 = self.from_s8(features["s8"]) + self.from_s4(features["s4"])
        p4 = self.to_p4(p3)
        p5 = self.to_p5(p4)
        return p3, p4, p5


class YOLO11mOBBNeckHead(nn.Module):
    """Reuse layers 11-23 from the PetOrb YOLO11m-OBB checkpoint.

    The old YOLO backbone (layers 0-10) is omitted. The DRB adapter supplies
    its three skip features to the existing FPN/PAN neck and OBB head.
    """

    def __init__(self, yolo_checkpoint: str | Path) -> None:
        super().__init__()
        original = YOLO(str(yolo_checkpoint)).model
        if len(original.model) != 24 or type(original.model[23]).__name__ != "OBB":
            raise ValueError("Expected the copied 24-layer PetOrb YOLO11m-OBB model")
        self.layers = nn.ModuleList(original.model[11:24])

    def forward(self, p3: torch.Tensor, p4: torch.Tensor, p5: torch.Tensor):
        layer = lambda number: self.layers[number - 11]
        up_p5 = layer(11)(p5)
        neck_p4 = layer(13)(layer(12)([up_p5, p4]))
        up_p4 = layer(14)(neck_p4)
        neck_p3 = layer(16)(layer(15)([up_p4, p3]))
        down_p3 = layer(17)(neck_p3)
        out_p4 = layer(19)(layer(18)([down_p3, neck_p4]))
        down_p4 = layer(20)(out_p4)
        out_p5 = layer(22)(layer(21)([down_p4, p5]))
        return layer(23)([neck_p3, out_p4, out_p5])


class BlurRobustOBB(nn.Module):
    """Proposed detection graph; no trained combined checkpoint exists yet."""

    def __init__(self, drb_checkpoint: str | Path, yolo_checkpoint: str | Path) -> None:
        super().__init__()
        self.encoder = DRBEncoder()
        load_pretrained_encoder(self.encoder, drb_checkpoint)
        self.adapter = DRBToYOLOPyramid()
        self.neck_head = YOLO11mOBBNeckHead(yolo_checkpoint)

    def forward(self, rgb_minus1_to1: torch.Tensor):
        features = self.encoder(rgb_minus1_to1)
        p3, p4, p5 = self.adapter(features)
        return self.neck_head(p3, p4, p5)
