# Dataset Sources

## Use These First

| Dataset | Use | Local path | Status |
|---|---|---|---|
| BraggNN frames archive | Best public HEDM/full-frame lead | `data/raw/hedm/braggnn/dataset.tar.gz` | Downloaded archive; do not extract casually |
| edgeBragg patches | Quick HEDM sparse-patch benchmark | `data/raw/hedm/edgebragg/s68-73.h5` | Downloaded and inspected |
| Bjurbole SEM | SEM image benchmark | `data/raw/sem/bjurbole/SEM.zip` | Downloaded and ZIP-tested |

## HEDM Notes

BraggNN is the best public lead found so far. Its archive contains:

- `frames-exp4train.hdf5`, listed at about 24 GB when expanded
- `peaks-exp4train-psz11.hdf5`, 77,267 peak records over frame indices 0-1439

The BraggNN README documents the frame HDF5 as a `frames` dataset with shape
`(1440, 2048, 2048)` and dtype `float32`. Keep the archive compressed until we
are ready to spend the disk space.

edgeBragg is smaller and usable immediately, but it is patch-level data:

- `patch`: shape `(20383, 15, 15)`, dtype `float32`
- `peakLoc`: shape `(20383, 2)`, dtype `float32`
- patch zero fraction: about `0.969`

Use edgeBragg first to shake out sparse compression code. Use BraggNN when we
need full-frame behavior and have enough disk to extract the frame HDF5.

## SEM Notes

The Bjurbole SEM archive contains 121 `.tif` images. A sample file reports
`1400 x 1120`, 8 bits/sample, one sample/pixel, uncompressed TIFF with a color
palette. The embedded metadata also mentions a G16 acquisition channel, so
inspect conversion before treating it as pure uint8.

## Still Needed

Ask the advisor or beamline contact for one target-format HEDM dataset from the
actual project. Best formats:

- `.MIDAS.zip`
- `data.h5` / HDF5 raw detector stack
- TIFF or raw binary rotation series

Ask for detector dimensions, dtype/bit depth, frame count, dark/flood/background
frames, and what preprocessing or loss is scientifically acceptable.

Suggested request:

```text
Hi,

For the beamline compression benchmark, could you share one representative raw
far-field HEDM detector stack from the project? A .MIDAS.zip, HDF5 data.h5,
TIFF series, or raw binary frame series is fine.

It would help to also have detector dimensions, dtype/bit depth, number of
frames, dark/flood/background frames if available, and guidance on what
preprocessing or loss would be scientifically acceptable.
```

## Sources

- BraggNN: https://github.com/lzhengchun/BraggNN
- edgeBragg: https://github.com/AdvancedPhotonSource/edgeBragg
- CHESS HEDM tools: https://github.com/daltonshadle/CHESS_hedmTools
- SR-MIDAS format/workflow reference: https://github.com/AdvancedPhotonSource/SR-MIDAS
- Bjurbole SEM: https://zenodo.org/records/6504816
