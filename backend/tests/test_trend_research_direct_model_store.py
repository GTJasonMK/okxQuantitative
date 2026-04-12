import json
from pathlib import Path

from app.core.trend_research.direct_models import (
    DirectExtremaMetrics,
    DirectExtremaModelBundle,
    DirectExtremaModelConfig,
)
from app.core.trend_research import model_store


class FakeTorchModule:
    @staticmethod
    def save(payload, path):
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def load(path, map_location=None):
        return json.loads(Path(path).read_text(encoding="utf-8"))


def test_direct_model_bundle_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(model_store, "_load_torch_module", lambda: FakeTorchModule)

    bundle = DirectExtremaModelBundle(
        trained_at="2026-04-07T00:00:00+00:00",
        config=DirectExtremaModelConfig(
            architecture="tcn",
            input_minutes=120,
            horizon_minutes=60,
            bucket_seconds=60,
            hidden_channels=(32, 64),
            dropout=0.1,
            feature_names=("queue_imbalance", "basis_bps"),
        ),
        normalization_means=(0.0, 0.0),
        normalization_stds=(1.0, 2.0),
        state_dict={"encoder.weight": [[0.1, 0.2]], "encoder.bias": [0.3]},
        metrics=DirectExtremaMetrics(
            top_time_mae_minutes=4.0,
            bottom_time_mae_minutes=5.0,
            top_price_mae_bps=40.0,
            bottom_price_mae_bps=55.0,
            joint_hit_rate=0.42,
        ),
    )

    metadata_path = tmp_path / "trend_direct_model.json"
    saved_path = model_store.save_direct_model_bundle(bundle, path=metadata_path)
    loaded = model_store.load_direct_model_bundle(saved_path)

    assert saved_path == metadata_path
    assert metadata_path.exists()
    assert metadata_path.with_suffix(".pt").exists()
    assert loaded == bundle
