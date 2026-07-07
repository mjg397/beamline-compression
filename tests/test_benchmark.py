from __future__ import annotations

import sys
import unittest
from array import array
from pathlib import Path

from beamcomp.benchmark import (
    PreprocessOptions,
    apply_preprocess,
    available_compressors,
    parse_keep_bit_range,
    run_benchmarks,
)


def u16le(values: list[int]) -> bytes:
    data = array("H", values)
    if sys.byteorder != "little":
        data.byteswap()
    return data.tobytes()


def from_u16le(data: bytes) -> list[int]:
    values = array("H")
    values.frombytes(data)
    if sys.byteorder != "little":
        values.byteswap()
    return list(values)


class BenchmarkTests(unittest.TestCase):
    def test_zero_below_median(self) -> None:
        data = u16le([1, 2, 100, 200])
        processed, label, notes = apply_preprocess(
            data,
            PreprocessOptions(dtype="u16le", zero_mode="zero-below-median"),
        )

        self.assertEqual(from_u16le(processed), [0, 0, 100, 200])
        self.assertEqual(label, "zero-below-median")
        self.assertIn("zeroed 2/4", notes)

    def test_drop_low_bits(self) -> None:
        data = u16le([15, 16])
        processed, label, _ = apply_preprocess(
            data,
            PreprocessOptions(dtype="u16le", drop_low_bits=2),
        )

        self.assertEqual(from_u16le(processed), [12, 16])
        self.assertEqual(label, "drop-low-bits-2")

    def test_keep_bit_range(self) -> None:
        data = u16le([0b111111])
        processed, label, _ = apply_preprocess(
            data,
            PreprocessOptions(dtype="u16le", keep_bit_range=(1, 3)),
        )

        self.assertEqual(from_u16le(processed), [0b001110])
        self.assertEqual(label, "keep-bits-1-3")

    def test_parse_keep_bit_range(self) -> None:
        self.assertEqual(parse_keep_bit_range("6:22"), (6, 22))

    def test_run_benchmarks_has_raw_and_zlib(self) -> None:
        results = run_benchmarks(
            Path("sample.bin"),
            b"abcabcabc" * 100,
            PreprocessOptions(),
            include_optional=False,
        )
        algorithms = {result.algorithm for result in results}

        self.assertIn("raw", algorithms)
        self.assertIn("zlib-6", algorithms)

    def test_optional_compressors_are_optional(self) -> None:
        compressors = available_compressors(include_optional=True)

        self.assertIn("raw", {name for name, _, _ in compressors})


if __name__ == "__main__":
    unittest.main()
