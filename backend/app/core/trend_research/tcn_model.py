from __future__ import annotations

TORCH_IMPORT_ERROR = None

try:
    import torch
    from torch import nn
except Exception as exc:  # pragma: no cover - exercised in dependency-missing tests
    torch = None
    nn = None
    TORCH_IMPORT_ERROR = exc


TORCH_AVAILABLE = torch is not None
KERNEL_SIZE = 3


def _require_torch():
    if TORCH_AVAILABLE:
        return
    raise RuntimeError("PyTorch is required for direct extrema TCN") from TORCH_IMPORT_ERROR


if TORCH_AVAILABLE:

    class CausalResidualBlock(nn.Module):
        def __init__(self, in_channels: int, out_channels: int, *, dilation: int, dropout: float):
            super().__init__()
            padding = (KERNEL_SIZE - 1) * dilation
            self.crop = padding
            self.conv1 = nn.Conv1d(in_channels, out_channels, KERNEL_SIZE, padding=padding, dilation=dilation)
            self.norm1 = nn.GroupNorm(1, out_channels)
            self.conv2 = nn.Conv1d(out_channels, out_channels, KERNEL_SIZE, padding=padding, dilation=dilation)
            self.norm2 = nn.GroupNorm(1, out_channels)
            self.dropout = nn.Dropout(dropout)
            self.activation = nn.GELU()
            self.residual = nn.Conv1d(in_channels, out_channels, kernel_size=1) if in_channels != out_channels else nn.Identity()

        def _trim(self, values):
            return values[..., :-self.crop] if self.crop > 0 else values

        def forward(self, inputs):
            residual = self.residual(inputs)
            hidden = self._trim(self.conv1(inputs))
            hidden = self.dropout(self.activation(self.norm1(hidden)))
            hidden = self._trim(self.conv2(hidden))
            hidden = self.dropout(self.norm2(hidden))
            return self.activation(hidden + residual)


    class TCNEncoder(nn.Module):
        def __init__(self, *, input_dim: int, hidden_channels: tuple[int, ...], dropout: float):
            super().__init__()
            first_channel = hidden_channels[0]
            self.input_projection = nn.Conv1d(input_dim, first_channel, kernel_size=1)
            blocks = []
            in_channels = first_channel
            for index, out_channels in enumerate(hidden_channels):
                blocks.append(
                    CausalResidualBlock(
                        in_channels,
                        out_channels,
                        dilation=2 ** index,
                        dropout=dropout,
                    )
                )
                in_channels = out_channels
            self.blocks = nn.ModuleList(blocks)

        def forward(self, inputs):
            hidden = self.input_projection(inputs)
            for block in self.blocks:
                hidden = block(hidden)
            return hidden


    class DirectExtremaTCN(nn.Module):
        def __init__(self, *, input_dim: int, hidden_channels: tuple[int, ...], horizon_buckets: int, dropout: float):
            super().__init__()
            if not hidden_channels:
                raise ValueError("hidden_channels must not be empty")
            self.encoder = TCNEncoder(input_dim=input_dim, hidden_channels=hidden_channels, dropout=dropout)
            hidden_dim = hidden_channels[-1]
            self.top_time_head = nn.Linear(hidden_dim, horizon_buckets)
            self.bottom_time_head = nn.Linear(hidden_dim, horizon_buckets)
            self.top_return_head = nn.Linear(hidden_dim, 1)
            self.bottom_return_head = nn.Linear(hidden_dim, 1)

        def forward(self, inputs):
            if inputs.ndim != 3:
                raise ValueError("inputs must have shape [batch, sequence, features]")
            encoded = self.encoder(inputs.transpose(1, 2))[:, :, -1]
            return {
                "top_time_logits": self.top_time_head(encoded),
                "bottom_time_logits": self.bottom_time_head(encoded),
                "top_return": self.top_return_head(encoded).squeeze(-1),
                "bottom_return": self.bottom_return_head(encoded).squeeze(-1),
            }

else:

    class DirectExtremaTCN:  # pragma: no cover - behavior covered by dependency-missing test
        def __init__(self, *args, **kwargs):
            _require_torch()
