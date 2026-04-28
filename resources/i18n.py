# ============================================================
# filter_toolbox/resources/i18n.py
# UI string translations.
# To add a new language: copy the EN block, change the key,
# and translate the values.  Then add the key to LANGUAGES.
# ============================================================

LANGUAGES = {
    "English": "en",
    "Español": "es",
}

STRINGS = {
    # ── Main window ──────────────────────────────────────────
    "en": {
        # Window / title
        "app_title":            "Filter Design Toolbox",
        "window_title":         "Analog Filter Design Toolbox",

        # Menu bar
        "menu_file":            "File",
        "menu_view":            "View",
        "menu_help":            "Help",
        "action_new":           "New",
        "action_open":          "Open…",
        "action_save":          "Save",
        "action_export_netlist":"Export SPICE Netlist…",
        "action_export_report": "Export PDF Report…",
        "action_quit":          "Quit",
        "action_toggle_theme":  "Toggle Light/Dark Theme",
        "action_toggle_panel":  "Toggle Settings Panel",
        "action_language":      "Language",
        "action_about":         "About…",

        # Buttons
        "btn_design":           "Design Filter",
        "btn_simulate":         "Run SPICE Simulation",
        "btn_export_netlist":   "Export Netlist",
        "btn_export_report":    "Export Report",
        "btn_theme":            "☀ Light / Dark",
        "btn_reset_zoom":       "⊙ Reset Zoom",
        "chk_show_sos":         "Show SOS stages",

        # Group boxes
        "gb_approx":            "Approximation & Type",
        "gb_specs":             "Filter Specifications",
        "gb_impl":              "Implementation",
        "gb_passive":           "Passive Component Preferences",
        "gb_components":        "Computed Component Values",

        # Approximation & Type
        "lbl_approx":           "Approximation",
        "lbl_type":             "Filter Type",
        "approx_butterworth":   "Butterworth",
        "approx_cheby1":        "Chebyshev I",
        "approx_cheby2":        "Chebyshev II",
        "approx_elliptic":      "Elliptic (Cauer)",
        "type_lp":              "Low-pass",
        "type_hp":              "High-pass",
        "type_bp":              "Band-pass",
        "type_bs":              "Band-stop (Notch)",

        # Specifications
        "lbl_fp":               "Passband edge fp (Hz)",
        "lbl_fs":               "Stopband edge fs (Hz)",
        "lbl_fp_lower":         "Lower passband fp1 (Hz)",
        "lbl_fs_lower":         "Lower stopband fs1 (Hz)",
        "lbl_fp2":              "Passband edge fp2 (Hz)",
        "lbl_fs2":              "Stopband edge fs2 (Hz)",
        "lbl_ap":               "Max passband loss Ap (dB)",
        "lbl_as":               "Min stopband loss As (dB)",
        "lbl_order":            "Computed order n",

        # Implementation
        "lbl_topology":         "Topology",
        "lbl_ic_model":         "IC / Op-Amp Model",
        "topo_sk":              "Sallen-Key",
        "topo_tt":              "Tow-Thomas (UAF42)",
        "topo_del":             "Deliyannis-Friend",
        "topo_del_disabled_hp": "Deliyannis-Friend is not available for High-pass filters",

        # Passive components
        "lbl_r_series":         "Resistor Series (E-series)",
        "lbl_c_series":         "Capacitor Series",
        "lbl_r_base":           "Base Resistor (Ω)",
        "lbl_c_base":           "Base Capacitor (F)",

        # Component table headers
        "tbl_stage":            "Stage",
        "tbl_type":             "Type",
        "tbl_component":        "Component",
        "tbl_ideal":            "Ideal Value",
        "tbl_rounded":          "Rounded (E-series)",
        "tbl_error":            "Error (%)",

        # Plot titles / axes
        "plot_mag_title":       "Magnitude Response",
        "plot_mag_x":           "Frequency",
        "plot_mag_y":           "Magnitude",
        "plot_phase_title":     "Phase Response",
        "plot_phase_y":         "Phase",
        "plot_gd_title":        "Group Delay",
        "plot_gd_y":            "Group Delay",
        "plot_pz_title":        "Pole-Zero Map",
        "plot_pz_x":            "Real",
        "plot_pz_y":            "Imaginary",
        "tab_magnitude":        "Magnitude Response",
        "tab_phase":            "Phase Response",
        "tab_group_delay":      "Group Delay",
        "tab_pole_zero":        "Pole-Zero Map",
        "tab_schematic":        "Circuit Schematic",
        "legend_theoretical":   "Theoretical",
        "legend_spice":         "SPICE",
        "schematic_placeholder":"Schematic will be rendered here after design.",

        # Status messages
        "status_ready":         "Ready.",
        "status_computing":     "Computing transfer function…",
        "status_simulating":    "Running SPICE simulation…",
        "status_sim_done":      "Simulation complete.",
        "status_new":           "New session.",
        "status_not_impl":      "⚠ Student function not yet implemented.",
        "status_design_done":   "Design complete  |  Order {order}  |  {approx}  {ftype}  |  fp = {fp:.1f} Hz  fs = {fs:.1f} Hz",
        "status_netlist_saved": "Netlist saved → {path}",
        "status_error":         "Error: {title}",

        # Dialogs
        "dlg_no_design_title":  "No Design",
        "dlg_no_design_msg":    "Please run Design Filter first.",
        "dlg_not_impl_title":   "Not Implemented",
        "dlg_not_impl_msg":     "This function is a student entry point:\n\n{msg}",
        "dlg_error_msg":        "An error occurred.  See details below.",
        "dlg_open_title":       "Open",
        "dlg_open_msg":         "Session open/save not yet implemented.",
        "dlg_save_title":       "Save",
        "dlg_save_msg":         "Session open/save not yet implemented.",
        "dlg_report_title":     "Export Report",
        "dlg_report_msg":       "PDF report export is not yet implemented.\nStudents: use reportlab or matplotlib's PDF backend.",
        "dlg_netlist_filter":   "SPICE Files (*.cir *.sp *.net)",
        "dlg_netlist_title":    "Save Netlist",

        # About dialog
        "about_window_title":   "About — Analog Filter Design Toolbox",
        "about_app_title":      "Analog Filter Design Toolbox",
        "about_course":         "Advanced Instrumentation I — Class Lab Project",
        "about_version":        "Version 1.0",
        "about_gb_students":    "Student Team",
        "about_gb_instructors": "Instructors",
        "about_institution":    "Universidad Iberoamericana — Campus Ciudad de México",
        "about_year":           "2026",
        "about_close":          "Close",
    },

    # ── Spanish ──────────────────────────────────────────────
    "es": {
        # Window / title
        "app_title":            "Herramienta de Diseño de Filtros",
        "window_title":         "Herramienta de Diseño de Filtros Analógicos",

        # Menu bar
        "menu_file":            "Archivo",
        "menu_view":            "Vista",
        "menu_help":            "Ayuda",
        "action_new":           "Nuevo",
        "action_open":          "Abrir…",
        "action_save":          "Guardar",
        "action_export_netlist":"Exportar Netlist SPICE…",
        "action_export_report": "Exportar Reporte PDF…",
        "action_quit":          "Salir",
        "action_toggle_theme":  "Alternar Tema Claro/Oscuro",
        "action_toggle_panel":  "Alternar Panel de Configuración",
        "action_language":      "Idioma",
        "action_about":         "Acerca de…",

        # Buttons
        "btn_design":           "Diseñar Filtro",
        "btn_simulate":         "Ejecutar Simulación SPICE",
        "btn_export_netlist":   "Exportar Netlist",
        "btn_export_report":    "Exportar Reporte",
        "btn_theme":            "☀ Claro / Oscuro",
        "btn_reset_zoom":       "⊙ Reset Zoom",
        "chk_show_sos":         "Mostrar etapas SOS",

        # Group boxes
        "gb_approx":            "Aproximación y Tipo",
        "gb_specs":             "Especificaciones del Filtro",
        "gb_impl":              "Implementación",
        "gb_passive":           "Preferencias de Componentes Pasivos",
        "gb_components":        "Valores de Componentes Calculados",

        # Approximation & Type
        "lbl_approx":           "Aproximación",
        "lbl_type":             "Tipo de Filtro",
        "approx_butterworth":   "Butterworth",
        "approx_cheby1":        "Chebyshev I",
        "approx_cheby2":        "Chebyshev II",
        "approx_elliptic":      "Elíptico (Cauer)",
        "type_lp":              "Pasa-bajas",
        "type_hp":              "Pasa-altas",
        "type_bp":              "Pasa-banda",
        "type_bs":              "Rechaza-banda (Notch)",

        # Specifications
        "lbl_fp":               "Frec. de paso fp (Hz)",
        "lbl_fs":               "Frec. de rechazo fs (Hz)",
        "lbl_fp_lower":         "Paso inferior fp1 (Hz)",
        "lbl_fs_lower":         "Rechazo inferior fs1 (Hz)",
        "lbl_fp2":              "Paso superior fp2 (Hz)",
        "lbl_fs2":              "Rechazo superior fs2 (Hz)",
        "lbl_ap":               "Pérd. máx. en banda de paso Ap (dB)",
        "lbl_as":               "Pérd. mín. en banda de rechazo As (dB)",
        "lbl_order":            "Orden calculado n",

        # Implementation
        "lbl_topology":         "Topología",
        "lbl_ic_model":         "Modelo CI / Op-Amp",
        "topo_sk":              "Sallen-Key",
        "topo_tt":              "Tow-Thomas (UAF42)",
        "topo_del":             "Deliyannis-Friend",
        "topo_del_disabled_hp": "Deliyannis-Friend no está disponible para filtros pasa-altas",
        "lbl_r_series":         "Serie de resistores (E)",
        "lbl_c_series":         "Serie de capacitores (E)",
        "lbl_r_base":           "Resistor base (Ω)",
        "lbl_c_base":           "Capacitor base (F)",

        # Component table headers
        "tbl_stage":            "Etapa",
        "tbl_type":             "Tipo",
        "tbl_component":        "Componente",
        "tbl_ideal":            "Valor Ideal",
        "tbl_rounded":          "Redondeado (Serie E)",
        "tbl_error":            "Error (%)",

        # Plot titles / axes
        "plot_mag_title":       "Respuesta en Magnitud",
        "plot_mag_x":           "Frecuencia",
        "plot_mag_y":           "Magnitud",
        "plot_phase_title":     "Respuesta en Fase",
        "plot_phase_y":         "Fase",
        "plot_gd_title":        "Retardo de Grupo",
        "plot_gd_y":            "Retardo de Grupo",
        "plot_pz_title":        "Mapa de Polos y Ceros",
        "plot_pz_x":            "Real",
        "plot_pz_y":            "Imaginario",
        "tab_magnitude":        "Respuesta en Magnitud",
        "tab_phase":            "Respuesta en Fase",
        "tab_group_delay":      "Retardo de Grupo",
        "tab_pole_zero":        "Polos y Ceros",
        "tab_schematic":        "Esquemático del Circuito",
        "legend_theoretical":   "Teórico",
        "legend_spice":         "SPICE",
        "schematic_placeholder":"El esquemático se mostrará aquí después del diseño.",

        # Status messages
        "status_ready":         "Listo.",
        "status_computing":     "Calculando función de transferencia…",
        "status_simulating":    "Ejecutando simulación SPICE…",
        "status_sim_done":      "Simulación completada.",
        "status_new":           "Nueva sesión.",
        "status_not_impl":      "⚠ Función de estudiante aún no implementada.",
        "status_design_done":   "Diseño completo  |  Orden {order}  |  {approx}  {ftype}  |  fp = {fp:.1f} Hz  fs = {fs:.1f} Hz",
        "status_netlist_saved": "Netlist guardado → {path}",
        "status_error":         "Error: {title}",

        # Dialogs
        "dlg_no_design_title":  "Sin Diseño",
        "dlg_no_design_msg":    "Por favor ejecute primero Diseñar Filtro.",
        "dlg_not_impl_title":   "No Implementado",
        "dlg_not_impl_msg":     "Esta función es un punto de entrada para estudiantes:\n\n{msg}",
        "dlg_error_msg":        "Ocurrió un error. Vea los detalles abajo.",
        "dlg_open_title":       "Abrir",
        "dlg_open_msg":         "Abrir/guardar sesión aún no implementado.",
        "dlg_save_title":       "Guardar",
        "dlg_save_msg":         "Abrir/guardar sesión aún no implementado.",
        "dlg_report_title":     "Exportar Reporte",
        "dlg_report_msg":       "Exportación a PDF aún no implementada.\nEstudiantes: usar reportlab o el backend PDF de matplotlib.",
        "dlg_netlist_filter":   "Archivos SPICE (*.cir *.sp *.net)",
        "dlg_netlist_title":    "Guardar Netlist",

        # About dialog
        "about_window_title":   "Acerca de — Herramienta de Diseño de Filtros",
        "about_app_title":      "Herramienta de Diseño de Filtros Analógicos",
        "about_course":         "Instrumentación Avanzada I — Proyecto de Laboratorio",
        "about_version":        "Versión 1.0",
        "about_gb_students":    "Equipo de Estudiantes",
        "about_gb_instructors": "Profesores",
        "about_institution":    "Universidad Iberoamericana — Campus Ciudad de México",
        "about_year":           "2026",
        "about_close":          "Cerrar",
    },
}


def tr(key: str, lang: str = "en", **kwargs) -> str:
    """
    Return the translated string for *key* in *lang*.
    Falls back to English if the key is missing in the target language.
    Any keyword arguments are formatted into the string with str.format().
    """
    text = STRINGS.get(lang, STRINGS["en"]).get(key) \
        or STRINGS["en"].get(key, f"[{key}]")
    return text.format(**kwargs) if kwargs else text
