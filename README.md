# beamline-compression

Software-first compression study for beamline detector data.

The current goal is to compare compression approaches on representative HEDM
and SEM datasets before choosing anything to implement on an FPGA. The FPGA path
only makes sense if a candidate gives useful compression, can keep up with the
detector data rate, and has a hardware design that is not more complex than the
benefit justifies.

## Immediate Workflow

1. Use the downloaded public HEDM/SEM candidates in
   [docs/dataset-sources.md](docs/dataset-sources.md), and keep asking for one
   project-specific HEDM stack.
2. Record shape, dtype, bit depth, frame count, source, and scientific
   constraints in [docs/dataset-log.csv](docs/dataset-log.csv).
3. Run a raw compression baseline and a threshold/bit-plane preprocessing sweep.
4. Fill in results in
   [docs/compression-candidate-matrix.md](docs/compression-candidate-matrix.md).
5. Promote only the best software candidates into FPGA feasibility work.

The detailed plan is in [docs/action-plan.md](docs/action-plan.md).

## Starter Benchmark

The starter benchmark uses only the Python standard library, so it can run
before optional codecs such as Zstd, LZ4, Bitshuffle, ZFP, or SZ3 are installed.

```bash
PYTHONPATH=src python3 -m beamcomp.benchmark data/raw/hedm --out results/benchmark.csv
```

For flat little-endian integer detector frames, you can test simple
preprocessing:

```bash
PYTHONPATH=src python3 -m beamcomp.benchmark data/raw/hedm \
  --dtype u16le \
  --preprocess zero-below-median \
  --drop-low-bits 2 \
  --out results/benchmark.csv
```

Use `--dtype u32le` for 32-bit integer frames. HDF5/TIFF/MAT loading is the next
step once the real data format is confirmed.
