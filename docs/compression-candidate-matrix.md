# Compression Candidate Matrix

Scores are initial guesses from the meeting notes, not final results. Update
them after each benchmark.

| Priority | Candidate | Best target | Why it is in scope | First implementation | FPGA complexity | Initial promise | Citation/source |
|---:|---|---|---|---|---|---:|---|
| 1 | Threshold plus run-length encoding | Sparse HEDM | The notes suggest most of the HEDM frame can become zero after background removal. Long zero runs should be cheap to represent. | Custom software encoder after median/background zeroing. | Low to medium; streaming if runs are emitted linearly. | 9 | Golomb, "Run-Length Encodings", IEEE Trans. IT, 1966, https://doi.org/10.1109/TIT.1966.1053907 |
| 2 | Sparse coordinate/value encoding with delta-coded positions | Sparse HEDM | Sends only non-background pixels plus enough metadata to place them back. Strong fit if occupancy is very low. | Encode nonzero index deltas plus retained pixel values. | Medium; metadata packing and random sparsity matter. | 9 | Custom candidate; benchmark against general codecs. |
| 3 | Bit-depth trimming / n-bit style packing | HEDM, SEM integer images | Notes say many top bits are unused and low bits may be noise. This can give "free" compression before any entropy coding. | Preserve selected bit range, then compress. | Low if bit range is fixed per frame/block. | 8 | HDF5 n-bit and scale-offset filters: https://docs.hdfgroup.org/hdf5/develop/group___d_c_p_l.html |
| 4 | Bitshuffle plus LZ4 or Zstd | Typed integer arrays | Directly targets unused/redundant bit planes in typed binary data. Very relevant to 16/32-bit detector pixels. | Add optional `bitshuffle` benchmark once dependencies are installed. | Medium; bit transpose plus block compressor. | 8 | Bitshuffle DOI/preprint listed by project: https://github.com/kiyo-masui/bitshuffle |
| 5 | LZ4 | Fast general-purpose lossless baseline | Good speed baseline. If LZ4 is close enough, custom FPGA work may not be worth it. | Add optional `lz4.frame` benchmark. | Medium if implemented, but often better left to CPU. | 7 | LZ4 project and block/frame format docs: https://github.com/lz4/lz4 |
| 6 | Zstandard | Strong general-purpose lossless baseline | Better ratios than LZ4/DEFLATE in many cases, useful as a software ceiling. | Add optional `zstandard` benchmark. | High for FPGA; mostly comparison baseline. | 7 | RFC 8878: https://www.rfc-editor.org/rfc/rfc8878 |
| 7 | DEFLATE/gzip/zlib | Standard file compression baseline | Ubiquitous and already in Python. Useful as the first reproducible baseline. | Included in the starter benchmark as zlib levels 1, 6, and 9. | High-ish for full implementation; compare, do not start here for FPGA. | 5 | RFC 1951: https://www.rfc-editor.org/rfc/rfc1951 |
| 8 | Canonical Huffman coding | Thresholded symbols or residuals | Useful if the symbol distribution after preprocessing is strongly skewed. | Prototype after histograms reveal symbol frequencies. | Medium; hardware-friendly if code tables are bounded. | 6 | Huffman, "A Method for the Construction of Minimum-Redundancy Codes", 1952, https://doi.org/10.1109/JRPROC.1952.273898 |
| 9 | Golomb-Rice / RLGR coding | Zero runs or prediction residuals | Good for geometric-like run lengths or residuals and simpler than adaptive Huffman. | Prototype on zero-run lengths and residual images. | Low to medium; attractive for FPGA if distributions fit. | 7 | Golomb 1966 DOI above; Rice/Plaunt spacecraft image coding, 1971. |
| 10 | JPEG-LS | SEM images, maybe 2D detector frames | Low-complexity lossless/near-lossless image compression; useful for SEM-style images. | Add via a library or command-line tool after SEM format is known. | Medium; explicitly hardware-friendly. | 7 | JPEG-LS overview: https://jpeg.org/jpegls/ |

## Second-Pass Candidates

These are worth reading and possibly testing, but they should not distract from
the first lossless/sparse pass.

| Candidate | Why defer it | Citation/source |
|---|---|---|
| JPEG 2000 / HTJ2K | Strong image codec and FPGA ecosystem, but heavier than JPEG-LS and not the first thing to try for sparse HEDM. | https://jpeg.org/jpeg2000/ |
| ZFP | Strong for correlated multidimensional arrays; may fit SEM or smooth scientific fields better than sparse diffraction spots. | https://github.com/LLNL/zfp |
| SZ3 | Error-bounded scientific compressor; useful if controlled lossy compression is acceptable. | https://github.com/szcompressor/SZ3 |
| Neural compression | Meeting notes flag decompression as a problem. Keep as literature review unless standard methods fail. | Add papers only if it becomes a serious branch. |

## Columns To Add After Benchmarks

- Dataset ID
- Preprocessing variant
- Compression ratio
- Encode MB/s
- Decode MB/s
- Max absolute error
- RMSE or PSNR if lossy
- Metadata bytes per frame
- FPGA resource estimate
- Updated promise score
