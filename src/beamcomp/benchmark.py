"""Run the beamline array compression comparison and write CSV results."""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from beamcomp.compressors import ArrayMetadata, Compressor, available_compressors
from beamcomp.data import load_array
from beamcomp.preprocessing import (
    ParameterValue,
    PreprocessingSpec,
    apply_preprocessing,
    default_preprocessing_specs,
    fixed_threshold_spec,
)


@dataclass(frozen=True)
class BenchmarkResult:
    dataset_type: str
    input_filename: str
    image_shape: tuple[int, ...]
    dtype: str
    preprocessing_method: str
    preprocessing_parameters: dict[str, ParameterValue]
    preprocessing_lossless: bool
    compressor_name: str
    lossless_vs_raw_input: bool
    reconstruction_correct: bool
    original_raw_bytes: int
    preprocessed_bytes: int
    compressed_bytes: int
    compression_ratio_vs_raw: float
    compression_ratio_vs_preprocessed: float
    compression_time_ms: float
    decompression_time_ms: float
    compression_throughput_mb_s: float
    decompression_throughput_mb_s: float
    percent_nonzero_before: float
    percent_nonzero_after: float
    max_absolute_error_vs_raw: float | None
    notes: str


CSV_FIELDS = [
    "dataset_type",
    "input_filename",
    "image_shape",
    "dtype",
    "preprocessing_method",
    "preprocessing_parameters",
    "preprocessing_lossless",
    "compressor_name",
    "lossless_vs_raw_input",
    "reconstruction_correct",
    "original_raw_bytes",
    "preprocessed_bytes",
    "compressed_bytes",
    "compression_ratio_vs_raw",
    "compression_ratio_vs_preprocessed",
    "compression_time_ms",
    "decompression_time_ms",
    "compression_throughput_mb_s",
    "decompression_throughput_mb_s",
    "percent_nonzero_before",
    "percent_nonzero_after",
    "max_absolute_error_vs_raw",
    "notes",
]


def _percent_nonzero(array: np.ndarray) -> float:
    if array.size == 0:
        return 0.0
    return 100.0 * float(np.count_nonzero(array)) / array.size


def _arrays_exact(left: np.ndarray, right: np.ndarray) -> bool:
    return (
        left.shape == right.shape
        and left.dtype == right.dtype
        and np.ascontiguousarray(left).tobytes(order="C")
        == np.ascontiguousarray(right).tobytes(order="C")
    )


def _max_absolute_error(reference: np.ndarray, candidate: np.ndarray) -> float:
    if reference.shape != candidate.shape or reference.size == 0:
        return 0.0
    conversion = np.complex128 if np.issubdtype(reference.dtype, np.complexfloating) else np.float64
    difference = np.abs(reference.astype(conversion) - candidate.astype(conversion))
    finite_difference = difference[~np.isnan(difference)]
    return float(np.max(finite_difference)) if finite_difference.size else 0.0


def _throughput_mb_s(byte_count: int, elapsed_seconds: float) -> float:
    if byte_count == 0 or elapsed_seconds <= 0:
        return 0.0
    return (byte_count / 1_000_000) / elapsed_seconds


def benchmark_array(
    array: np.ndarray,
    *,
    input_path: str | Path,
    dataset_type: str,
    preprocessing_specs: list[PreprocessingSpec] | None = None,
    compressors: list[Compressor] | None = None,
    include_optional: bool = False,
) -> list[BenchmarkResult]:
    """Benchmark every preprocessing/compressor combination for one array."""
    raw = np.ascontiguousarray(np.asarray(array))
    if raw.dtype.hasobject:
        raise ValueError("object arrays are not supported")

    specs = (
        default_preprocessing_specs()
        if preprocessing_specs is None
        else preprocessing_specs
    )
    selected_compressors = (
        available_compressors(include_optional)
        if compressors is None
        else compressors
    )
    nonzero_before = _percent_nonzero(raw)
    results: list[BenchmarkResult] = []

    for spec in specs:
        prepared = apply_preprocessing(raw, spec)
        nonzero_after = _percent_nonzero(prepared.array)

        for compressor in selected_compressors:
            compressed: bytes | None = None
            reconstructed: np.ndarray | None = None
            errors: list[str] = []

            compression_start = time.perf_counter()
            try:
                compressed = compressor.encode(prepared.array)
            except Exception as exc:  # Keep the rest of a long matrix running.
                errors.append(f"compression failed: {type(exc).__name__}: {exc}")
            compression_seconds = time.perf_counter() - compression_start

            decompression_seconds = 0.0
            if compressed is not None:
                metadata = ArrayMetadata.from_array(prepared.array)
                decompression_start = time.perf_counter()
                try:
                    reconstructed = compressor.decode(compressed, metadata)
                except Exception as exc:  # Keep the failure visible in the CSV.
                    errors.append(f"decompression failed: {type(exc).__name__}: {exc}")
                decompression_seconds = time.perf_counter() - decompression_start

            reconstruction_correct = (
                reconstructed is not None
                and _arrays_exact(prepared.array, reconstructed)
            )
            lossless_vs_raw = (
                reconstructed is not None
                and reconstruction_correct
                and _arrays_exact(raw, reconstructed)
            )
            max_error = None
            if not prepared.is_lossless and reconstructed is not None:
                max_error = _max_absolute_error(raw, reconstructed)

            compressed_size = len(compressed) if compressed is not None else 0
            ratio_vs_raw = raw.nbytes / compressed_size if compressed_size else 0.0
            ratio_vs_prepared = (
                prepared.array.nbytes / compressed_size if compressed_size else 0.0
            )
            notes = "; ".join(
                part
                for part in (prepared.notes, compressor.notes, *errors)
                if part
            )
            results.append(
                BenchmarkResult(
                    dataset_type=dataset_type,
                    input_filename=str(input_path),
                    image_shape=tuple(int(size) for size in raw.shape),
                    dtype=raw.dtype.str,
                    preprocessing_method=prepared.name,
                    preprocessing_parameters=prepared.parameters,
                    preprocessing_lossless=prepared.is_lossless,
                    compressor_name=compressor.name,
                    lossless_vs_raw_input=lossless_vs_raw,
                    reconstruction_correct=reconstruction_correct,
                    original_raw_bytes=raw.nbytes,
                    preprocessed_bytes=prepared.array.nbytes,
                    compressed_bytes=compressed_size,
                    compression_ratio_vs_raw=ratio_vs_raw,
                    compression_ratio_vs_preprocessed=ratio_vs_prepared,
                    compression_time_ms=compression_seconds * 1_000,
                    decompression_time_ms=decompression_seconds * 1_000,
                    compression_throughput_mb_s=_throughput_mb_s(
                        prepared.array.nbytes, compression_seconds
                    ),
                    decompression_throughput_mb_s=_throughput_mb_s(
                        prepared.array.nbytes, decompression_seconds
                    ),
                    percent_nonzero_before=nonzero_before,
                    percent_nonzero_after=nonzero_after,
                    max_absolute_error_vs_raw=max_error,
                    notes=notes,
                )
            )
    return results


def benchmark_file(
    input_path: str | Path,
    *,
    dataset_type: str,
    preprocessing_specs: list[PreprocessingSpec] | None = None,
    compressors: list[Compressor] | None = None,
    include_optional: bool = False,
) -> list[BenchmarkResult]:
    path = Path(input_path)
    return benchmark_array(
        load_array(path),
        input_path=path,
        dataset_type=dataset_type,
        preprocessing_specs=preprocessing_specs,
        compressors=compressors,
        include_optional=include_optional,
    )


def _format_number(value: float) -> str:
    return f"{value:.6f}"


def _result_to_csv_row(result: BenchmarkResult) -> dict[str, object]:
    return {
        "dataset_type": result.dataset_type,
        "input_filename": result.input_filename,
        "image_shape": json.dumps(result.image_shape, separators=(",", ":")),
        "dtype": result.dtype,
        "preprocessing_method": result.preprocessing_method,
        "preprocessing_parameters": json.dumps(
            result.preprocessing_parameters, sort_keys=True, separators=(",", ":")
        ),
        "preprocessing_lossless": str(result.preprocessing_lossless).lower(),
        "compressor_name": result.compressor_name,
        "lossless_vs_raw_input": str(result.lossless_vs_raw_input).lower(),
        "reconstruction_correct": str(result.reconstruction_correct).lower(),
        "original_raw_bytes": result.original_raw_bytes,
        "preprocessed_bytes": result.preprocessed_bytes,
        "compressed_bytes": result.compressed_bytes,
        "compression_ratio_vs_raw": _format_number(result.compression_ratio_vs_raw),
        "compression_ratio_vs_preprocessed": _format_number(
            result.compression_ratio_vs_preprocessed
        ),
        "compression_time_ms": _format_number(result.compression_time_ms),
        "decompression_time_ms": _format_number(result.decompression_time_ms),
        "compression_throughput_mb_s": _format_number(
            result.compression_throughput_mb_s
        ),
        "decompression_throughput_mb_s": _format_number(
            result.decompression_throughput_mb_s
        ),
        "percent_nonzero_before": _format_number(result.percent_nonzero_before),
        "percent_nonzero_after": _format_number(result.percent_nonzero_after),
        "max_absolute_error_vs_raw": (
            ""
            if result.max_absolute_error_vs_raw is None
            else _format_number(result.max_absolute_error_vs_raw)
        ),
        "notes": result.notes,
    }


def write_results_csv(
    output_path: str | Path,
    results: list[BenchmarkResult],
    *,
    append: bool = False,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append and path.exists() else "w"
    needs_header = mode == "w" or path.stat().st_size == 0
    with path.open(mode, newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerows(_result_to_csv_row(result) for result in results)


def _terminal_preprocessing_label(result: BenchmarkResult) -> str:
    if result.preprocessing_method == "median_std_zero":
        return f"median+{result.preprocessing_parameters.get('k', 2):g}std"
    if result.preprocessing_method == "right_shift":
        return f"shift {result.preprocessing_parameters['bits']} bits"
    if result.preprocessing_method == "fixed_threshold_zero":
        threshold = result.preprocessing_parameters["threshold"]
        return f"fixed < {threshold:.5g}"
    return result.preprocessing_method


def print_results_table(results: list[BenchmarkResult]) -> None:
    """Print a compact, human-readable view of benchmark results."""
    if not results:
        print("No benchmark results.")
        return

    first = results[0]
    shape = " x ".join(str(size) for size in first.image_shape)
    print()
    print(f"Input:   {first.input_filename}")
    print(f"Dataset: {first.dataset_type} | Shape: {shape} | Dtype: {first.dtype}")
    print()

    header = (
        f"{'Preprocessing':<18} {'Compressor':<23} {'Ratio':>8} "
        f"{'Bytes':>12} {'Enc MB/s':>9} {'Dec MB/s':>9} "
        f"{'NZ %':>8} {'Max err':>9} {'OK':>3}"
    )
    print(header)
    print("-" * len(header))

    previous_preprocessing = ""
    for result in results:
        preprocessing = _terminal_preprocessing_label(result)
        if previous_preprocessing and preprocessing != previous_preprocessing:
            print()
        previous_preprocessing = preprocessing
        max_error = (
            "-"
            if result.max_absolute_error_vs_raw is None
            else f"{result.max_absolute_error_vs_raw:.3g}"
        )
        print(
            f"{preprocessing:<18} {result.compressor_name:<23} "
            f"{result.compression_ratio_vs_raw:>7.2f}x "
            f"{result.compressed_bytes:>12,} "
            f"{result.compression_throughput_mb_s:>9.1f} "
            f"{result.decompression_throughput_mb_s:>9.1f} "
            f"{result.percent_nonzero_after:>8.3f} "
            f"{max_error:>9} "
            f"{'yes' if result.reconstruction_correct else 'NO':>3}"
        )
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare lossless compressors on one beamline detector array."
    )
    parser.add_argument("--input", type=Path, required=True, help="One .tif, .tiff, or .npy file.")
    parser.add_argument(
        "--dataset-type",
        required=True,
        help="Dataset family, such as hedm or sem.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/benchmark.csv"),
        help="CSV output path.",
    )
    parser.add_argument("--append", action="store_true", help="Append rows to an existing CSV.")
    parser.add_argument(
        "--preprocessing",
        action="append",
        choices=["none", "median-std", "right-shift-2", "right-shift-4"],
        help=(
            "Run only this preprocessing choice; repeat the option to select more than "
            "one. The four-method default is used when omitted."
        ),
    )
    parser.add_argument(
        "--fixed-threshold",
        type=float,
        help="Add a fixed-value threshold-zeroing run to the selected matrix.",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Also use zstd and lz4 when their packages are installed.",
    )
    return parser


def _selected_preprocessing_specs(names: list[str] | None) -> list[PreprocessingSpec]:
    if names is None:
        return default_preprocessing_specs()

    choices = {
        "none": PreprocessingSpec("none", is_lossless=True),
        "median-std": PreprocessingSpec("median_std_zero", {"k": 2.0}),
        "right-shift-2": PreprocessingSpec("right_shift", {"bits": 2}),
        "right-shift-4": PreprocessingSpec("right_shift", {"bits": 4}),
    }
    return [choices[name] for name in names]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    specs = _selected_preprocessing_specs(args.preprocessing)
    if args.fixed_threshold is not None:
        specs.append(fixed_threshold_spec(args.fixed_threshold))

    try:
        results = benchmark_file(
            args.input,
            dataset_type=args.dataset_type,
            preprocessing_specs=specs,
            include_optional=args.include_optional,
        )
        write_results_csv(args.output, results, append=args.append)
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    failures = sum(not result.reconstruction_correct for result in results)
    print_results_table(results)
    print(
        f"Wrote {len(results)} rows for {args.input} to {args.output}; "
        f"round-trip failures: {failures}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
