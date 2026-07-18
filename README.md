# Beamline Compression Benchmark

This project is a small software comparison tool for beamline detector
compression. It loads one TIFF or NumPy `.npy` array, applies several simple
preprocessing choices, benchmarks lossless compressors, verifies every round
trip, and writes the measurements to CSV. It does not contain RTL or FPGA code.

HEDM frames are often sparse after background removal, so zero-run-length and
sparse coordinate-value encodings are included alongside general-purpose
codecs. SEM images may have different texture and noise statistics, so they
should be measured separately rather than assumed to behave like HEDM data.

The current goal is to compare compression ratio, speed, reconstruction
correctness, and preprocessing error. Those results can later inform which
methods are worth considering for FPGA feasibility.

## Install

Python 3.11 or newer is required.

```bash
python -m pip install -e ".[test]"
```

Optional Zstandard and LZ4 support can be installed with:

```bash
python -m pip install -e ".[codecs]"
```

## Run The Raw HEDM Baseline

The downloaded HEXRD NIST Ruby sample is a detector-native GE frame as
distributed by the HEXRD examples project. The file contains an 8192-byte
container header followed by one `2048 x 2048` little-endian `uint16` frame.
Convert it to NumPy without changing any pixel values:

```powershell
.\.venv\python311\python.exe scripts\convert_ge_to_npy.py --input data\raw\hedm\hexrd_nist_ruby\RUBY_4553.ge --output data\processed\hedm\hexrd_nist_ruby\RUBY_4553_frame_00000.npy
.\.venv\python311\python.exe scripts\run_benchmark.py --input data\processed\hedm\hexrd_nist_ruby\RUBY_4553_frame_00000.npy --dataset-type hedm --output results\hedm_raw_comparison.csv
```

The converter removes only the GE header. Its NumPy pixel payload was verified
byte-for-byte against the source file. The benchmark writes 24 rows and has
been verified with zero reconstruction failures. It also prints a compact
terminal table, so opening the CSV is not required for a quick comparison.

Here, "raw" means detector-native integer counts before software dark
subtraction, thresholding, cropping, normalization, or flipping. Acquisition
metadata would still be needed to rule out corrections performed inside the
detector system itself.

## Run The Preprocessed edgeBragg Patch

The edgeBragg sample is useful for testing sparse encodings, but it is not raw
detector data. It contains cropped, masked, zero-padded, per-patch normalized
`15 x 15` `float32` peak images. Right shifts only apply to integer pixels, so
run the two applicable preprocessing methods:

```powershell
.\.venv\python311\python.exe scripts\run_benchmark.py --input data\processed\hedm\edgebragg\patch_00000.npy --dataset-type hedm --output results\hedm_comparison.csv --preprocessing none --preprocessing median-std
```

## Run A Target HEDM TIFF

Use the full default 24-row matrix when an integer HEDM TIFF is available:

```bash
python scripts/run_benchmark.py --input data/raw/hedm/frame_00001.tif --dataset-type hedm --output results/hedm_comparison.csv
```

`data/raw/hedm/frame_00001.tif` is a placeholder path and is not included in
the downloaded datasets. Replace it with a TIFF that actually exists.

The default matrix produces 24 rows: no preprocessing, median plus `2 * std`
background zeroing, and right shifts of 2 and 4 bits, each paired with raw,
gzip, bz2, lzma, zero-run-length, and sparse coordinate-value storage. Add
`--fixed-threshold VALUE` to include a fixed background threshold, or
`--include-optional` to use installed Zstandard and LZ4 packages.

Right shifting applies only to integer detector pixels. For a floating-point
array, select the applicable methods explicitly:

```bash
python scripts/run_benchmark.py --input frame.npy --dataset-type hedm --output results/hedm_float.csv --preprocessing none --preprocessing median-std
```

Every CSV row records shape, dtype, nonzero density, sizes, ratios, compression
and decompression timing, throughput, reconstruction status, and maximum error
against the original pixels for lossy preprocessing. TIFF loading uses
`tifffile`; NumPy files are loaded with pickling disabled.

Measured HEDM and SEM results are summarized in
[`docs/benchmark-comparison-matrix.md`](docs/benchmark-comparison-matrix.md).

Public dataset notes and download provenance are kept in
[`docs/dataset-sources.md`](docs/dataset-sources.md). A project-specific frame
is still needed to confirm that the public GE sample represents the target
beamline and detector.
