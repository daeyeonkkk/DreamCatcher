from __future__ import annotations

from .rawprep_benchmark_service import RawPrepBenchmarkRequest, build_rawprep_benchmark_record


def benchmark_status() -> dict[str, object]:
    try:
        record = build_rawprep_benchmark_record(
            RawPrepBenchmarkRequest(
                output_dir="_benchmark_preview",
                output_root="outputs",
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        return {
            "enabled": False,
            "status": "missing_foundation",
            "message": str(exc),
        }

    return {
        "enabled": True,
        "status": record.status,
        "message": record.summary,
        "catalog_version": record.catalog_version,
        "single_raw_sample_count": record.single_raw_sample_count,
        "single_raw_measured_sample_count": record.single_raw_measured_sample_count,
        "tri_raw_bucket_count": len(record.tri_raw_buckets),
        "tri_raw_populated_bucket_count": len(record.tri_raw_populated_bucket_ids),
        "tri_raw_measured_bucket_count": len(record.tri_raw_measured_bucket_ids),
        "tri_raw_missing_bucket_ids": record.tri_raw_missing_bucket_ids,
        "hard_case_bucket_defined": record.hard_case_bucket_defined,
        "report_template_documented": record.report_template_documented,
        "report_status": record.report_status,
        "report_path": record.report_path,
        "compare_decision_logging_defined": record.compare_decision_logging_defined,
        "compare_decision_count": record.compare_decision_count,
    }
