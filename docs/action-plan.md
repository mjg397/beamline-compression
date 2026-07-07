# Beamline Compression Action Plan

## Working Thesis

Do the comparison in software first. An FPGA compressor is worth pursuing only
if it beats simpler CPU/GPU/storage options on the same data, with the same
scientific error limits, and with a design that can plausibly stream in real
time.

## Exact Next Steps

1. Collect two dataset families.
   - HEDM: one sparse detector frame stack, preferably the 144-image style
     dataset described in the notes.
   - SEM: one representative image set, ideally raw or minimally processed
     grayscale images rather than compressed screenshots.

2. Standardize the inputs.
   - Store large files under `data/raw/hedm/` and `data/raw/sem/`.
   - Record source, format, shape, dtype, frame count, and notes in
     `docs/dataset-log.csv`.
   - If the HEDM data arrives as HDF5/MAT/TIFF, flatten/export the frames into a
     consistent local format before benchmarking.

3. Profile the raw data before compressing it.
   - Histogram of pixel values.
   - Approximate background level.
   - Fraction of pixels near background.
   - Effective bit depth: highest active bit and noisy low bits.
   - Frame-to-frame similarity for the HEDM rotation stack.

4. Run preprocessing variants.
   - No preprocessing.
   - Zero values below the median/background threshold.
   - Zero values below median plus a noise margin.
   - Drop low-order noisy bits.
   - Preserve only a chosen bit range, such as bits 6 through 22, if justified
     by the data.

5. Benchmark the first-pass compression candidates.
   - Run every candidate against the same preprocessed inputs.
   - Measure compression ratio, compressed size, compression speed,
     decompression speed when available, and error introduced by preprocessing.
   - Keep the candidate matrix updated with citations, results, and a
     1-to-10 promise score.

6. Score FPGA feasibility after software results exist.
   - Streaming friendliness.
   - Required line/frame buffering.
   - Metadata overhead.
   - Expected LUT/BRAM/DSP pressure.
   - Whether the compressor needs global statistics or can work locally.
   - Whether decompression remains simple enough for the downstream workflow.

7. Pick finalists.
   - Keep 2-3 candidates if they produce meaningful compression and look
     hardware-plausible.
   - Defer candidates that compress well but require too much global state,
     memory, or fragile decompression.

## Decision Rule

Promote a candidate toward FPGA work only if all of these are true:

- It improves meaningfully over generic file compression on the same data.
- It can plausibly keep up with detector throughput.
- Its preprocessing loss is scientifically acceptable or it is fully lossless.
- Its metadata overhead does not erase the compression gain.
- The hardware implementation has a clear streaming design.

## First Deliverable

A table with one row per dataset/preprocessing/compressor combination:

- Dataset ID
- Data type
- Shape and dtype
- Preprocessing
- Compressor
- Compression ratio
- Encode speed
- Decode speed
- Error metrics
- FPGA complexity estimate
- Notes/citation

The starter code writes the first version of this as `results/benchmark.csv`.
