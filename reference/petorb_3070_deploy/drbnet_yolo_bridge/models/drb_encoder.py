"""The encoder layers of DRBNet_single, kept with their original key names.

The reconstruction decoder is used only in the pretraining model. This class
copies the encoder architecture so its weights can be transferred by name.
"""

from __future__ import annotations

import torch
from torch import nn

from third_party.drbnet.DRBNet import conv, resnet_block


class DRBEncoder(nn.Module):
    """RGB input -> DRBNet features at strides 1, 2, 4 and 8."""

    def __init__(self) -> None:
        super().__init__()
        self.conv1_1 = conv(3, 32)
        self.conv1_2 = conv(32, 32)
        self.conv1_3 = conv(32, 32)
        self.conv2_1 = conv(32, 64, stride=2)
        self.conv2_2 = conv(64, 64)
        self.conv2_3 = conv(64, 64)
        self.conv3_1 = conv(64, 128, stride=2)
        self.conv3_2 = conv(128, 128)
        self.conv3_3 = conv(128, 128)
        self.conv4_1 = conv(128, 256, stride=2)
        self.conv4_2 = conv(256, 256)
        self.conv4_3 = conv(256, 256)
        self.conv4_4 = nn.Sequential(
            conv(256, 256),
            resnet_block(256, res_num=1),
            resnet_block(256, res_num=1),
            conv(256, 256),
        )

    def forward(self, image: torch.Tensor) -> dict[str, torch.Tensor]:
        s1 = self.conv1_3(self.conv1_2(self.conv1_1(image)))
        s2 = self.conv2_3(self.conv2_2(self.conv2_1(s1)))
        s4 = self.conv3_3(self.conv3_2(self.conv3_1(s2)))
        s8 = self.conv4_3(self.conv4_2(self.conv4_1(s4)))
        s8 = self.conv4_4(s8)
        return {"s1": s1, "s2": s2, "s4": s4, "s8": s8}
