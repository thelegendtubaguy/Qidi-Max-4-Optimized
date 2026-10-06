# Video-assisted force-scale calibration

## Result

The video and cold raw sensor log give an approximate scale factor of **158–162 counts/gf**. The loaded-point fit restricted to displayed masses below 2000 g gives **158.45 counts/gf**, with R² 0.9959 across 18 paired readings. This is a provisional workshop calibration, not a certified force measurement. The upstream author's 182.96 counts/gf is not appropriate to assume for this printer.

[Transcribed readings and fit results](evidence/scale-calibration-analysis.json) include the source video's filename and SHA-256, not its private local path. The personal video remains outside the repository. Display frames were extracted at explicit seek times, manually read, and paired with the continuously recorded load-cell counts.

The fit uses loaded readings only and estimates an intercept rather than subtracting a distant unloaded reference. Sensor data receive a centered median-three filter for this offline calculation; original readings are retained. A robust linear regression jointly searches an effective video-to-log alignment offset. That offset includes clock and display-update lag; it is not an ADC conversion timestamp.

| Selected readings | Points | Counts/gf | R² |
|---|---:|---:|---:|
| All loaded readings above 100 g | 34 | 159.97 | 0.9930 |
| Loaded readings below 2200 g | 26 | 157.98 | 0.9969 |
| Loaded readings below 2000 g | 18 | 158.45 | 0.9959 |
| Held-load sections, including high loads | 19 | 162.00 | 0.9996 |

The optimum effective alignment offsets are approximately −1.1 s relative to the UTC timestamp in the video filename. Varying the offset from −1.5 to −0.5 s gives approximately 156.5–162.3 counts/gf for the below-2000-g selection. These sensitivity ranges are not formal confidence intervals. Hand-held loading, scale accuracy, display latency, force alignment, and video transcription contribute unquantified uncertainty.

## Safety correction

The video includes displayed loads near 4 kg, above the linked project's reported 2 kg load-cell rating. The operator was not given an explicit numerical ceiling before recording; that was an instruction failure. **Do not repeat those high loads.** Their retained data are diagnostic, not evidence that such loading is safe. Agreement between fits does not establish that the cell is undamaged.

No printer heating, homing, or powered movement was used for acquisition. The logger uses the independently implemented nonzeroing raw path, not `read_origin_data()`. Completion and restoration records are retained separately with the capture. No further physical loading is needed to derive this provisional scale factor.

Acquisition finished with **4500/4500 responses**, no issues, and verified unchanged reference/homing state and handler cleanup. Raw evidence is retained in `evidence/scale-calibration-live.jsonl` and `evidence/scale-calibration-capture.json`. Run `evidence/offline/fit_scale_video.py` with NumPy/SciPy to reproduce all four fits. Reproduction agrees within 0.000001 counts/gf. The temporary logger/include were removed and the original config hash and pre-session runtime PA/motion settings restored. No calibration factor has yet been installed.
