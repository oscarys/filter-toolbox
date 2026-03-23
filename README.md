# Analog Filter Design Toolbox

![CI](https://github.com/<org>/filter-toolbox/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

> **Advanced Instrumentation I — Class Lab Project**  
> Universidad Iberoamericana · Campus Ciudad de México · 2026

A PyQt6 desktop application for the design, synthesis, and SPICE simulation
of analog active filters. The GUI scaffold and all callbacks are provided;
students implement the signal-processing and circuit-synthesis back-end.

---

## Features

| Area | Detail |
|---|---|
| **Approximations** | Butterworth · Chebyshev I · Chebyshev II · Elliptic (Cauer) |
| **Filter types** | Low-pass · High-pass · Band-pass · Band-stop (Notch) |
| **Topologies** | Sallen-Key · Tow-Thomas (UAF42) · Deliyannis-Friend |
| **Component rounding** | E6 / E12 / E24 / E48 / E96 / Exact |
| **Plots** | Magnitude · Phase · Group Delay · Pole-Zero Map · Schematic |
| **Simulation** | PySpice / ngspice AC analysis with IC model selection |
| **Theme** | Light and Dark mode, toggled at runtime |
| **i18n** | English / Español (easily extensible) |

---

## Project layout

```
filter-toolbox/
├── main.py                  # Entry point
├── mainwindow.py            # GUI controller  ← do NOT modify
├── mainwindow.ui            # Qt Designer layout
├── about_dialog.ui          # About box (edit names here)
├── filter_design.py         # ★ STUDENT CODE ★
├── requirements.txt
├── CONTRIBUTING.md
├── LICENSE
└── resources/
    ├── __init__.py
    ├── i18n.py              # All UI strings (EN + ES)
    └── styles.py            # Light / Dark QSS themes
```

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/<org>/filter-toolbox.git
cd filter-toolbox

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install ngspice  (required for SPICE simulation)
#    Ubuntu/Debian : sudo apt install ngspice
#    macOS         : brew install ngspice
#    Windows       : https://ngspice.sourceforge.io/download.html

# 5. Launch
python main.py
```

> **Python 3.10 or newer** is required.

---

## Student entry points

All student work goes in **`filter_design.py`**. Each function has a full
docstring with the expected signature, return type, and implementation hints.

| # | Function | Description |
|---|---|---|
| 1 | `compute_minimum_order(spec)` | Minimum filter order from the spec |
| 2 | `compute_transfer_function(spec)` | Full H(s) + computed order |
| 3 | `factored_biquads(tf)` | Cascade of 1st / 2nd-order sections |
| 4 | `compute_frequency_response(tf, …)` | Magnitude, phase, group delay |
| 5 | `synthesise_sallen_key(…)` | R/C values for Sallen-Key topology |
| 6 | `synthesise_tow_thomas(…)` | R/C values for Tow-Thomas / UAF42 |
| 7 | `synthesise_deliyannis(…)` | R/C values for Deliyannis-Friend |
| 8 | `generate_spice_netlist(…)` | SPICE netlist string |
| 9 | `run_spice_simulation(netlist)` | PySpice AC simulation |

Helper utilities already implemented (do not modify):

- `round_to_eseries(value, series)` — snap to nearest E-series value
- `eseries_error_pct(ideal, rounded)` — percentage rounding error
- `FilterSpec.ripple_eps` — ε derived from Ap automatically
- `FilterSpec.omega_p/s/p2/s2` — rad/s conversion from Hz fields

---

## Editing names in the About box

Open `about_dialog.ui` in Qt Designer and edit the label text directly — no
Python changes needed.

| Widget | Content |
|---|---|
| `lblInstructor1/2/3` | Instructor names |
| `lblStudent1/2/3` | Student names and roles |
| `lblCourse` | Course name |
| `lblInstitution` | Institution |
| `lblYear` | Academic year |

---

## Editing the GUI

Open `mainwindow.ui` in Qt Designer. The following widget **names must not
be changed** (they are referenced by `mainwindow.py`):

`cbApproximation` · `cbFilterType` · `sbFp` · `sbFs` · `sbFp2` · `sbFs2`
`sbAp` · `sbAs` · `cbImplementation` · `cbIcModel`
`cbRSeries` · `cbCSeries` · `sbRBase` · `sbCBase`
`btnDesign` · `btnSimulate` · `btnExportNetlist` · `btnExportReport` · `btnToggleTheme`
`tabPlots` · `wgtMagnitudePlot` · `wgtPhasePlot` · `wgtGroupDelayPlot` · `wgtPoleZeroPlot`
`tblComponents` · `lblStatus` · `lblTitle` · `lblSchematic`
`lblComputedOrder` · `lblFp` · `lblFs` · `lblFp2` · `lblFs2`
`lblAp` · `lblAs` · `lblOrderLabel` · `lblImpl` · `lblIcModel`
`lblRSeries` · `lblCSeries` · `lblRBase` · `lblCBase` · `leftPanel`

---

## Adding a language

1. Open `resources/i18n.py`
2. Copy the `"es"` block and give it a new key (e.g. `"fr"`)
3. Translate all values
4. Add `"Français": "fr"` to the `LANGUAGES` dict at the top

The new language appears automatically in **View → Language**.

---

## Adding a SPICE op-amp model

Place the `.lib` subcircuit file in `resources/spice_models/` and reference
it in `generate_spice_netlist()` with a `.lib` directive.

Free model sources:
- **TI** — https://www.ti.com/design-resources/design-tools-simulation/spice-models.html
- **Analog Devices** — https://www.analog.com/en/design-center/simulation-models/spice-models.html

---

## Dependencies

| Package | Purpose |
|---|---|
| `PyQt6 >= 6.6` | GUI framework |
| `pyqtgraph >= 0.13` | Embedded plots |
| `numpy >= 1.26` | Numerical arrays |
| `scipy >= 1.12` | Filter design (student use) |
| `PySpice >= 1.5` | SPICE netlist + simulation |
| `ngspice` *(system)* | SPICE simulator backend |

---

## CI

GitHub Actions runs on every push to `main` / `develop` and on all PRs:

- **pyflakes** syntax check on all `.py` files
- **i18n completeness** — warns if any language is missing keys
- **XML validation** of all `.ui` files

---

## License

[MIT](LICENSE) © 2026 Universidad Iberoamericana
