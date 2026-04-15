from __future__ import annotations

from pathlib import Path

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.fit_artifacts import build_dataset_fit_artifact_preview
from app.core.research_platform.dataset.qualified_rows import load_qualified_rows
from tests.research_platform_dataset_helpers import close_storage
from tests.research_platform_manifest_helpers import build_manifest_payload
from tests.research_platform_manifest_helpers import seed_dataset_rows


def test_dataset_preview_materializes_classifier_fit_by_outer_origin(tmp_path: Path):
    storage = DataStorage(tmp_path / 'research_platform_classifier_artifacts.db')
    try:
        seed_dataset_rows(storage, sample_count=12)
        manifest = {
            **build_manifest_payload(),
            'dataset_id': 'dataset-classifier-preview',
            'embargo_sec': 0,
            'weighting_version': 'classifier_density_ratio_weighting',
            'weight_definition': 'raw_odds_ratio_no_clip_no_self_normalization',
            'weight_estimator_version': 'oof_logistic_odds_ratio_v1',
            'domain_classifier_version': 'l2_logistic_shift_state_v1',
            'strata_fit_ref': 'artifact://dataset/classifier-preview/strata-fit-by-origin.json',
            'weight_fit_ref': 'artifact://dataset/classifier-preview/weight-fit-by-origin.json',
            'domain_classifier_fit_ref': 'artifact://dataset/classifier-preview/domain-classifier-fit-by-origin.json',
        }
        qualified_rows, census_rows = load_qualified_rows(storage, manifest)

        preview = build_dataset_fit_artifact_preview(
            manifest=manifest,
            qualified_rows=qualified_rows,
            census_rows=census_rows,
        )

        assert preview['weight_fit_bundle']['fit_scope'] == 'dataset_outer_origins'
        assert preview['domain_classifier_fit_bundle']['fit_scope'] == 'dataset_outer_origins'
        assert preview['weight_fit_bundle']['origin_count'] == len(preview['weight_fit_bundle']['by_origin'])
        assert preview['domain_classifier_fit_bundle']['origin_count'] == len(
            preview['domain_classifier_fit_bundle']['by_origin']
        )
        assert preview['domain_classifier_fit_bundle']['by_origin'][0]['fit_scope'] == 'outer_origin_pre_origin_fit'
    finally:
        close_storage(storage)
