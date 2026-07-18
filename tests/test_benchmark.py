from __future__ import annotations

import csv
from collections import Counter

import numpy as np
import tifffile

from beamcomp.benchmark import (
    CSV_FIELDS,
    benchmark_array,
    benchmark_file,
    main,
    write_results_csv,
)
from beamcomp.compressors import (
    ArrayMetadata,
    get_compressor,
    sparse_decode,
    sparse_encode,
)
from beamcomp.data import load_array
from beamcomp.ge import load_ge_frame
from beamcomp.preprocessing import (
    PreprocessingSpec,
    apply_preprocessing,
    fixed_threshold_spec,
)


def test_load_npy_preserves_array(tmp_path) -> None:
    expected = np.arange(12, dtype=np.uint16).reshape(3, 4)
    path = tmp_path / "frame.npy"
    np.save(path, expected)

    actual = load_array(path)

    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    assert np.array_equal(actual, expected)


def test_load_tiff_preserves_array(tmp_path) -> None:
    expected = np.arange(20, dtype=np.uint16).reshape(4, 5)
    path = tmp_path / "frame.tif"
    tifffile.imwrite(path, expected)

    actual = load_array(path)

    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    assert np.array_equal(actual, expected)


def test_load_ge_frame_only_removes_header(tmp_path) -> None:
    first = np.arange(12, dtype="<u2").reshape(3, 4)
    second = (first + 100).astype("<u2")
    path = tmp_path / "detector.ge"
    path.write_bytes(b"GEHEADER" + first.tobytes() + second.tobytes())

    actual = load_ge_frame(
        path,
        shape=(3, 4),
        header_bytes=8,
        frame_index=1,
    )

    assert actual.shape == second.shape
    assert actual.dtype == second.dtype
    assert actual.tobytes() == second.tobytes()


def test_fixed_threshold_zeroing() -> None:
    source = np.array([0, 2, 5, 9], dtype=np.uint16)

    result = apply_preprocessing(source, fixed_threshold_spec(5))

    assert np.array_equal(result.array, np.array([0, 0, 5, 9], dtype=np.uint16))
    assert result.is_lossless is False


def test_median_std_zeroing() -> None:
    source = np.array([1, 1, 1, 100], dtype=np.uint16)

    result = apply_preprocessing(
        source, PreprocessingSpec("median_std_zero", {"k": 2.0})
    )

    assert np.array_equal(result.array, np.array([0, 0, 0, 100], dtype=np.uint16))
    assert result.parameters["threshold"] > 1


def test_right_shift() -> None:
    source = np.array([15, 16, 255], dtype=np.uint16)

    result = apply_preprocessing(source, PreprocessingSpec("right_shift", {"bits": 2}))

    assert result.array.dtype == source.dtype
    assert np.array_equal(result.array, np.array([3, 4, 63], dtype=np.uint16))


def _assert_roundtrip(name: str, source: np.ndarray) -> None:
    compressor = get_compressor(name)
    payload = compressor.encode(source)
    restored = compressor.decode(payload, ArrayMetadata.from_array(source))
    assert restored.dtype == source.dtype
    assert restored.shape == source.shape
    assert restored.tobytes() == source.tobytes()


def test_gzip_roundtrip() -> None:
    _assert_roundtrip("gzip", np.arange(100, dtype=np.uint16).reshape(10, 10))


def test_zero_run_length_roundtrip() -> None:
    source = np.array([[0, 0, 12, 0], [7, 8, 0, 0]], dtype=np.uint16)
    _assert_roundtrip("zero-run-length", source)


def test_sparse_coordinate_value_roundtrip() -> None:
    source = np.zeros((8, 9), dtype=np.uint32)
    source[1, 2] = 17
    source[7, 8] = 1_000
    _assert_roundtrip("sparse-coordinate-value", source)

    restored_without_external_metadata = sparse_decode(sparse_encode(source))
    assert restored_without_external_metadata.dtype == source.dtype
    assert restored_without_external_metadata.shape == source.shape
    assert restored_without_external_metadata.tobytes() == source.tobytes()


def test_zero_based_codecs_preserve_negative_zero_bits() -> None:
    source = np.array([[0.0, -0.0, 2.5, 0.0]], dtype=np.float32)

    _assert_roundtrip("zero-run-length", source)
    _assert_roundtrip("sparse-coordinate-value", source)


def test_benchmark_writes_a_csv_row(tmp_path) -> None:
    input_path = tmp_path / "frame.npy"
    output_path = tmp_path / "comparison.csv"
    np.save(input_path, np.array([[0, 4], [0, 8]], dtype=np.uint16))

    results = benchmark_file(
        input_path,
        dataset_type="hedm",
        preprocessing_specs=[PreprocessingSpec("none", is_lossless=True)],
        compressors=[get_compressor("raw")],
    )
    write_results_csv(output_path, results)

    with output_path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file)
        rows = list(reader)
    assert reader.fieldnames == CSV_FIELDS
    assert len(rows) == 1
    assert rows[0]["dataset_type"] == "hedm"
    assert rows[0]["compressor_name"] == "raw"
    assert rows[0]["reconstruction_correct"] == "true"
    assert rows[0]["image_shape"] == "[2,2]"


def test_default_integer_matrix_has_24_correct_roundtrips() -> None:
    source = np.zeros((8, 8), dtype=np.uint16)
    source[2, 3] = 100

    results = benchmark_array(
        source,
        input_path="synthetic.npy",
        dataset_type="hedm",
    )

    assert len(results) == 24
    assert all(result.reconstruction_correct for result in results)
    assert Counter(result.compressor_name for result in results) == {
        "raw": 4,
        "gzip": 4,
        "bz2": 4,
        "lzma": 4,
        "zero-run-length": 4,
        "sparse-coordinate-value": 4,
    }
    assert Counter(result.preprocessing_method for result in results) == {
        "none": 6,
        "median_std_zero": 6,
        "right_shift": 12,
    }


def test_lossy_preprocessing_reports_raw_error() -> None:
    source = np.array([0, 3, 7, 15], dtype=np.uint16)

    result = benchmark_array(
        source,
        input_path="synthetic.npy",
        dataset_type="hedm",
        preprocessing_specs=[PreprocessingSpec("right_shift", {"bits": 2})],
        compressors=[get_compressor("raw")],
    )[0]

    assert result.preprocessing_lossless is False
    assert result.reconstruction_correct is True
    assert result.lossless_vs_raw_input is False
    assert result.max_absolute_error_vs_raw == 12.0


def test_lossless_metrics_are_internally_consistent() -> None:
    source = np.array([[0, 2], [0, 4]], dtype=np.uint16)

    result = benchmark_array(
        source,
        input_path="frame.npy",
        dataset_type="hedm",
        preprocessing_specs=[PreprocessingSpec("none", is_lossless=True)],
        compressors=[get_compressor("gzip")],
    )[0]

    assert result.dataset_type == "hedm"
    assert result.input_filename == "frame.npy"
    assert result.image_shape == (2, 2)
    assert result.dtype == source.dtype.str
    assert result.preprocessing_parameters == {}
    assert result.preprocessing_lossless is True
    assert result.lossless_vs_raw_input is True
    assert result.reconstruction_correct is True
    assert result.original_raw_bytes == source.nbytes
    assert result.preprocessed_bytes == source.nbytes
    assert result.compressed_bytes > 0
    assert result.compression_ratio_vs_raw == source.nbytes / result.compressed_bytes
    assert result.compression_ratio_vs_preprocessed == (
        source.nbytes / result.compressed_bytes
    )
    assert result.compression_time_ms >= 0
    assert result.decompression_time_ms >= 0
    assert result.compression_throughput_mb_s >= 0
    assert result.decompression_throughput_mb_s >= 0
    assert result.percent_nonzero_before == 50.0
    assert result.percent_nonzero_after == 50.0
    assert result.max_absolute_error_vs_raw is None
    assert result.notes


def test_cli_runs_one_tiff_and_writes_default_matrix(tmp_path, capsys) -> None:
    input_path = tmp_path / "frame_00001.tif"
    output_path = tmp_path / "hedm_comparison.csv"
    frame = np.zeros((16, 16), dtype=np.uint16)
    frame[3, 4] = 1_000
    tifffile.imwrite(input_path, frame)

    exit_code = main(
        [
            "--input",
            str(input_path),
            "--dataset-type",
            "hedm",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    with output_path.open(newline="", encoding="utf-8") as input_file:
        rows = list(csv.DictReader(input_file))
    assert len(rows) == 24
    assert all(row["reconstruction_correct"] == "true" for row in rows)

    terminal_output = capsys.readouterr().out
    assert "Preprocessing" in terminal_output
    assert "Compressor" in terminal_output
    assert "Enc MB/s" in terminal_output
    assert "gzip" in terminal_output
    assert "shift 2 bits" in terminal_output
    assert "round-trip failures: 0" in terminal_output
