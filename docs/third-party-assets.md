# Third-party browser assets

These assets are vendored so the dashboard does not contact third-party script or font CDNs at runtime. Files were retrieved on 2026-10-21. Keep the accompanying licenses when redistributing the application or its portable export.

## Cytoscape.js

- Version: **3.34.4**. Browser UMD bundle exposes `window.cytoscape`; CommonJS exports are also available for validation.
- Local bundle: `src/luma_review/static/vendor/cytoscape.min.js`.
- License: **MIT**, copied unchanged to `src/luma_review/static/vendor/cytoscape-LICENSE.txt`.
- Official project: <https://github.com/cytoscape/cytoscape.js>.
- Package metadata: <https://registry.npmjs.org/cytoscape/3.34.4>.
- Exact download: <https://registry.npmjs.org/cytoscape/-/cytoscape-3.34.4.tgz>.
- Archive members: `package/dist/cytoscape.min.js` and `package/LICENSE`; the JavaScript file was copied without modification.
- Download integrity, verified before extraction: `sha512-msY99tMY8iWTg+sIPGfSqDcPNOt4xcj+v/K/7qUFaCUxxlqnMkUYLBjRUzn9W5CU/R2hrmtJa5+UtovrEM2ctg==`.

The bundle is 435,649 bytes. Its SHA-256 is `081591ab735b2b6a3b31a3c60f8f3a3e2fee8c92939e0c7820ad1208571b6cd8`.

## Fonts

**DM Sans** supplies the normal variable body face for weights **400–700**. **Instrument Serif** supplies the editorial face at weight **400**, normal and italic. Both use the **SIL Open Font License 1.1**. The files are unmodified WOFF2 subsets from Google Fonts, with Latin and Latin Extended coverage. Unsupported writing systems use the application’s system-font fallback.

- Stylesheet: `src/luma_review/static/fonts/fonts.css`.
- DM Sans CSS origin: <https://fonts.googleapis.com/css2?family=DM+Sans:wght@400..700&display=swap>.
- Instrument Serif CSS origin: <https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&display=swap>.
- Google Fonts requests used a modern Chromium user agent to obtain WOFF2 variable-font responses. The stylesheet was preserved with source URLs changed to relative local filenames.
- DM Sans license: `src/luma_review/static/fonts/dmsans-OFL.txt`, from <https://raw.githubusercontent.com/google/fonts/main/ofl/dmsans/OFL.txt>.
- Instrument Serif license: `src/luma_review/static/fonts/instrumentserif-OFL.txt`, from <https://raw.githubusercontent.com/google/fonts/main/ofl/instrumentserif/OFL.txt>.
- Upstream font projects: <https://github.com/googlefonts/dm-fonts> and <https://github.com/Instrument/instrument-serif>.

The stylesheet contains `font-display: swap` and the upstream `unicode-range` declarations. Link it as `/fonts/fonts.css`; relative WOFF2 paths resolve within `/fonts/`.

| Local filename (under `static/fonts/`) | Bytes | Exact Google Fonts origin |
| --- | ---: | --- |
| `dm-sans-normal-latin.woff2` | 36,980 | [WOFF2](https://fonts.gstatic.com/s/dmsans/v17/rP2Yp2ywxg089UriI5-g4vlH9VoD8Cmcqbu0-K6z9mXg.woff2) |
| `dm-sans-normal-latin-ext.woff2` | 18,192 | [WOFF2](https://fonts.gstatic.com/s/dmsans/v17/rP2Yp2ywxg089UriI5-g4vlH9VoD8Cmcqbu6-K6z9mXgjU0.woff2) |
| `instrument-serif-normal-latin.woff2` | 15,040 | [WOFF2](https://fonts.gstatic.com/s/instrumentserif/v5/jizBRFtNs2ka5fXjeivQ4LroWlx-6zUTjnTLgNs.woff2) |
| `instrument-serif-normal-latin-ext.woff2` | 7,828 | [WOFF2](https://fonts.gstatic.com/s/instrumentserif/v5/jizBRFtNs2ka5fXjeivQ4LroWlx-6zsTjnTLgNuZ5w.woff2) |
| `instrument-serif-italic-latin.woff2` | 15,684 | [WOFF2](https://fonts.gstatic.com/s/instrumentserif/v5/jizHRFtNs2ka5fXjeivQ4LroWlx-6zAjjH7Motmp5g.woff2) |
| `instrument-serif-italic-latin-ext.woff2` | 8,444 | [WOFF2](https://fonts.gstatic.com/s/instrumentserif/v5/jizHRFtNs2ka5fXjeivQ4LroWlx-6zAjgn7Motmp5r61.woff2) |

The six font binaries total **102,168 bytes**.

SHA-256 checksums:

```text
468d56b6b25b05b70190b6c233d773f6f1770e8579827ce022a57f03fa8002fb  dm-sans-normal-latin.woff2
219b02c7d8884817d3d6ad4c8771f2c000ce4c5669a67ef4e2e5617ffa25c4cc  dm-sans-normal-latin-ext.woff2
60c06664b5a95c7de6cc3e00d1f9034d78bd1e40b564016b241674449a067d4d  instrument-serif-normal-latin.woff2
a8c4bd7cd7073180e740d2d83a616b5cb0845579b73207eeafeae8532e70c901  instrument-serif-normal-latin-ext.woff2
6ee678c33f388dd7ba59700ebea635deb98821baafd817b09891f7927177f702  instrument-serif-italic-latin.woff2
a04fc7ed18a8037149ce0bfda58076709d8e0840e136ed00abbdc196b7992443  instrument-serif-italic-latin-ext.woff2
```
