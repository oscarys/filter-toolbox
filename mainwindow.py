"""
filter_toolbox/mainwindow.py
============================
PyQt6 main window controller.

Loads the Designer .ui file, wires all signals/slots, manages plots
(pyqtgraph), and calls the student-implemented filter_design.py functions.

Students do NOT need to modify this file.  All computation entry-points are
in filter_design.py.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import numpy as np
import pyqtgraph as pg

from PyQt6 import uic
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QTableWidgetItem, QFileDialog,
    QMessageBox, QHeaderView, QMenu,
)

# ── backend ───────────────────────────────────────────────────────────────────
import filter_design as fd
from filter_design import (
    FilterSpec, Approximation, FilterType, Topology, ESeries,
    TransferFunction, ComponentValue, SimulationResult,
)

# ── themes & i18n ─────────────────────────────────────────────────────────────
from resources.styles import LIGHT_QSS, DARK_QSS
from resources.i18n import LANGUAGES, tr

UI_FILE    = Path(__file__).parent / "mainwindow.ui"
ABOUT_FILE = Path(__file__).parent / "about_dialog.ui"


# ──────────────────────────────────────────────────────────────────────────────
# Worker thread for SPICE simulation
# ──────────────────────────────────────────────────────────────────────────────

class SimWorker(QObject):
    finished = pyqtSignal(SimulationResult)
    error    = pyqtSignal(str)

    def __init__(self, netlist: str):
        super().__init__()
        self._netlist = netlist

    def run(self) -> None:
        try:
            self.finished.emit(fd.run_spice_simulation(self._netlist))
        except NotImplementedError:
            self.error.emit("run_spice_simulation() is not yet implemented.")
        except Exception:
            self.error.emit(f"Simulation error:\n{traceback.format_exc()}")


# ──────────────────────────────────────────────────────────────────────────────
# Main Window
# ──────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        uic.loadUi(UI_FILE, self)

        self._dark_mode : bool = True
        self._lang      : str  = "en"
        self._tf        : TransferFunction | None = None
        self._biquads   : list[TransferFunction]  = []
        self._f_start   : float = 1.0
        self._f_stop    : float = 1e6
        self._components: list[ComponentValue]    = []
        self._sim_result: SimulationResult | None = None
        self._sim_thread: QThread | None          = None

        self._setup_menu_bar()
        self._setup_plots()
        self._setup_plot_widgets()
        self._connect_signals()
        self._apply_theme()
        self._retranslate()
        self._update_spec_fields()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _(self, key: str, **kwargs) -> str:
        return tr(key, self._lang, **kwargs)

    # ── Menu bar ──────────────────────────────────────────────────────────────

    def _setup_menu_bar(self) -> None:
        mb = self.menuBar()
        mb.setNativeMenuBar(False)

        self._mFile = mb.addMenu("")
        self.actionNew           = QAction("", self)
        self.actionOpen          = QAction("", self)
        self.actionSave          = QAction("", self)
        self.actionExportNetlist = QAction("", self)
        self.actionExportReport  = QAction("", self)
        self.actionQuit          = QAction("", self)
        self.actionQuit.setShortcut("Ctrl+Q")
        self._mFile.addAction(self.actionNew)
        self._mFile.addAction(self.actionOpen)
        self._mFile.addAction(self.actionSave)
        self._mFile.addSeparator()
        self._mFile.addAction(self.actionExportNetlist)
        self._mFile.addAction(self.actionExportReport)
        self._mFile.addSeparator()
        self._mFile.addAction(self.actionQuit)

        self._mView = mb.addMenu("")
        self.actionToggleTheme     = QAction("", self)
        self.actionToggleLeftPanel = QAction("", self)
        self._mView.addAction(self.actionToggleTheme)
        self._mView.addAction(self.actionToggleLeftPanel)

        # Language submenu with radio-style checkmarks
        self._mLang = QMenu("", self)
        self._mView.addSeparator()
        self._mView.addMenu(self._mLang)
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        self._lang_actions: dict[str, QAction] = {}
        for display_name, code in LANGUAGES.items():
            act = QAction(display_name, self, checkable=True)
            act.setChecked(code == self._lang)
            act.setData(code)
            act.triggered.connect(self._on_language_changed)
            lang_group.addAction(act)
            self._mLang.addAction(act)
            self._lang_actions[code] = act

        self._mHelp = mb.addMenu("")
        self.actionAbout = QAction("", self)
        self._mHelp.addAction(self.actionAbout)

    # ── Plot setup ────────────────────────────────────────────────────────────

    def _setup_plots(self) -> None:
        self._plot_mag   = pg.PlotWidget()
        self._plot_phase = pg.PlotWidget()
        self._plot_gd    = pg.PlotWidget()
        self._plot_pz    = pg.PlotWidget()

        for pw in (self._plot_mag, self._plot_phase, self._plot_gd, self._plot_pz):
            pw.setBackground(None)
            pw.showGrid(x=True, y=True, alpha=0.3)

        self._plot_mag.setLogMode(x=True, y=False)
        self._plot_phase.setLogMode(x=True, y=False)
        self._plot_gd.setLogMode(x=True, y=False)
        self._plot_pz.setAspectLocked(True)

    def _setup_plot_widgets(self) -> None:
        def _replace(placeholder, new_widget):
            layout = placeholder.parentWidget().layout()
            idx = layout.indexOf(placeholder)
            layout.removeWidget(placeholder)
            placeholder.setParent(None)
            layout.insertWidget(idx, new_widget)

        _replace(self.wgtMagnitudePlot,  self._plot_mag)
        _replace(self.wgtPhasePlot,      self._plot_phase)
        _replace(self.wgtGroupDelayPlot, self._plot_gd)
        _replace(self.wgtPoleZeroPlot,   self._plot_pz)

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.btnDesign.clicked.connect(self._on_design)
        self.btnSimulate.clicked.connect(self._on_simulate)
        self.btnExportNetlist.clicked.connect(self._on_export_netlist)
        self.btnExportReport.clicked.connect(self._on_export_report)
        self.btnResetZoom.clicked.connect(self._on_reset_zoom)
        self.btnToggleTheme.clicked.connect(self._on_toggle_theme)

        self.actionNew.triggered.connect(self._on_new)
        self.actionOpen.triggered.connect(self._on_open)
        self.actionSave.triggered.connect(self._on_save)
        self.actionExportNetlist.triggered.connect(self._on_export_netlist)
        self.actionExportReport.triggered.connect(self._on_export_report)
        self.actionQuit.triggered.connect(self.close)
        self.actionToggleTheme.triggered.connect(self._on_toggle_theme)
        self.actionToggleLeftPanel.triggered.connect(self._on_toggle_left_panel)
        self.actionAbout.triggered.connect(self._on_about)

        self.cbFilterType.currentIndexChanged.connect(self._update_spec_fields)
        self.cbApproximation.currentIndexChanged.connect(self._update_spec_fields)
        self.chkShowSOS.stateChanged.connect(self._on_sos_toggled)

    # ── i18n ─────────────────────────────────────────────────────────────────

    def _retranslate(self) -> None:
        t = self._

        self.setWindowTitle(t("window_title"))
        self.lblTitle.setText(t("app_title"))

        self._mFile.setTitle(t("menu_file"))
        self._mView.setTitle(t("menu_view"))
        self._mHelp.setTitle(t("menu_help"))
        self._mLang.setTitle(t("action_language"))
        self.actionNew.setText(t("action_new"))
        self.actionOpen.setText(t("action_open"))
        self.actionSave.setText(t("action_save"))
        self.actionExportNetlist.setText(t("action_export_netlist"))
        self.actionExportReport.setText(t("action_export_report"))
        self.actionQuit.setText(t("action_quit"))
        self.actionToggleTheme.setText(t("action_toggle_theme"))
        self.actionToggleLeftPanel.setText(t("action_toggle_panel"))
        self.actionAbout.setText(t("action_about"))

        self.btnDesign.setText(t("btn_design"))
        self.btnSimulate.setText(t("btn_simulate"))
        self.btnExportNetlist.setText(t("btn_export_netlist"))
        self.btnExportReport.setText(t("btn_export_report"))
        self.btnResetZoom.setText(t("btn_reset_zoom"))
        self.btnToggleTheme.setText(t("btn_theme"))
        self.chkShowSOS.setText(t("chk_show_sos"))

        self.gbApprox.setTitle(t("gb_approx"))
        self.gbSpecs.setTitle(t("gb_specs"))
        self.gbImpl.setTitle(t("gb_impl"))
        self.gbPassive.setTitle(t("gb_passive"))
        self.gbComponents.setTitle(t("gb_components"))

        self.lblApprox.setText(t("lbl_approx"))
        self.lblType.setText(t("lbl_type"))

        self.cbApproximation.setItemText(0, t("approx_butterworth"))
        self.cbApproximation.setItemText(1, t("approx_cheby1"))
        self.cbApproximation.setItemText(2, t("approx_cheby2"))
        self.cbApproximation.setItemText(3, t("approx_elliptic"))

        self.cbFilterType.setItemText(0, t("type_lp"))
        self.cbFilterType.setItemText(1, t("type_hp"))
        self.cbFilterType.setItemText(2, t("type_bp"))
        self.cbFilterType.setItemText(3, t("type_bs"))

        self.lblAp.setText(t("lbl_ap"))
        self.lblAs.setText(t("lbl_as"))
        self.lblOrderLabel.setText(t("lbl_order"))

        self.lblImpl.setText(t("lbl_topology"))
        self.lblIcModel.setText(t("lbl_ic_model"))
        self.cbImplementation.setItemText(0, t("topo_sk"))
        self.cbImplementation.setItemText(1, t("topo_tt"))
        self.cbImplementation.setItemText(2, t("topo_del"))

        self.lblRSeries.setText(t("lbl_r_series"))
        self.lblCSeries.setText(t("lbl_c_series"))
        self.lblRBase.setText(t("lbl_r_base"))
        self.lblCBase.setText(t("lbl_c_base"))

        self.tblComponents.setHorizontalHeaderLabels([
            t("tbl_stage"), t("tbl_component"),
            t("tbl_ideal"), t("tbl_rounded"), t("tbl_error"),
        ])

        self._plot_mag.setTitle(t("plot_mag_title"))
        self._plot_mag.setLabel("bottom", t("plot_mag_x"), units="Hz")
        self._plot_mag.setLabel("left",   t("plot_mag_y"), units="dB")
        self._plot_phase.setTitle(t("plot_phase_title"))
        self._plot_phase.setLabel("bottom", t("plot_mag_x"), units="Hz")
        self._plot_phase.setLabel("left",   t("plot_phase_y"), units="°")
        self._plot_gd.setTitle(t("plot_gd_title"))
        self._plot_gd.setLabel("bottom", t("plot_mag_x"), units="Hz")
        self._plot_gd.setLabel("left",   t("plot_gd_y"), units="s")
        self._plot_pz.setTitle(t("plot_pz_title"))
        self._plot_pz.setLabel("bottom", t("plot_pz_x"))
        self._plot_pz.setLabel("left",   t("plot_pz_y"))

        self.tabPlots.setTabText(0, t("tab_magnitude"))
        self.tabPlots.setTabText(1, t("tab_phase"))
        self.tabPlots.setTabText(2, t("tab_group_delay"))
        self.tabPlots.setTabText(3, t("tab_pole_zero"))
        self.tabPlots.setTabText(4, t("tab_schematic"))
        self.lblSchematic.setText(t("schematic_placeholder"))

        self._update_spec_fields()

    def _on_language_changed(self) -> None:
        action = self.sender()
        if action:
            self._lang = action.data()
            self._retranslate()

    # ── Dynamic fields ────────────────────────────────────────────────────────

    def _update_spec_fields(self) -> None:
        ft = FilterType(self.cbFilterType.currentIndex())
        is_two_band = ft in (FilterType.BANDPASS, FilterType.BANDSTOP)

        for w in (self.sbFp2, self.sbFs2, self.lblFp2, self.lblFs2):
            w.setEnabled(is_two_band)
            w.setVisible(is_two_band)

        if is_two_band:
            self.lblFp.setText(self._("lbl_fp_lower"))
            self.lblFs.setText(self._("lbl_fs_lower"))
            self.lblFp2.setText(self._("lbl_fp2"))
            self.lblFs2.setText(self._("lbl_fs2"))
        else:
            self.lblFp.setText(self._("lbl_fp"))
            self.lblFs.setText(self._("lbl_fs"))

        self.lblComputedOrder.setText("—")

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(
            DARK_QSS if self._dark_mode else LIGHT_QSS)
        bg = "#161926" if self._dark_mode else "#ffffff"
        fg = "#d8dde8" if self._dark_mode else "#1e2230"
        for pw in (self._plot_mag, self._plot_phase, self._plot_gd, self._plot_pz):
            pw.setBackground(bg)
            pw.getAxis("bottom").setPen(fg)
            pw.getAxis("left").setPen(fg)

    def _on_toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self._apply_theme()

    # ── Read spec ─────────────────────────────────────────────────────────────

    def _read_spec(self) -> FilterSpec:
        return FilterSpec(
            approximation = Approximation(self.cbApproximation.currentIndex()),
            filter_type   = FilterType(self.cbFilterType.currentIndex()),
            fp  = self.sbFp.value(),  fs  = self.sbFs.value(),
            fp2 = self.sbFp2.value(), fs2 = self.sbFs2.value(),
            a_p = self.sbAp.value(),  a_s = self.sbAs.value(),
        )

    def _read_eseries(self, combo) -> ESeries:
        return {0: ESeries.E6, 1: ESeries.E12, 2: ESeries.E24,
                3: ESeries.E48, 4: ESeries.E96, 5: ESeries.EXACT
                }.get(combo.currentIndex(), ESeries.E24)

    # ── Design ────────────────────────────────────────────────────────────────

    def _on_design(self) -> None:
        spec = self._read_spec()
        self.lblStatus.setText(self._("status_computing"))
        QApplication.processEvents()
        try:
            self._tf, computed_order = fd.compute_transfer_function(spec)
            self.lblComputedOrder.setText(str(computed_order))

            # ── Frequency range: always bracket the actual spec edges ──────
            ft = fd.FilterType(self.cbFilterType.currentIndex())
            if ft in (fd.FilterType.BANDPASS, fd.FilterType.BANDSTOP):
                # For two-band types use the outer edges
                f_lo = min(spec.fp, spec.fs, spec.fp2, spec.fs2)
                f_hi = max(spec.fp, spec.fs, spec.fp2, spec.fs2)
            else:
                f_lo = min(spec.fp, spec.fs)
                f_hi = max(spec.fp, spec.fs)
            # Sweep one decade below the lower edge and one above the upper
            f_start = f_lo / 10.0
            f_stop  = f_hi * 10.0

            freqs, mag_db, phase_deg, gd = fd.compute_frequency_response(
                self._tf, f_start=f_start, f_stop=f_stop)
            self._plot_theoretical(freqs, mag_db, phase_deg, gd)

            # ── SOS stage overlays (if checkbox is on) ────────────────────
            self._biquads = fd.factored_biquads(self._tf)
            self._f_start = f_start
            self._f_stop  = f_stop
            if self.chkShowSOS.isChecked():
                self._plot_sos_responses(self._biquads, f_start, f_stop)

            self.tabPlots.setCurrentIndex(0)
            self._plot_pole_zero(self._tf)

            topology = Topology(self.cbImplementation.currentIndex())
            self._components = {
                Topology.SALLEN_KEY: fd.synthesise_sallen_key,
                Topology.TOW_THOMAS: fd.synthesise_tow_thomas,
                Topology.DELIYANNIS: fd.synthesise_deliyannis,
            }[topology](self._biquads, self.sbRBase.value(), self.sbCBase.value(),
                        self._read_eseries(self.cbRSeries),
                        self._read_eseries(self.cbCSeries))
            self._populate_component_table(self._components)

            self.lblStatus.setText(self._("status_design_done",
                order=computed_order,
                approx=self.cbApproximation.currentText(),
                ftype=self.cbFilterType.currentText(),
                fp=spec.fp, fs=spec.fs))

        except NotImplementedError as nie:
            self._show_not_implemented(str(nie))
        except Exception:
            self._show_error("Design", traceback.format_exc())

    # ── Simulate ──────────────────────────────────────────────────────────────

    def _on_simulate(self) -> None:
        if not self._components:
            QMessageBox.information(self,
                self._("dlg_no_design_title"), self._("dlg_no_design_msg"))
            return
        try:
            netlist = fd.generate_spice_netlist(
                self._components,
                Topology(self.cbImplementation.currentIndex()),
                self.cbIcModel.currentText())
        except NotImplementedError as nie:
            self._show_not_implemented(str(nie)); return

        self.lblStatus.setText(self._("status_simulating"))
        self.btnSimulate.setEnabled(False)
        QApplication.processEvents()

        self._sim_thread = QThread()
        worker = SimWorker(netlist)
        worker.moveToThread(self._sim_thread)
        self._sim_thread.started.connect(worker.run)
        worker.finished.connect(self._on_simulation_done)
        worker.error.connect(self._on_simulation_error)
        worker.finished.connect(self._sim_thread.quit)
        worker.error.connect(self._sim_thread.quit)
        self._sim_thread.start()

    def _on_simulation_done(self, result: SimulationResult) -> None:
        self._sim_result = result
        self.btnSimulate.setEnabled(True)
        self._plot_simulated(result)
        self.lblStatus.setText(self._("status_sim_done"))

    def _on_simulation_error(self, msg: str) -> None:
        self.btnSimulate.setEnabled(True)
        if "not yet implemented" in msg:
            self._show_not_implemented(msg)
        else:
            self._show_error("Simulation error", msg)

    # ── Plots ─────────────────────────────────────────────────────────────────

    _THEORY_PEN = pg.mkPen("#4d94ff", width=2.5)
    _SPICE_PEN  = pg.mkPen("#ff5722", width=2.0, style=Qt.PenStyle.DashLine)
    _POLE_BRUSH = pg.mkBrush("#ff4444")
    _ZERO_BRUSH = pg.mkBrush("#44aaff")

    def _plot_theoretical(self, freqs, mag, phase, gd) -> None:
        for pw in (self._plot_mag, self._plot_phase, self._plot_gd):
            pw.clear()
        for level, color in ((-3, "#ffaa00"), (-20, "#888888"), (-40, "#555555")):
            self._plot_mag.addItem(pg.InfiniteLine(
                pos=level, angle=0,
                pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine),
                label=f"{level} dB", labelOpts={"color": color, "position": 0.02}))
        name = self._("legend_theoretical")
        self._plot_mag.plot(freqs, mag,   pen=self._THEORY_PEN, name=name)
        self._plot_phase.plot(freqs, phase, pen=self._THEORY_PEN, name=name)
        self._plot_gd.plot(freqs, gd,     pen=self._THEORY_PEN, name=name)
        for pw in (self._plot_mag, self._plot_phase, self._plot_gd):
            if not pw.plotItem.legend:
                pw.addLegend()

    def _plot_sos_responses(
        self,
        biquads: list[TransferFunction],
        f_start: float,
        f_stop: float,
    ) -> None:
        """Overlay individual SOS stage responses as thin dashed lines."""
        # Distinct muted colours, one per stage, cycling if order > 8
        palette = [
            "#a0c4ff", "#b9fbc0", "#ffd6a5", "#ffadad",
            "#caffbf", "#fdffb6", "#c77dff", "#f4acb7",
        ]
        for i, bq in enumerate(biquads):
            try:
                freqs, mag, _, _ = fd.compute_frequency_response(
                    bq, f_start=f_start, f_stop=f_stop)
                color = pg.mkColor(palette[i % len(palette)])
                color.setAlpha(180)   # ~70% opacity
                pen = pg.mkPen(color, width=1.2)
                self._plot_mag.plot(freqs, mag, pen=pen,
                                    name=f"SOS {i + 1}")
            except Exception:
                pass   # skip silently if a biquad isn't ready yet

    def _on_sos_toggled(self) -> None:
        """Re-draw the magnitude plot when the SOS checkbox changes."""
        if not self._tf:
            return
        # Re-plot theoretical (clears previous SOS lines too)
        try:
            freqs, mag_db, phase_deg, gd = fd.compute_frequency_response(
                self._tf, f_start=self._f_start, f_stop=self._f_stop)
            self._plot_theoretical(freqs, mag_db, phase_deg, gd)
            if self.chkShowSOS.isChecked() and self._biquads:
                self._plot_sos_responses(
                    self._biquads, self._f_start, self._f_stop)
            # Re-overlay SPICE if available
            if self._sim_result:
                self._plot_simulated(self._sim_result)
        except Exception:
            pass

    def _plot_simulated(self, result: SimulationResult) -> None:
        name = self._("legend_spice")
        self._plot_mag.plot(result.frequencies, result.magnitude_db,
                            pen=self._SPICE_PEN, name=name)
        self._plot_phase.plot(result.frequencies, result.phase_deg,
                              pen=self._SPICE_PEN, name=name)

    def _plot_pole_zero(self, tf: TransferFunction) -> None:
        self._plot_pz.clear()
        if tf.poles.size:
            self._plot_pz.plot(tf.poles.real, tf.poles.imag, pen=None,
                               symbol="x", symbolBrush=self._POLE_BRUSH,
                               symbolSize=12, name="Poles")
        if tf.zeros.size:
            self._plot_pz.plot(tf.zeros.real, tf.zeros.imag, pen=None,
                               symbol="o", symbolBrush=self._ZERO_BRUSH,
                               symbolSize=10, name="Zeros")
        self._plot_pz.addLine(x=0, pen=pg.mkPen("#888888", width=1))
        self._plot_pz.addLine(y=0, pen=pg.mkPen("#888888", width=1))

    # ── Component table ───────────────────────────────────────────────────────

    def _populate_component_table(self, components: list[ComponentValue]) -> None:
        tbl = self.tblComponents
        tbl.setRowCount(len(components))
        for row, c in enumerate(components):
            tbl.setItem(row, 0, QTableWidgetItem(str(c.stage)))
            tbl.setItem(row, 1, QTableWidgetItem(c.name))
            tbl.setItem(row, 2, QTableWidgetItem(f"{c.ideal:.6g}"))
            tbl.setItem(row, 3, QTableWidgetItem(f"{c.rounded:.6g}"))
            err_item = QTableWidgetItem(f"{c.error_pct:+.2f}")
            if abs(c.error_pct) > 5.0:
                err_item.setForeground(pg.mkColor("#ff6b6b"))
            tbl.setItem(row, 4, err_item)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export_netlist(self) -> None:
        if not self._components:
            QMessageBox.information(self,
                self._("dlg_no_design_title"), self._("dlg_no_design_msg"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self._("dlg_netlist_title"), "filter.cir",
            self._("dlg_netlist_filter"))
        if not path:
            return
        try:
            netlist = fd.generate_spice_netlist(
                self._components,
                Topology(self.cbImplementation.currentIndex()),
                self.cbIcModel.currentText())
            Path(path).write_text(netlist)
            self.lblStatus.setText(self._("status_netlist_saved", path=path))
        except NotImplementedError as nie:
            self._show_not_implemented(str(nie))
        except Exception:
            self._show_error("Export", traceback.format_exc())

    def _on_export_report(self) -> None:
        QMessageBox.information(self,
            self._("dlg_report_title"), self._("dlg_report_msg"))

    # ── File menu ─────────────────────────────────────────────────────────────

    def _on_new(self) -> None:
        self._tf = None
        self._biquads = []
        self._f_start = 1.0
        self._f_stop  = 1e6
        self._components = []
        self._sim_result = None
        for pw in (self._plot_mag, self._plot_phase, self._plot_gd, self._plot_pz):
            pw.clear()
        self.tblComponents.setRowCount(0)
        self.lblComputedOrder.setText("—")
        self.lblStatus.setText(self._("status_new"))

    def _on_open(self) -> None:
        QMessageBox.information(self,
            self._("dlg_open_title"), self._("dlg_open_msg"))

    def _on_save(self) -> None:
        QMessageBox.information(self,
            self._("dlg_save_title"), self._("dlg_save_msg"))

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _on_toggle_left_panel(self) -> None:
        self.leftPanel.setVisible(not self.leftPanel.isVisible())

    def _on_reset_zoom(self) -> None:
        """Reset all plot views to fit their current data."""
        for pw in (self._plot_mag, self._plot_phase,
                   self._plot_gd, self._plot_pz):
            pw.autoRange()

    def _on_about(self) -> None:
        dlg = uic.loadUi(ABOUT_FILE)
        dlg.setStyleSheet(QApplication.instance().styleSheet())
        t = self._
        dlg.setWindowTitle(t("about_window_title"))
        dlg.lblAppTitle.setText(t("about_app_title"))
        dlg.lblCourse.setText(t("about_course"))
        dlg.lblVersion.setText(t("about_version"))
        dlg.gbStudents.setTitle(t("about_gb_students"))
        dlg.gbInstructors.setTitle(t("about_gb_instructors"))
        dlg.lblInstitution.setText(t("about_institution"))
        dlg.lblYear.setText(t("about_year"))
        dlg.btnClose.setText(t("about_close"))
        dlg.exec()

    # ── Error helpers ─────────────────────────────────────────────────────────

    def _show_not_implemented(self, msg: str) -> None:
        self.lblStatus.setText(self._("status_not_impl"))
        QMessageBox.warning(self,
            self._("dlg_not_impl_title"),
            self._("dlg_not_impl_msg", msg=msg))

    def _show_error(self, title: str, detail: str) -> None:
        self.lblStatus.setText(self._("status_error", title=title))
        dlg = QMessageBox(self)
        dlg.setWindowTitle(title)
        dlg.setText(self._("dlg_error_msg"))
        dlg.setDetailedText(detail)
        dlg.setIcon(QMessageBox.Icon.Critical)
        dlg.exec()
