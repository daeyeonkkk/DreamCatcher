from app.raw_engine_v2.shared.lens_correction import build_lens_correction_plan
from app.raw_engine_v2.shared.metadata import normalize_raw_metadata, summarize_bracket_metadata
from app.raw_engine_v2.shared.noise_model import estimate_noise_profile, summarize_bracket_noise
from app.raw_engine_v2.shared.raw_io import build_raw_input_bundle
from app.raw_engine_v2.shared.scene_linear import (
    build_scene_linear_plan,
    build_scene_linear_spec,
    normalize_sensor_channels,
    normalize_sensor_value,
)


def test_shared_raw_input_bundle_supports_single_and_bracket_inputs():
    single = build_raw_input_bundle([r"C:\captures\frame_001.CR3"])
    assert single.kind == "single_raw"
    assert [frame.frame_role for frame in single.frames] == ["single"]
    assert single.reference_frame().file_name == "frame_001.CR3"

    bracket = build_raw_input_bundle(
        [
            r"C:\captures\frame_low.CR3",
            r"C:\captures\frame_mid.CR3",
            r"C:\captures\frame_high.CR3",
        ],
        bracket_id="bracket_demo",
    )
    assert bracket.kind == "raw_bracket"
    assert bracket.bracket_id == "bracket_demo"
    assert [frame.frame_role for frame in bracket.frames] == ["low", "middle", "high"]
    assert bracket.reference_frame().file_name == "frame_mid.CR3"
    assert [plan.decoder_key for plan in bracket.build_decode_plans()] == [
        "raw_decode.cr3",
        "raw_decode.cr3",
        "raw_decode.cr3",
    ]


def test_metadata_normalization_handles_camera_lens_and_sensor_levels():
    metadata = normalize_raw_metadata(
        {
            "Make": "Canon",
            "Model": "EOS R5",
            "LensModel": "RF24-70mm F2.8 L IS USM",
            "ISO": "800",
            "ExposureTime": "1/125",
            "FNumber": "2.8",
            "FocalLength": [70, 1],
            "ExposureBiasValue": "-1/3",
            "BlackLevel": [512, 513, 512, 514],
            "WhiteLevel": [16383],
            "BitsPerSample": 14,
            "CFAPattern": [0, 1, 1, 2],
        },
        source_path=r"C:\captures\frame_001.CR3",
    )

    assert metadata.camera_key == "canon_eos_r5"
    assert metadata.lens_key == "rf24_70mm_f2_8_l_is_usm"
    assert metadata.iso == 800
    assert metadata.exposure_seconds == 1 / 125
    assert metadata.aperture_f_number == 2.8
    assert metadata.focal_length_mm == 70.0
    assert round(metadata.exposure_bias_ev, 4) == round(-1 / 3, 4)
    assert metadata.black_level == (512.0, 513.0, 512.0, 514.0)
    assert metadata.white_level == 16383.0
    assert metadata.cfa_pattern == "rggb"
    assert metadata.reference_black_level() == 512.75
    assert metadata.dynamic_range_code_values() == 15870.25


def test_bracket_summary_noise_lens_and_scene_linear_plans_share_same_metadata_contract():
    records = [
        normalize_raw_metadata(
            {
                "Make": "Nikon",
                "Model": "Z8",
                "LensModel": "NIKKOR Z 24-120mm f/4 S",
                "ISO": 200,
                "ExposureTime": "1/1000",
                "FNumber": 4.0,
                "FocalLength": 24,
                "BlackLevel": 512,
                "WhiteLevel": 16383,
                "CFAPattern": "RGGB",
            },
            source_path=r"C:\captures\frame_0.NEF",
        ),
        normalize_raw_metadata(
            {
                "Make": "Nikon",
                "Model": "Z8",
                "LensModel": "NIKKOR Z 24-120mm f/4 S",
                "ISO": 200,
                "ExposureTime": "1/125",
                "FNumber": 4.0,
                "FocalLength": 24,
                "BlackLevel": 512,
                "WhiteLevel": 16383,
                "CFAPattern": "RGGB",
            },
            source_path=r"C:\captures\frame_1.NEF",
        ),
        normalize_raw_metadata(
            {
                "Make": "Nikon",
                "Model": "Z8",
                "LensModel": "NIKKOR Z 24-120mm f/4 S",
                "ISO": 200,
                "ExposureTime": "1/15",
                "FNumber": 4.0,
                "FocalLength": 24,
                "BlackLevel": 512,
                "WhiteLevel": 16383,
                "CFAPattern": "RGGB",
            },
            source_path=r"C:\captures\frame_2.NEF",
        ),
    ]

    bracket_summary = summarize_bracket_metadata(records)
    assert bracket_summary.frame_count == 3
    assert bracket_summary.shared_camera_key == "nikon_z8"
    assert bracket_summary.shared_lens_key == "nikkor_z_24_120mm_f_4_s"
    assert bracket_summary.reference_frame_index == 1
    assert bracket_summary.exposure_order == "ascending"
    assert bracket_summary.mixed_sensor_calibration is False

    noise_profiles = [estimate_noise_profile(record) for record in records]
    noise_summary = summarize_bracket_noise(noise_profiles)
    assert noise_summary.frame_count == 3
    assert noise_summary.iso_values == (200, 200, 200)
    assert noise_summary.peak_shot_noise_scale > 0.0
    assert noise_summary.peak_read_noise_scale > 0.0

    lens_plan = build_lens_correction_plan(records[1])
    assert lens_plan.apply_distortion is True
    assert lens_plan.apply_vignette is True
    assert lens_plan.distortion_model == "brown_conrady"
    assert lens_plan.crop_margin_ratio > 0.0

    scene_linear_spec = build_scene_linear_spec()
    scene_linear_plan = build_scene_linear_plan(
        records[1],
        noise_profile=noise_profiles[1],
        lens_correction=lens_plan,
    )
    assert scene_linear_spec.relative_path == "scene_linear.exr"
    assert scene_linear_plan.target_relative_path == "scene_linear.exr"
    assert scene_linear_plan.noise_model_key == "phase1_deterministic_noise_profile"
    assert scene_linear_plan.distortion_model == "brown_conrady"


def test_scene_linear_normalization_clamps_sensor_values_into_unit_range():
    metadata = normalize_raw_metadata(
        {
            "Make": "Sony",
            "Model": "A7R V",
            "ISO": 400,
            "ExposureTime": "1/60",
            "BlackLevel": [512, 512, 512, 512],
            "WhiteLevel": 16383,
            "CFAPattern": "RGGB",
        }
    )

    assert normalize_sensor_value(512, black_level=512, white_level=16383) == 0.0
    assert normalize_sensor_value(16383, black_level=512, white_level=16383) == 1.0
    assert round(normalize_sensor_value(8447.5, black_level=512, white_level=16383), 4) == 0.5
    assert normalize_sensor_channels([512, 8447.5, 16383], metadata) == (0.0, 0.5, 1.0)
