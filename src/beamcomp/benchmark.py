"""Command-line compression benchmark helpers.

This starter intentionally uses the Python standard library first. Optional
codecs can be added once representative HEDM and SEM data are available.
"""

from __future__ import annotations

import argparse
import bz2
import csv
import importlib
import importlib.util
import lzma
import statistics
import sys
import time
import zlib
from array import array
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


INTEGER_DTYPES = {
    "u16le": ("H", 2, 16),
    "u32le": ("I", 4, 32),
}


@dataclass(frozen=True)
class PreprocessOptions:
    dtype: str = "bytes"
    zero_mode: str = "none"
    drop_low_bits: int = 0
    keep_bit_range: tuple[int, int] | None = None


@dataclass(frozen=True)
class BenchmarkResult:
    path: Path
    original_bytes: int
    prepared_bytes: int
    dtype: str
    preprocess: str
    algorithm: str
    compressed_bytes: int
    ratio_vs_original: float
    ratio_vs_prepared: float
    encode_ms: float
    encode_mb_s: float
    notes: str


Compressor = tuple[str, Callable[[bytes], bytes], str]


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def read_int_array(data: bytes, dtype: str) -> tuple[array, int]:
    """Read little-endian unsigned integer data into a native-endian array."""
    if dtype not in INTEGER_DTYPES:
        raise ValueError(f"{dtype!r} is not an integer dtype")

    typecode, item_size, bit_width = INTEGER_DTYPES[dtype]
    values = array(typecode)
    if values.itemsize != item_size:
        raise RuntimeError(f"Python array type {typecode!r} is not {item_size} bytes")
    if len(data) % item_size:
        raise ValueError(f"{dtype} data length must be a multiple of {item_size}")

    values.frombytes(data)
    if sys.byteorder != "little":
        values.byteswap()
    return values, bit_width


def int_array_to_le_bytes(values: array) -> bytes:
    output = array(values.typecode, values)
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


def parse_keep_bit_range(text: str) -> tuple[int, int]:
    try:
        low_text, high_text = text.split(":", maxsplit=1)
        low = int(low_text)
        high = int(high_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bit range must look like LOW:HIGH") from exc

    if low < 0 or high < low:
        raise argparse.ArgumentTypeError("bit range must satisfy 0 <= LOW <= HIGH")
    return low, high


def _sample(values: array, limit: int = 1_000_000) -> array:
    if len(values) <= limit:
        return values
    stride = max(1, len(values) // limit)
    return values[::stride]


def apply_preprocess(data: bytes, options: PreprocessOptions) -> tuple[bytes, str, str]:
    if options.dtype == "bytes":
        if (
            options.zero_mode != "none"
            or options.drop_low_bits
            or options.keep_bit_range is not None
        ):
            raise ValueError("numeric preprocessing requires --dtype u16le or u32le")
        return data, "none", ""

    values, bit_width = read_int_array(data, options.dtype)
    notes: list[str] = []
    labels: list[str] = []

    if options.zero_mode != "none":
        sample = _sample(values)
        median = float(statistics.median(sample))
        threshold = median
        if options.zero_mode == "zero-below-median-plus-2std":
            spread = statistics.pstdev(sample) if len(sample) > 1 else 0.0
            threshold = median + (2.0 * spread)
        elif options.zero_mode != "zero-below-median":
            raise ValueError(f"unknown zero mode: {options.zero_mode}")

        zeroed = 0
        for index, value in enumerate(values):
            if value <= threshold:
                values[index] = 0
                zeroed += 1
        labels.append(options.zero_mode)
        notes.append(f"zeroed {zeroed}/{len(values)} values <= {threshold:.3f}")

    if options.drop_low_bits:
        if options.drop_low_bits >= bit_width:
            raise ValueError("--drop-low-bits must be smaller than the dtype width")
        mask = ((1 << bit_width) - 1) ^ ((1 << options.drop_low_bits) - 1)
        for index, value in enumerate(values):
            values[index] = value & mask
        labels.append(f"drop-low-bits-{options.drop_low_bits}")
        notes.append(f"cleared {options.drop_low_bits} low-order bits")

    if options.keep_bit_range is not None:
        low, high = options.keep_bit_range
        if high >= bit_width:
            raise ValueError(f"bit range high value must be < {bit_width}")
        mask = ((1 << (high - low + 1)) - 1) << low
        for index, value in enumerate(values):
            values[index] = value & mask
        labels.append(f"keep-bits-{low}-{high}")
        notes.append(f"kept bit range {low}:{high}")

    label = "+".join(labels) if labels else "none"
    return int_array_to_le_bytes(values), label, "; ".join(notes)


def standard_compressors() -> list[Compressor]:
    return [
        ("raw", lambda data: data, "uncompressed baseline"),
        ("zlib-1", lambda data: zlib.compress(data, level=1), "DEFLATE level 1"),
        ("zlib-6", lambda data: zlib.compress(data, level=6), "DEFLATE level 6"),
        ("zlib-9", lambda data: zlib.compress(data, level=9), "DEFLATE level 9"),
        ("bz2-1", lambda data: bz2.compress(data, compresslevel=1), "bzip2 level 1"),
        ("bz2-9", lambda data: bz2.compress(data, compresslevel=9), "bzip2 level 9"),
        ("lzma-0", lambda data: lzma.compress(data, preset=0), "LZMA preset 0"),
        ("lzma-6", lambda data: lzma.compress(data, preset=6), "LZMA preset 6"),
    ]


def optional_compressors() -> list[Compressor]:
    compressors: list[Compressor] = []

    if module_available("zstandard"):
        zstd = importlib.import_module("zstandard")
        compressors.append(
            (
                "zstd-3",
                lambda data: zstd.ZstdCompressor(level=3).compress(data),
                "optional zstandard level 3",
            )
        )

    if module_available("lz4.frame"):
        lz4 = importlib.import_module("lz4.frame")
        compressors.append(
            (
                "lz4-frame",
                lambda data: lz4.compress(data),
                "optional LZ4 frame compression",
            )
        )

    return compressors


def available_compressors(include_optional: bool = True) -> list[Compressor]:
    compressors = standard_compressors()
    if include_optional:
        compressors.extend(optional_compressors())
    return compressors


def run_benchmarks(
    path: Path,
    data: bytes,
    options: PreprocessOptions,
    include_optional: bool = True,
) -> list[BenchmarkResult]:
    prepared, preprocess_label, preprocess_notes = apply_preprocess(data, options)
    results: list[BenchmarkResult] = []

    for name, compress, codec_notes in available_compressors(include_optional):
        start_ns = time.perf_counter_ns()
        compressed = compress(prepared)
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

        compressed_size = len(compressed)
        elapsed_s = max(elapsed_ms / 1_000, 1e-12)
        encode_mb_s = (len(prepared) / 1_000_000) / elapsed_s
        ratio_vs_original = len(data) / compressed_size if compressed_size else 0.0
        ratio_vs_prepared = len(prepared) / compressed_size if compressed_size else 0.0
        notes = "; ".join(part for part in (preprocess_notes, codec_notes) if part)

        results.append(
            BenchmarkResult(
                path=path,
                original_bytes=len(data),
                prepared_bytes=len(prepared),
                dtype=options.dtype,
                preprocess=preprocess_label,
                algorithm=name,
                compressed_bytes=compressed_size,
                ratio_vs_original=ratio_vs_original,
                ratio_vs_prepared=ratio_vs_prepared,
                encode_ms=elapsed_ms,
                encode_mb_s=encode_mb_s,
                notes=notes,
            )
        )

    return results


def iter_input_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(child for child in path.rglob("*") if child.is_file())
        else:
            yield path


def write_results(path: Path, results: list[BenchmarkResult], append: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append and path.exists() else "w"
    fieldnames = [
        "path",
        "original_bytes",
        "prepared_bytes",
        "dtype",
        "preprocess",
        "algorithm",
        "compressed_bytes",
        "ratio_vs_original",
        "ratio_vs_prepared",
        "encode_ms",
        "encode_mb_s",
        "notes",
    ]

    with path.open(mode, newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        if mode == "w" or path.stat().st_size == 0:
            writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "path": str(result.path),
                    "original_bytes": result.original_bytes,
                    "prepared_bytes": result.prepared_bytes,
                    "dtype": result.dtype,
                    "preprocess": result.preprocess,
                    "algorithm": result.algorithm,
                    "compressed_bytes": result.compressed_bytes,
                    "ratio_vs_original": f"{result.ratio_vs_original:.6f}",
                    "ratio_vs_prepared": f"{result.ratio_vs_prepared:.6f}",
                    "encode_ms": f"{result.encode_ms:.3f}",
                    "encode_mb_s": f"{result.encode_mb_s:.3f}",
                    "notes": result.notes,
                }
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark compression candidates.")
    parser.add_argument("inputs", nargs="+", type=Path, help="Files or directories to test.")
    parser.add_argument("--out", type=Path, default=Path("results/benchmark.csv"))
    parser.add_argument("--append", action="store_true", help="Append to the output CSV.")
    parser.add_argument(
        "--dtype",
        choices=["bytes", *INTEGER_DTYPES.keys()],
        default="bytes",
        help="Interpret input as raw bytes or little-endian integer pixels.",
    )
    parser.add_argument(
        "--preprocess",
        choices=["none", "zero-below-median", "zero-below-median-plus-2std"],
        default="none",
    )
    parser.add_argument(
        "--drop-low-bits",
        type=int,
        default=0,
        help="Clear N low-order bits before compression.",
    )
    parser.add_argument(
        "--keep-bit-range",
        type=parse_keep_bit_range,
        help="Clear all bits except LOW:HIGH, inclusive.",
    )
    parser.add_argument(
        "--no-optional",
        action="store_true",
        help="Skip optional codecs even if installed.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    options = PreprocessOptions(
        dtype=args.dtype,
        zero_mode=args.preprocess,
        drop_low_bits=args.drop_low_bits,
        keep_bit_range=args.keep_bit_range,
    )

    all_results: list[BenchmarkResult] = []
    for input_path in iter_input_files(args.inputs):
        if not input_path.exists():
            raise FileNotFoundError(input_path)
        data = input_path.read_bytes()
        all_results.extend(
            run_benchmarks(
                input_path,
                data,
                options,
                include_optional=not args.no_optional,
            )
        )

    write_results(args.out, all_results, append=args.append)
    for result in all_results:
        print(
            f"{result.path} {result.algorithm}: "
            f"{result.ratio_vs_original:.2f}x, "
            f"{result.encode_mb_s:.1f} MB/s"
        )
    print(f"Wrote {len(all_results)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
