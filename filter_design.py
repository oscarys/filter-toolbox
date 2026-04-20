"""
filter_toolbox/filter_design.py
================================
Backend computation module.

STUDENT ENTRY POINTS
--------------------
Each function marked with  ── STUDENT CODE ──  is a stub that must be
implemented by the student team.  The GUI calls these functions via the
callbacks in mainwindow.py; the signatures and return types MUST be kept
exactly as documented.

Dependencies (install via pip):
    numpy, scipy, matplotlib, pyqtgraph, PySpice
"""

from __future__ import annotations
import numpy as np
import scipy.signal as sps
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Enumerations  (mirrors the GUI combo-box indices)
# ──────────────────────────────────────────────────────────────────────────────

class Approximation(Enum):
    BUTTERWORTH  = 0
    CHEBYSHEV_I  = 1
    CHEBYSHEV_II = 2
    ELLIPTIC     = 3

class FilterType(Enum):
    LOWPASS  = 0
    HIGHPASS = 1
    BANDPASS = 2
    BANDSTOP = 3

class Topology(Enum):
    SALLEN_KEY   = 0
    TOW_THOMAS   = 1   # UAF42
    DELIYANNIS   = 2

class ESeries(Enum):
    E6   = 6
    E12  = 12
    E24  = 24
    E48  = 48
    E96  = 96
    EXACT = -1


# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FilterSpec:
    """Filter specification entered by the user. All frequencies in Hz."""
    approximation : Approximation = Approximation.BUTTERWORTH
    filter_type   : FilterType    = FilterType.LOWPASS
    fp            : float = 1000.0    # passband edge Hz  (lower edge for BP/BS)
    fs            : float = 2000.0    # stopband edge Hz  (lower edge for BP/BS)
    fp2           : float = 3000.0    # upper passband edge Hz (BP/BS only)
    fs2           : float = 4000.0    # upper stopband edge Hz (BP/BS only)
    a_p           : float = 3.0       # max passband attenuation (dB)
    a_s           : float = 40.0      # min stopband attenuation (dB)

    @property
    def omega_p(self) -> float:
        """Passband edge in rad/s."""
        return 2 * np.pi * self.fp

    @property
    def omega_s(self) -> float:
        """Stopband edge in rad/s."""
        return 2 * np.pi * self.fs

    @property
    def omega_p2(self) -> float:
        """Upper passband edge in rad/s (BP/BS only)."""
        return 2 * np.pi * self.fp2

    @property
    def omega_s2(self) -> float:
        """Upper stopband edge in rad/s (BP/BS only)."""
        return 2 * np.pi * self.fs2

    @property
    def ripple_eps(self) -> float:
        """Passband ripple ε derived from Ap: ε = sqrt(10^(Ap/10) - 1)."""
        return np.sqrt(10 ** (self.a_p / 10) - 1)

@dataclass
class TransferFunction:
    """Represents H(s) = num(s) / den(s) as coefficient arrays (descending power)."""
    numerator   : np.ndarray = field(default_factory=lambda: np.array([1.0]))
    denominator : np.ndarray = field(default_factory=lambda: np.array([1.0, 1.0]))

    # Poles, zeros, gain (filled in by compute_poles_zeros)
    poles : np.ndarray = field(default_factory=lambda: np.array([]))
    zeros : np.ndarray = field(default_factory=lambda: np.array([]))
    gain  : float = 1.0

@dataclass
class ComponentValue:
    stage     : int
    name      : str          # e.g. "R1", "C2"
    ideal     : float        # Ohms or Farads
    rounded   : float        # nearest E-series value
    error_pct : float

@dataclass
class SimulationResult:
    """Holds the SPICE AC-analysis result vectors."""
    frequencies  : np.ndarray = field(default_factory=lambda: np.array([]))
    magnitude_db : np.ndarray = field(default_factory=lambda: np.array([]))
    phase_deg    : np.ndarray = field(default_factory=lambda: np.array([]))


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 1 ────────────────────────────────────────────────────
# Filter Order Calculator
# ──────────────────────────────────────────────────────────────────────────────

def compute_minimum_order(spec: FilterSpec) -> int:
    """
    Compute the minimum integer filter order that satisfies *spec*.

    Parameters
    ----------
    spec : FilterSpec
        Fully populated filter specification.  Use spec.omega_p / spec.omega_s
        (rad/s properties) for the selectivity ratio computation — do NOT use
        the Hz fields directly in the prototype formulas.

    Returns
    -------
    int
        Minimum order n ≥ 1.

    Notes
    -----
    ── STUDENT CODE ──
    Use the closed-form expressions for each approximation:
      Butterworth  : n ≥ log((10^(As/10)-1) / (10^(Ap/10)-1)) / (2·log(Ωs/Ωp))
      Chebyshev I  : n ≥ acosh(√((10^(As/10)-1) / ε²)) / acosh(Ωs/Ωp)
      Chebyshev II : symmetric to Cheby-I via stopband selectivity
      Elliptic     : use Landen/elliptic-integral formulas or scipy.signal.ellipord
    For BP/BS convert the two-sided spec to a LP prototype selectivity ratio first.
    Always round up to the nearest integer (math.ceil).
    """
    # Orden por default
    n = 1
    
    # Cociente de selectividad según tipo de filtro para las especificaciones 
    # Usar omega_ratio en vez de  spec.omega_s/spec.omega_p directo,ya que eso solo
    # funciona para LP. Aquí calculamos el cociente  para cada caso.
    if spec.filter_type == FilterType.LOWPASS:
        # LP: directo, fs > fp entonces ratio > 1
        omega_ratio = spec.omega_s / spec.omega_p


    elif spec.filter_type == FilterType.HIGHPASS:
        # HP: se invierte porque la transformación LP a HP voltea el eje de
        # frecuencias. fp > fs en HP, al invertir obtenemos ratio > 1.
        omega_ratio = spec.omega_p / spec.omega_s

    #funcion para bandstop
    #Funcion para bandpass

    # Calcula especificación
    if spec.approximation == Approximation.BUTTERWORTH:
        n = np.ceil(np.log((10**(spec.a_s/10)-1) / (10**(spec.a_p/10)-1)) / (2*np.log(omega_ratio))).astype(int)
    elif spec.approximation == Approximation.CHEBYSHEV_I:
        n = np.ceil(np.acosh(np.sqrt((10**(spec.a_s/10)-1) / spec.ripple_eps**2)) / np.acosh(omega_ratio)).astype(int)
    elif spec.approximation == Approximation.CHEBYSHEV_II:
        n = np.ceil(np.acosh(np.sqrt((10**(spec.a_s/10)-1) / spec.ripple_eps**2)) / np.acosh(omega_ratio)).astype(int)
    elif spec.approximation == Approximation.ELLIPTIC:
        import scipy.signal as sig
        n, _ = sig.ellipord(wp=1.0, ws=omega_ratio, gpass=spec.a_p, gstop=spec.a_s, analog=True)
        n = int(n)
        
    # Regresa el orden del filtro

    print(f'debug (oscar): orden del filtro {n}')

    return n

# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 2 ────────────────────────────────────────────────────
# Prototype and Frequency-Transformed Transfer Function
# ──────────────────────────────────────────────────────────────────────────────

def compute_transfer_function(spec: FilterSpec) -> tuple[TransferFunction, int]:
    """
    Compute the analogue transfer function H(s) for the given specification.

    Steps expected:
      1. Call compute_minimum_order(spec) to obtain n.
      2. Compute LP prototype poles (and zeros for Cheby-II / Elliptic).
      3. Apply LP→{LP|HP|BP|BS} frequency transformation using spec.omega_p/s.
      4. Denormalise to the physical edge frequency.
      5. Express as rational polynomial in *s*.

    Parameters
    ----------
    spec : FilterSpec

    Returns
    -------
    (TransferFunction, int)
        tf  : TransferFunction  — .numerator and .denominator are numpy arrays
              of polynomial coefficients (highest power first, scipy convention).
              .poles, .zeros, .gain are also populated.
        order : int             — the computed minimum order (displayed in the GUI).

    Notes
    -----
    ── STUDENT CODE ──
    Hint: scipy.signal.{buttap, cheb1ap, cheb2ap, ellipap} return LP prototype
    zeros, poles, gain.  scipy.signal.lp2{lp,hp,bp,bs} perform the frequency
    transformation.  scipy.signal.zpk2tf converts to polynomial form.
    Use spec.omega_p, spec.omega_s, spec.omega_p2, spec.omega_s2 (rad/s).
    Use spec.ripple_eps for the prototype ripple parameter.
    """

    # 1. Calcula el orden del filtro
    n = compute_minimum_order(spec)
    
    # Crea el objeto para la fucnión de transferencia
    tf = TransferFunction()
    
    #  2. Compute LP prototype poles (and zeros for Cheby-II / Elliptic).
    # OJO cálculo de ejemplo TEMPORAL: polos chebyshev orden 4
    n = 4
    wc = 2*np.pi*100
    e = 0.01
    a = (1/n)*np.arcsinh(1/e)
    k = np.arange(0, 2*n)
    p = np.sin((2*k+1)*np.pi/(2*n))*np.sinh(a) + 1j*np.cos((2*k+1)*np.pi/(2*n))*np.cosh(a)
    tf.poles = np.array([pi for pi in p if pi.real < 0])
    tf.numerator = np.array([wc**n])
    den = np.poly(tf.poles)
    tf.denominator = np.array([den[0], wc*den[1], (wc**2)*den[2], (wc**3)*den[3], wc**4])
    
    #  3. Apply LP→{LP|HP|BP|BS} frequency transformation using spec.omega_p/s.
    #  4. Denormalise to the physical edge frequency.
    #  5. Express as rational polynomial in *s*.
    
    # Regresa el objeto función de transferencia y el orden
    return (tf, n)
    
    #raise NotImplementedError("STUDENT: implement compute_transfer_function()")


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 3 ────────────────────────────────────────────────────
# Biquad / Stage Decomposition
# ──────────────────────────────────────────────────────────────────────────────

def factored_biquads(tf: TransferFunction) -> list[TransferFunction]:
    """
    Split H(s) into a cascade of first- and second-order sections (biquads).

    Parameters
    ----------
    tf : TransferFunction
        Full-order transfer function returned by compute_transfer_function().

    Returns
    -------
    list[TransferFunction]
        Each element is a 1st- or 2nd-order section, ordered for minimum
        intermediate signal dynamics (Q-ordered pairing recommended).

    Notes
    -----
    ── STUDENT CODE ──
    Use scipy.signal.tf2sos then convert each row back to a TransferFunction.
    Apply Q-ordered pairing and output-ordering optimisation.
    """

    sos = scipy.signal.tf2sos(tf.numerator, tf.denominator)

    sections = []

    for row in sos:
        b = row[:3].copy()
        a = row[3:].copy()

        if not np.isclose(a[0], 1.0):
            b = b / a[0]
            a = a / a[0]

        if np.isclose(a[2], 0.0) and np.isclose(b[2], 0.0):
            b = b[:2]
            a = a[:2]

        section_tf = TransferFunction(
            numerator = np.array(b),
            denominator = np.array(a)
        )

        sections.append(section_tf)

    # ----- Q-ordering (inline) -----
    def compute_Q(section):
        a = section.denominator
        if len(a) == 3:
            a1 = a[1]
            a2 = a[2]
            if a1 != 0 and a2 > 0:
                return np.sqrt(a2) / a1
        return 0.0

    sections = sorted(sections, key = compute_Q)

    return sections

    raise NotImplementedError("STUDENT: implement factored_biquads()")


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 4 ────────────────────────────────────────────────────
# Frequency Response (Theoretical)
# ──────────────────────────────────────────────────────────────────────────────

def compute_frequency_response(
    tf: TransferFunction,
    f_start: float = 1.0,
    f_stop: float = 1e6,
    n_points: int = 1000,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Evaluate H(jω) over a logarithmic frequency sweep.

    Parameters
    ----------
    tf       : TransferFunction
    f_start  : float   – start frequency in Hz
    f_stop   : float   – stop  frequency in Hz
    n_points : int     – number of frequency points

    Returns
    -------
    (freqs_hz, magnitude_db, phase_deg, group_delay_s)
        All four arrays have length n_points.
        freqs_hz      : np.ndarray  – frequency axis in Hz
        magnitude_db  : np.ndarray  – |H(jω)| in dB
        phase_deg     : np.ndarray  – unwrapped phase in degrees
        group_delay_s : np.ndarray  – group delay τ(ω) = -dφ/dω in seconds

    Notes
    -----
    ── STUDENT CODE ──
    Use scipy.signal.freqs (analogue) to evaluate the transfer function.
    Unwrap the phase with np.unwrap before converting to degrees.
    Group delay = -d(phase_rad)/d(omega).  Use np.gradient for numerical diff.
    """
    
    # Eje logarítmico de frecuencias en Hz
    freqs_hz = np.logspace(np.log10(f_start), np.log10(f_stop), n_points)
    # Mismo eje, en rad/s
    omega = 2*np.pi*freqs_hz
    # Calcula la respuesta en frecuencia
    w, H = sps.freqs(tf.numerator, tf.denominator, worN=omega)
    # Calcula la magnitud en dB
    magnitude_db = 20*np.log10(np.abs(H))
    # Calcula la fase en rad/s y grados
    phase_rad = np.unwrap(np.angle(H))
    phase_deg = np.degrees(phase_rad)
    # Calcula el retardo de grupo 
    dphi_domega = np.gradient(phase_rad, omega)
    group_delay_s = -dphi_domega
    # Regresa la tupla de arreglos calculados
    return (freqs_hz, magnitude_db, phase_deg, group_delay_s)

    # raise NotImplementedError("STUDENT: implement compute_frequency_response()")


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 5 ────────────────────────────────────────────────────
# Component Synthesis  (Sallen-Key)
# ──────────────────────────────────────────────────────────────────────────────

def synthesise_sallen_key(
    biquads: list[TransferFunction],
    r_base: float,
    c_base: float,
    r_series: ESeries,
    c_series: ESeries,
) -> list[ComponentValue]:
    """
    Compute R and C values for a Sallen-Key cascade realising *biquads*.

    Parameters
    ----------
    biquads  : list[TransferFunction]   – from factored_biquads()
    r_base   : float                    – base/scaling resistor value (Ω)
    c_base   : float                    – base/scaling capacitor value (F)
    r_series : ESeries                  – target E-series for resistors
    c_series : ESeries                  – target E-series for capacitors

    Returns
    -------
    list[ComponentValue]
        One entry per component per stage, populated with ideal, rounded, and
        error_pct fields.

    Notes
    -----
    ── STUDENT CODE ──
    For each biquad extract ω₀ and Q.  Apply the equal-C (or equal-R) design
    equations for a unity-gain Sallen-Key LP section.  For HP sections apply
    the LP→HP dual (swap R↔C roles).
    Use round_to_eseries() (provided below) to snap to standard values.
    """
    raise NotImplementedError("STUDENT: implement synthesise_sallen_key()")


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 6 ────────────────────────────────────────────────────
# Component Synthesis  (Tow-Thomas / UAF42)
# ──────────────────────────────────────────────────────────────────────────────

def synthesise_tow_thomas(
    biquads: list[TransferFunction],
    r_base: float,
    c_base: float,
    r_series: ESeries,
    c_series: ESeries,
) -> list[ComponentValue]:
    """
    Compute component values for a Tow-Thomas (state-variable / UAF42) cascade.

    Notes
    -----
    ── STUDENT CODE ──
    The UAF42 integrates two lossless integrators and a weighted summer.
    For each biquad:
        C₁ = C₂ = C  (user base value)
        R₁ = R₂ = 1 / (ω₀ · C)
        R_q = Q / (ω₀ · C)   (Q-setting resistor)
    Refer to the Burr-Brown UAF42 datasheet for the full design equations
    including the optional gain-setting resistors.
    """
    raise NotImplementedError("STUDENT: implement synthesise_tow_thomas()")


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 7 ────────────────────────────────────────────────────
# Component Synthesis  (Deliyannis-Friend)
# ──────────────────────────────────────────────────────────────────────────────

def synthesise_deliyannis(
    biquads: list[TransferFunction],
    r_base: float,
    c_base: float,
    r_series: ESeries,
    c_series: ESeries,
) -> list[ComponentValue]:
    """
    Compute component values for a Deliyannis-Friend (Friend) bandpass cascade.

    Notes
    -----
    ── STUDENT CODE ──
    The Friend (single-amplifier bandpass) biquad uses:
        C₁ = C₂ = C
        R₁ = 1 / (ω₀ · C · (2Q - 1/K))  where K is the gain at ω₀
        R₂ = Q / (ω₀ · C · K)
    Refer to Deliyannis (1968) and Wai-Kai Chen "Active Network Analysis" Ch. 6.
    """
    raise NotImplementedError("STUDENT: implement synthesise_deliyannis()")


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 8 ────────────────────────────────────────────────────
# SPICE Netlist Generation
# ──────────────────────────────────────────────────────────────────────────────

def generate_spice_netlist(
    components: list[ComponentValue],
    topology: Topology,
    ic_model: str,
) -> str:
    """
    Build a SPICE netlist string for AC analysis of the designed filter.

    Parameters
    ----------
    components : list[ComponentValue]   – from synthesise_*()
    topology   : Topology
    ic_model   : str                    – e.g. "TL071", "LM741", "Ideal"

    Returns
    -------
    str  – complete SPICE netlist ready to write to a .cir file.

    Notes
    -----
    ── STUDENT CODE ──
    Use PySpice's Circuit builder or write the netlist string manually.
    Include:
      * .ac dec 100 1 10Meg   (or appropriate range)
      * The op-amp sub-circuit model (load from resources/ .lib files)
      * Voltage source Vin ac 1
      * Component instances from the stages
      * .probe V(out)
    """
    raise NotImplementedError("STUDENT: implement generate_spice_netlist()")


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 9 ────────────────────────────────────────────────────
# Run PySpice AC Simulation
# ──────────────────────────────────────────────────────────────────────────────

def run_spice_simulation(netlist: str) -> SimulationResult:
    """
    Execute an AC simulation via PySpice and return the results.

    Parameters
    ----------
    netlist : str   – SPICE netlist from generate_spice_netlist()

    Returns
    -------
    SimulationResult
        .frequencies  : np.ndarray  Hz
        .magnitude_db : np.ndarray  dB
        .phase_deg    : np.ndarray  degrees

    Notes
    -----
    ── STUDENT CODE ──
    Example using PySpice:

        from PySpice.Spice.Netlist import Circuit
        from PySpice.Spice.NgSpice.Shared import NgSpiceShared

        # Write netlist to a temp file, run ngspice, parse .raw output.
        # PySpice's RawFile parser gives Analysis.frequency and complex voltages.
        # magnitude_db = 20*np.log10(np.abs(analysis['out']))
        # phase_deg    = np.degrees(np.angle(analysis['out']))

    Requires ngspice to be installed and on PATH.
    """
    raise NotImplementedError("STUDENT: implement run_spice_simulation()")


# ──────────────────────────────────────────────────────────────────────────────
# Helper Utilities  (provided – students should NOT modify these)
# ──────────────────────────────────────────────────────────────────────────────

# Pre-computed E-series tables
_E_SERIES: dict[int, list[float]] = {
    6:  [1.0, 1.5, 2.2, 3.3, 4.7, 6.8],
    12: [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2],
    24: [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
         3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1],
    48: [],   # populated below
    96: [],
}

def _build_e48_e96() -> None:
    """Generate E48 and E96 from the IEC 60063 formula."""
    for n in (48, 96):
        vals = sorted({round(10 ** (k / n), 2) for k in range(n)})
        _E_SERIES[n] = vals

_build_e48_e96()


def round_to_eseries(value: float, series: ESeries) -> float:
    """
    Round *value* to the nearest standard value in the given E-series.

    Works for any order of magnitude (e.g. 15 300 Ω → nearest E24 value).

    Parameters
    ----------
    value  : float   – ideal component value (Ω or F)
    series : ESeries

    Returns
    -------
    float  – nearest E-series value, same order of magnitude as *value*.
    """
    if series == ESeries.EXACT or value <= 0:
        return value

    table = _E_SERIES[series.value]
    if not table:
        return value

    # Decompose into mantissa ∈ [1, 10) and decade
    decade = 10 ** np.floor(np.log10(value))
    mantissa = value / decade

    # Find nearest in table (table covers [1, 10))
    nearest = min(table, key=lambda v: abs(v - mantissa))
    # Handle wraparound: if mantissa closer to 10 than any table value
    if abs(mantissa - 10.0) < abs(mantissa - nearest):
        nearest = 1.0
        decade *= 10

    return round(nearest * decade, 14)


def eseries_error_pct(ideal: float, rounded: float) -> float:
    """Return the percentage error introduced by rounding to an E-series."""
    if ideal == 0:
        return 0.0
    return 100.0 * (rounded - ideal) / ideal
