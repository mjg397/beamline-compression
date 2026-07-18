# Dataset Sources

## Use These First

| Dataset | Use | Local path | Status |
|---|---|---|---|
| HEXRD NIST Ruby GE frame | Raw-as-distributed HEDM detector baseline | `data/raw/hedm/hexrd_nist_ruby/RUBY_4553.ge` | Downloaded and pixel bytes verified |
| BraggNN frames archive | Full-frame HEDM lead with unclear preprocessing provenance | `data/raw/hedm/braggnn/dataset.tar.gz` | Downloaded archive; do not extract casually |
| edgeBragg patches | Preprocessed sparse-patch check | `data/raw/hedm/edgebragg/s68-73.h5` | Downloaded; not raw detector data |
| Bjurbole SEM | SEM image benchmark | `data/raw/sem/bjurbole/SEM.zip` | Downloaded and ZIP-tested |

## HEDM Notes

### Raw Detector Baseline

`RUBY_4553.ge` comes from the HEXRD NIST Ruby single-GE example. HEXRD
documents GE images as a raw format with a 2048 by 2048 frame, an 8192-byte
header skip, and little-endian unsigned 2-byte pixels. The local file matches
that layout exactly:

- file size: `8,396,800` bytes
- frame: `2048 x 2048`, `uint16`, `8,388,608` pixel bytes
- file SHA-256: `FDD24DB34BC46579DBA3223419E930231CF92FB722097170F56E11E2901A515A`
- pixel SHA-256: `DDEA9F14D5C70D0C2C85C1DCBC3750A03292669FA9550D3A39E3DF6541B5A95B`
- observed range: 1515 to 16353; median 2144; 100% nonzero

The benchmark-friendly file is
`data/processed/hedm/hexrd_nist_ruby/RUBY_4553_frame_00000.npy`. The converter
strips only the container header, and the resulting array bytes were verified
identical to the GE pixel payload:

```powershell
.\.venv\python311\python.exe scripts\convert_ge_to_npy.py --input data\raw\hedm\hexrd_nist_ruby\RUBY_4553.ge --output data\processed\hedm\hexrd_nist_ruby\RUBY_4553_frame_00000.npy
```

This is the strongest public raw baseline currently in the project: the
detector counts have not been dark-subtracted, thresholded, cropped,
normalized, or flipped by the converter. "Raw" here means raw as distributed
and before HEXRD software corrections. Without the acquisition record, it is
not possible to prove that the detector system applied no internal correction.

### Other HEDM Data

The BraggNN archive contains:

- `frames-exp4train.hdf5`, listed at about 24 GB when expanded
- `peaks-exp4train-psz11.hdf5`, 77,267 peak records over frame indices 0-1439

The BraggNN README documents the frame HDF5 as a `frames` dataset with shape
`(1440, 2048, 2048)` and dtype `float32`. Keep the archive compressed until we
are ready to spend the disk space. Its `float32` representation and incomplete
processing history mean it should not be labeled completely raw yet.

edgeBragg is heavily preprocessed patch-level data:

- `patch`: shape `(20383, 15, 15)`, dtype `float32`
- `peakLoc`: shape `(20383, 2)`, dtype `float32`
- patch zero fraction: about `0.969`
- all 20,383 local patches have a maximum value of exactly `1.0`

The upstream pipeline thresholds full frames for connected components, crops
peak regions, masks pixels belonging to other components, pads with zeros, and
feeds min-max-normalized patches to BraggNN. It is useful for checking sparse
compression mechanics, but its ratios must not be presented as raw detector
compression results.

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

- HEXRD NIST Ruby example: https://github.com/HEXRD/examples/tree/master/NIST_ruby/single_GE
- HEXRD ImageSeries raw format documentation: https://hexrd.readthedocs.io/en/0.9.7/dev/imageseries-overview.html
- BraggNN: https://github.com/lzhengchun/BraggNN
- edgeBragg: https://github.com/AdvancedPhotonSource/edgeBragg
- CHESS HEDM tools: https://github.com/daltonshadle/CHESS_hedmTools
- SR-MIDAS format/workflow reference: https://github.com/AdvancedPhotonSource/SR-MIDAS
- Bjurbole SEM: https://zenodo.org/records/6504816
