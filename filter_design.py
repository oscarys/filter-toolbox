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
from itertools import groupby


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

class SectionType(Enum):
    """
    Classification of a single biquad / first-order section.

    Determined by inspecting which numerator coefficients are
    significant (above a small threshold relative to the leading term).

    First-order sections
    --------------------
    LOWPASS_1   :  H(s) = b0 / (s + a0)             — num has only constant term
    HIGHPASS_1  :  H(s) = b1·s / (s + a0)           — num has only s term

    Second-order sections
    ---------------------
    LOWPASS_2   :  H(s) = b0 / (s² + …)             — num has only b0
    BANDPASS    :  H(s) = b1·s / (s² + …)           — num has only b1·s
    HIGHPASS_2  :  H(s) = b2·s² / (s² + …)         — num has only b2·s²
    BANDSTOP    :  H(s) = (b2·s² + b0) / (s² + …)  — num has b2·s² and b0
    ALLPASS     :  num ≈ den (mirrored coefficients)
    UNKNOWN     :  does not match any of the above patterns
    """
    LOWPASS_1  = "LP1"
    HIGHPASS_1 = "HP1"
    LOWPASS_2  = "LP2"
    BANDPASS   = "BP"
    HIGHPASS_2 = "HP2"
    BANDSTOP   = "BS"
    ALLPASS    = "AP"
    UNKNOWN    = "?"


@dataclass
class TransferFunction:
    """Represents H(s) = num(s) / den(s) as coefficient arrays (descending power)."""
    numerator   : np.ndarray = field(default_factory=lambda: np.array([1.0]))
    denominator : np.ndarray = field(default_factory=lambda: np.array([1.0, 1.0]))

    # Poles, zeros, gain
    poles : np.ndarray = field(default_factory=lambda: np.array([]))
    zeros : np.ndarray = field(default_factory=lambda: np.array([]))
    gain  : float = 1.0

    # Set by factored_biquads() — tells synthesise_* what kind of section this is
    section_type : SectionType = SectionType.UNKNOWN

    # Set by compute_transfer_function() — the global filter type from the spec,
    # carried down so netlist generators know the full context
    filter_type  : FilterType  = FilterType.LOWPASS

class ComponentType(Enum):
    RESISTOR  = "R"
    CAPACITOR = "C"
    INDUCTOR  = "L"   # reserved for future use

@dataclass
class ComponentValue:
    stage          : int
    name           : str              # e.g. "R1", "C2"
    component_type : ComponentType    # RESISTOR or CAPACITOR
    ideal          : float            # Ohms or Farads
    rounded        : float            # nearest E-series value
    error_pct      : float
    section_type   : SectionType  = SectionType.UNKNOWN   # LP2, BP, HP2, etc.
    filter_type    : FilterType   = FilterType.LOWPASS     # global filter context

    def formatted_ideal(self) -> str:
        """Return ideal value as a human-readable string with SI prefix."""
        return _si_format(self.ideal, self.component_type)

    def formatted_rounded(self) -> str:
        """Return rounded value as a human-readable string with SI prefix."""
        return _si_format(self.rounded, self.component_type)


def _si_format(value: float, ctype: ComponentType) -> str:
    """Format a component value with the appropriate SI prefix and unit."""
    unit = "Ω" if ctype == ComponentType.RESISTOR else "F"
    for threshold, prefix in (
        (1e12, "T"), (1e9, "G"), (1e6, "M"), (1e3, "k"),
        (1.0,  ""),  (1e-3, "m"), (1e-6, "μ"), (1e-9, "n"),
        (1e-12, "p"),
    ):
        if abs(value) >= threshold:
            return f"{value / threshold:.4g} {prefix}{unit}"
    return f"{value:.4g} {unit}"

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

    #funcion para bandpass
    elif spec.filter_type == FilterType.BANDPASS:
        # BP: convertimos los dos bordes de rechazo al prototipo LP equivalente
        # y tomamos el más restrictivo (el menor) para garantizar ambos bordes.
        import math
        omega_0 = math.sqrt(spec.omega_p * spec.omega_p2)
        BW      = spec.omega_p2 - spec.omega_p
        Os1 = abs(spec.omega_s**2  - omega_0**2) / (BW * spec.omega_s)
        Os2 = abs(spec.omega_s2**2 - omega_0**2) / (BW * spec.omega_s2)
        omega_ratio = min(Os1, Os2)

    #Funcion para bandstop
    elif spec.filter_type == FilterType.BANDSTOP:
        # BS: inverso del BP, el rechazo está en el centro.
        import math
        omega_0 = math.sqrt(spec.omega_p * spec.omega_p2)
        BW      = spec.omega_p2 - spec.omega_p
        Os1 = (BW * spec.omega_s)  / abs(spec.omega_s**2  - omega_0**2)
        Os2 = (BW * spec.omega_s2) / abs(spec.omega_s2**2 - omega_0**2)
        omega_ratio = min(Os1, Os2)

    # Guardia: si el cociente es ≤ 1 las specs son inválidas
    # (puede ocurrir en la llamada inicial de la GUI con valores default)
    if omega_ratio <= 1.0:
        print(f'(debug): orden del filtro inválido (Ωs={omega_ratio:.3f} ≤ 1), retornando 1')
        return 1

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

    print(f'(debug): orden del filtro {n}')

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

    # Calcula el orden del filtro con la funcion antes implementada 
    n = compute_minimum_order(spec)

    # Calcula los prototipos normalizados pasabajas (wp= 1rad/s)
    # cheb1ap recibe rp en dB (=a_p), No epsilon
    # cheb2ap recibe rs en dB (=a_s), NO epsilon
    # ellipap recibe rp y rs ambos en dB 

    match spec.approximation:
        case Approximation.BUTTERWORTH:
            #respuesta maximalmente plana 
            z, p, k = sps.buttap(n)
        case Approximation.CHEBYSHEV_I:
            # rp = rizado máximo en la banda de paso en dB
            z, p, k = sps.cheb1ap(n, rp=spec.a_p)
        case Approximation.CHEBYSHEV_II:
            # rs = atenuación mínima en la banda de rechazo en dB
            z, p, k = sps.cheb2ap(n, rs=spec.a_s)
        case Approximation.ELLIPTIC:
            # Necesita ambos: rizado en paso y atenuación en rechazo
            z, p, k = sps.ellipap(n, rp=spec.a_p, rs=spec.a_s)

    # ── Compute the correct prototype denormalisation frequency ──────────────
    # Each approximation normalises the LP prototype differently:
    #
    # Butterworth  : poles at 1 rad/s = the -3dB point, NOT the -Ap dB point.
    #                Must scale so that the -Ap dB point lands at omega_p:
    #                omega_c = omega_p / (10^(Ap/10) - 1)^(1/(2n))
    #
    # Chebyshev I  : prototype passband edge is exactly at 1 rad/s (-Ap dB).
    #                omega_c = omega_p  (no correction needed)
    #
    # Chebyshev II : prototype is normalised at the STOPBAND edge (1 rad/s = -As dB).
    #                omega_c = omega_s  (use stopband edge, not passband)
    #
    # Elliptic     : like Chebyshev I, passband edge at 1 rad/s (-Ap dB).
    #                omega_c = omega_p  (no correction needed)
    #
    # For BP/BS the same correction applies to omega_p (and omega_s for Cheby-II),
    # since lp2bp/lp2bs use BW which is already in physical rad/s.

    match spec.approximation:
        case Approximation.BUTTERWORTH:
            # Correct cutoff so -Ap dB lands exactly at omega_p
            omega_c = spec.omega_p / (10 ** (spec.a_p / 10) - 1) ** (1 / (2 * n))
        case Approximation.CHEBYSHEV_I:
            omega_c = spec.omega_p   # passband edge = 1 rad/s in prototype
        case Approximation.CHEBYSHEV_II:
            omega_c = spec.omega_s   # prototype normalised at stopband edge
        case Approximation.ELLIPTIC:
            omega_c = spec.omega_p   # passband edge = 1 rad/s in prototype

    # For BP/BS also compute the correct stopband-edge frequency for Chebyshev II
    if spec.filter_type in (FilterType.BANDPASS, FilterType.BANDSTOP):
        omega_0 = np.sqrt(spec.omega_p * spec.omega_p2)
        BW      = spec.omega_p2 - spec.omega_p
        if spec.approximation == Approximation.CHEBYSHEV_II:
            # Use the more restrictive of the two stopband edges
            Os1 = abs(spec.omega_s **2 - omega_0**2) / (BW * spec.omega_s)
            Os2 = abs(spec.omega_s2**2 - omega_0**2) / (BW * spec.omega_s2)
            # omega_c for BP/BS Cheby-II is incorporated via BW scaling
            # (lp2bp/lp2bs handle the centre frequency and BW directly)

    # TRANSFORMACION DE FRECUENCIA LP a {LP,HP,BP,BS}, AQUI SE OBTIENEN FRECUENCIAS DE CORTE 
    # Usamos z,p,k en lugar de polinomios para hacerlo mas estable con ordenes altos
    # lp2lp_zpk: escala la frecuencia de 1 rad/s a omega_p real
    # lp2hp_zpk: invierte el eje de frecuencias y escala a omega_p
    # lp2bp_zpk: abre la banda alrededor de omega_0 con ancho BW
    # lp2bs_zpk: inverso del BP ,  rechazo en el centro

    match spec.filter_type : 
        case FilterType.LOWPASS: 
            print(f'(debug): lp frec desnormalización: {omega_c/(2*np.pi)} Hz')
            z, p, k = sps.lp2lp_zpk(z, p, k, wo=omega_c)

        case FilterType.HIGHPASS:
            print(f'(debug): hp frec desnormalización: {omega_c/(2*np.pi)} Hz')
            z, p, k = sps.lp2hp_zpk(z, p, k, wo=omega_c)

        case FilterType.BANDPASS:
            omega_0 = np.sqrt(spec.omega_p * spec.omega_p2)
            BW      = spec.omega_p2 - spec.omega_p
            print(f'(debug): bp frec desnormalización: {omega_0/(2*np.pi)} Hz')
            print(f'(debug): bp bandwidth: {BW/(2*np.pi)} Hz')
            z, p, k = sps.lp2bp_zpk(z, p, k, wo=omega_0, bw=BW)

        case FilterType.BANDSTOP:
            omega_0 = np.sqrt(spec.omega_p * spec.omega_p2)
            BW      = spec.omega_p2 - spec.omega_p
            print(f'(debug): bs frec desnormalización: {omega_0/(2*np.pi)} Hz')
            print(f'(debug): bs bandwidth: {BW/(2*np.pi)} Hz')
            z, p, k = sps.lp2bs_zpk(z, p, k, wo=omega_0, bw=BW)

    # Calcula los polinomios de la función de transferencia
    # Convertir ZPK a coeficientes de polinomio 
    # zpk2tf convierte zeros,polos,ganancia a coeficientes num/den en orden
    # descendente de potencias: [b_n, b_{n-1}, b_0] / [a_n, a_0]
    # np.real() elimina la parte imaginaria residual de punto flotante (~1e-16).
    # Los coeficientes deben ser reales porque los polos complejos siempre son pares conjugados.
    num, den = sps.zpk2tf(z, p, k)

    # objeto TransferFunction
    # Se necesita los coeficientes para graficar H(jω) y los polos/zeros para el mapa polo-cero.
    tf = TransferFunction(
        numerator   = np.real(num),
        denominator = np.real(den),
        poles       = p,
        zeros       = z,
        gain        = float(np.real(k)),
        filter_type = spec.filter_type,   # carry spec context into TF
    )

    print(f'(debug): num: {tf.numerator}')
    print(f'(debug): den: {tf.denominator}')

    # Regresa el objeto función de transferencia y el orden
    return (tf, n)
    
    #raise NotImplementedError("STUDENT: implement compute_transfer_function()")


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 3 ────────────────────────────────────────────────────
# Biquad / Stage Decomposition
# ──────────────────────────────────────────────────────────────────────────────

def _classify_section(num: np.ndarray, den: np.ndarray, tol: float = 1e-4) -> SectionType:
    """
    Classify a biquad section by inspecting its numerator coefficient pattern.

    Parameters
    ----------
    num : np.ndarray  – numerator coefficients [b2, b1, b0] (length ≤ 3)
    den : np.ndarray  – denominator coefficients [a2, a1, a0] (length ≤ 3)
    tol : float       – relative threshold below which a coefficient is
                        considered zero (default 1e-4)

    Returns
    -------
    SectionType

    Notes
    -----
    Instructor-provided — do NOT modify.

    Numerator patterns (after padding to length 3: [b2, b1, b0]):
      [0,  0,  *]  →  LOWPASS_2  (only constant term)
      [0,  *,  0]  →  BANDPASS   (only s term)
      [*,  0,  0]  →  HIGHPASS_2 (only s² term)
      [*,  0,  *]  →  BANDSTOP   (s² and constant, no s term)
      [*,  *,  *]  →  ALLPASS if num ≈ reversed(den), else UNKNOWN

    For first-order sections (den has 2 coefficients):
      [0,  *]      →  LOWPASS_1
      [*,  0]      →  HIGHPASS_1
    """
    # Normalise to leading coefficient of denominator
    scale = abs(den[0]) if abs(den[0]) > 1e-30 else 1.0

    order = len(den) - 1   # 1 or 2

    # Pad numerator to match denominator length
    b = np.zeros(order + 1)
    b_src = np.real(num)
    b[-(len(b_src)):] = b_src

    # Relative significance mask
    sig = np.abs(b) / scale > tol

    if order == 1:
        # First-order section
        if sig[0] and not sig[1]:
            return SectionType.HIGHPASS_1
        if sig[1] and not sig[0]:
            return SectionType.LOWPASS_1
        return SectionType.UNKNOWN

    # Second-order section: sig = [b2_sig, b1_sig, b0_sig]
    b2, b1, b0 = sig
    if not b2 and not b1 and b0:
        return SectionType.LOWPASS_2
    if not b2 and b1 and not b0:
        return SectionType.BANDPASS
    if b2 and not b1 and not b0:
        return SectionType.HIGHPASS_2
    if b2 and not b1 and b0:
        return SectionType.BANDSTOP
    if b2 and b1 and b0:
        # Check for allpass: num coefficients ≈ reversed den coefficients
        den_norm = np.real(den) / den[0]
        num_norm = b / (b[0] if abs(b[0]) > 1e-30 else 1.0)
        if np.allclose(num_norm, den_norm[::-1], rtol=tol * 10):
            return SectionType.ALLPASS
    return SectionType.UNKNOWN


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
    # Arreglo de secciones
    sections = []
    # Calcula los ceros y los polos, ordenados por pares conjugados
    z = np.sort_complex(np.roots(tf.numerator))
    p = np.sort_complex(np.roots(tf.denominator))
    # Calcula el orden del filtro
    n = tf.denominator.shape[0] - 1
    # Genera las secciones segun n y tipo de filtro
    match tf.filter_type:
        case FilterType.LOWPASS:
            scale = tf.numerator[-1]**(1/n)
            if n%2:
                # Sección de primer orden
                seccion = TransferFunction(
                    numerator = np.real(np.array([scale])),
                    denominator = np.real(np.array([1, -p[0]])),
                    section_type = SectionType.LOWPASS_1,
                    filter_type  = tf.filter_type)
                sections.append(seccion)
                p = p[1:]
            for i in range(0,p.shape[0],2):
                # Sección de primer orden
                seccion = TransferFunction(
                    numerator = np.real(np.array([scale**2])),
                    denominator = np.real(np.poly(p[i:i+2])),
                    section_type = SectionType.LOWPASS_2,
                    filter_type  = tf.filter_type)
                sections.append(seccion)
        case _:
            # Factoriza en secciones de segundo orden
            sos = sps.tf2sos(tf.numerator, tf.denominator, pairing='minimal', analog=True)
            # Genera los objetos TransferFunction para cada seccion,
            # clasificando cada una y propagando el filter_type global.
            sections = []
            for row in sos:
                num, den = row[:3], row[3:]
                sec = TransferFunction(
                    numerator   = num,
                    denominator = den,
                    section_type = _classify_section(num, den),
                    filter_type  = tf.filter_type,   # carry global context down
                )
                sections.append(sec)

    # ----- Q-ordering (inline) -----
    def compute_Q(section):
        a = section.denominator
        if len(a) == 3:
            a1 = a[1]
            a2 = a[2]
            if a1 != 0 and a2 > 0:
                return np.sqrt(a2) / a1
        return 0.0

    sections = sorted(sections, key=compute_Q)

    for i, s in enumerate(sections):
        print(f'(debug) S{i+1}: {s.section_type}')
        print(f'                  {s.filter_type}')
        print(f'                  num: {s.numerator}')
        print(f'                  den: {s.denominator}')

    return sections

    # raise NotImplementedError("STUDENT: implement factored_biquads()")


# ──────────────────────────────────────────────────────────────────────────────
# ── STUDENT ENTRY POINT 4 ────────────────────────────────────────────────────
# Frequency Response (Theoretical)
# ──────────────────────────────────────────────────────────────────────────────

def compute_frequency_response(
    tf: TransferFunction,
    f_start: float = (0.01)*2*np.pi,
    f_stop: float = (1e2)*2*np.pi,
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
    For each biquad inspect biquad.section_type to determine the circuit:
      SectionType.LOWPASS_2  → Sallen-Key LP (equal-C design)
      SectionType.HIGHPASS_2 → Sallen-Key HP (equal-R design, swap R↔C roles)
      SectionType.LOWPASS_1  → Single RC + voltage follower (1st-order LP)
      SectionType.HIGHPASS_1 → Single RC + voltage follower (1st-order HP)
    Also check biquad.filter_type for the global filter context if needed.
    Use round_to_eseries() to snap to standard values.
    """
    components = []

    for stage_idx, biquad in enumerate(biquads):
        stage_num = stage_idx + 1
        ftype = biquad.filter_type

        #Limpiar el denominador de ceros lideres
        num_work = np.array(biquad.numerator, dtype = float)
        den_work = np.array(biquad.denominator, dtype = float)
       
        while len(den_work) > 1 and abs(den_work[0]) < 1e-20:
            den_work = den_work[1:]
            num_work = num_work[1:]

        #Reclasifica la seccion con los arrays limpios
        #Necesario cuando el biquad venia con cero lider y section_type incorrecto
        stype = _classify_section(num_work, den_work)

        print(f" [synthesise] Etapa {stage_num}: "
              f"section_type original = {biquad.section_type.value} ->" 
              f"corregido = {stype.value} "
              f"num= {np.round(num_work, 4)} den = {np.round(den_work, 4)}") 
        #Normaliza coeficiente lider del denominador a 1
        den = den_work / den_work[0]
        
        if stype == SectionType.LOWPASS_2:
            # Sallen-Key Pasa Bajas - Diseño de igual C
            
            a1 = den[-2]
            a0 = den[-1]

            C = c_base
            P = 1.0 / (a0 * C**2) #Producto R1 y R2
            S = a1 / (a0 * C)     #Suma R1 y R2

            discriminant = max(S**2 - 4*P, 0.0) #Sujetar ruido numerico

            R1_ideal = (S + np.sqrt(discriminant)) / 2.0
            R2_ideal = (S - np.sqrt(discriminant)) / 2.0
            C1_ideal = C
            C2_ideal = C

            componentes_etapa = [
                ("R1", ComponentType.RESISTOR, R1_ideal),
                ("R2", ComponentType.RESISTOR, R2_ideal),
                ("C1", ComponentType.CAPACITOR, C1_ideal),
                ("C2", ComponentType.CAPACITOR, C2_ideal),
            ]

        elif stype == SectionType.HIGHPASS_2:
            # Sallen-Key Pasa Altas - Diseño de igual R
            
            a1 = den[-2]
            a0 = den[-1]

            R = r_base
            P = 1.0 / (a0 * R**2) #Producto C1 y C2
            S = a1 / (a0 * R)     #Suma C1 y C2

            discriminant = max(S**2 - 4*P, 0.0) 

            C1_ideal = (S + np.sqrt(discriminant)) / 2.0
            C2_ideal = (S - np.sqrt(discriminant)) / 2.0
            R1_ideal = R
            R2_ideal = R

            componentes_etapa = [
                ("R1", ComponentType.RESISTOR, R1_ideal),
                ("R2", ComponentType.RESISTOR, R2_ideal),
                ("C1", ComponentType.CAPACITOR, C1_ideal),
                ("C2", ComponentType.CAPACITOR, C2_ideal),
            ]

        elif stype == SectionType.BANDPASS:
            # Sallen-Key Pasa Bandas - Topologia de multiple retroalimentacion
            
            a1 = den[-2]
            a0 = den[-1]

            omega0 = np.sqrt(a0)
            Q = omega0 / a1 #Q = w0 / (w0/Q)

            C = c_base

            R1_ideal = Q / (omega0 * C) #Resistencia de entrada
            R2_ideal = 1.0 / (Q * omega0 *C) #Resistencia de retroalimentación
            C1_ideal = C
            C2_ideal = C

            componentes_etapa = [
                ("R1", ComponentType.RESISTOR, R1_ideal),
                ("R2", ComponentType.RESISTOR, R2_ideal),
                ("C1", ComponentType.CAPACITOR, C1_ideal),
                ("C2", ComponentType.CAPACITOR, C2_ideal),
            ]

        elif stype == SectionType.BANDSTOP:
            # Red Twin-T Rechaza-Banda
            
            a0 = den[-1]

            omega0 = np.sqrt(a0)
            R = r_base
            C = 1.0 / (omega0 * R) # Valor base de capacitor

            R1_ideal = R
            R2_ideal = R
            R3_ideal = R / 2.0 #Resistencia central = R/2
            C1_ideal = C
            C2_ideal = C
            C3_ideal = 2.0 * C #Capacitor central = 2C

            componentes_etapa = [
                ("R1", ComponentType.RESISTOR, R1_ideal),
                ("R2", ComponentType.RESISTOR, R2_ideal),
                ("R3", ComponentType.RESISTOR, R3_ideal),
                ("C1", ComponentType.CAPACITOR, C1_ideal),
                ("C2", ComponentType.CAPACITOR, C2_ideal),
                ("C3", ComponentType.CAPACITOR, C3_ideal),
            ]

        elif stype == SectionType.LOWPASS_1:
            # RC Pasa Bajas de primer orden + Seguidor de Tension
            
            a0 = den[-1]
            omega0 = a0

            C_ideal = c_base
            R_ideal = 1.0 / (omega0 * C_ideal)

            componentes_etapa = [
                ("R1", ComponentType.RESISTOR, R_ideal),
                ("C1", ComponentType.CAPACITOR, C_ideal),
            ]

        elif stype == SectionType.HIGHPASS_1:
            # RC Pasa Altas de primer orden + Seguidor de Tension
            
            a0 = den[-1]
            omega0 = a0

            R_ideal = r_base
            C_ideal = 1.0 / (omega0 * R_ideal)

            componentes_etapa = [
                ("R1", ComponentType.RESISTOR, R_ideal),
                ("C1", ComponentType.CAPACITOR, C_ideal),
            ]

        else:
            # Tipo de sección no soportado (ALLPASS, UNKNOWN) - Se omite 
            print(f" [Advertencia] Etapa {stage_num}: sección tipo '{stype.value}' "
                  f"no soportada, se omite.")
            continue

        # Redondea a sere E y registra cada componente
        for name, ctype, ideal_val in componentes_etapa:
            serie = r_series if ctype == ComponentType.RESISTOR else c_series
            rounded = round_to_eseries(ideal_val, serie)
            components.append(ComponentValue(
                stage = stage_num,
                name = name,
                component_type = ctype,
                ideal = ideal_val,
                rounded = rounded,
                error_pct = eseries_error_pct(ideal_val, rounded),
                section_type = stype,
                filter_type = ftype,
            ))

    return components

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

    components = []

    # Valores internos/fijos del UAF42 usados en el análisis:
    # R1 = R2 = R4 = R = 50kΩ
    # y se elige RG = RQ = R
    R_INTERNAL = 50e3
    C = c_base

    for stage_idx, biquad in enumerate(biquads):
        stage = stage_idx + 1
        den = np.asarray(biquad.denominator, dtype=float)

        # ─────────────────────────────────────────────────────────────
        # CASO A: sección de primer orden normal
        # den = [a0, a1] → a0*s + a1
        # ωc = a1/a0
        # ─────────────────────────────────────────────────────────────
        if len(den) == 2:
            a0, a1 = den

            if abs(a0) < 1e-12:
                print(f"debug stage {stage}: primer orden inválido, saltando")
                continue

            omega_c = abs(a1 / a0)

            CP = C
            RP = 1.0 / (omega_c * CP)

            CP_r = round_to_eseries(CP, c_series)
            RP_r = round_to_eseries(RP, r_series)

            for name, val, val_r, ctype in (
                ("CP", CP, CP_r, ComponentType.CAPACITOR),
                ("RP", RP, RP_r, ComponentType.RESISTOR),
            ):
                components.append(ComponentValue(
                    stage          = stage,
                    name           = name,
                    component_type = ctype,
                    ideal          = val,
                    rounded        = val_r,
                    error_pct      = eseries_error_pct(val, val_r),
                    section_type   = biquad.section_type,
                    filter_type    = biquad.filter_type,
                ))

            print(
                f"debug stage {stage}: 1er orden "
                f"ωc={omega_c:.2f} rad/s, "
                f"RP={RP:.2f}Ω, CP={CP:.2e}F"
            )

            continue

        # ─────────────────────────────────────────────────────────────
        # CASO B: sección de primer orden disfrazada
        # scipy.tf2sos puede devolver den = [0, a1, a2]
        # que equivale a a1*s + a2
        # ─────────────────────────────────────────────────────────────
        if len(den) == 3 and abs(den[0]) < 1e-12:
            a0, a1, a2 = den

            if abs(a1) < 1e-12:
                print(f"debug stage {stage}: sección degenerada, saltando")
                continue

            omega_c = abs(a2 / a1)

            CP = C
            RP = 1.0 / (omega_c * CP)

            CP_r = round_to_eseries(CP, c_series)
            RP_r = round_to_eseries(RP, r_series)

            for name, val, val_r, ctype in (
                ("CP", CP, CP_r, ComponentType.CAPACITOR),
                ("RP", RP, RP_r, ComponentType.RESISTOR),
            ):
                components.append(ComponentValue(
                    stage          = stage,
                    name           = name,
                    component_type = ctype,
                    ideal          = val,
                    rounded        = val_r,
                    error_pct      = eseries_error_pct(val, val_r),
                    section_type   = biquad.section_type,
                    filter_type    = biquad.filter_type,
                ))

            print(
                f"debug stage {stage}: 1er orden  "
                f"ωc={omega_c:.2f} rad/s, "
                f"RP={RP:.2f}Ω, CP={CP:.2e}F"
            )

            continue

        # ─────────────────────────────────────────────────────────────
        # CASO C: sección de segundo orden Tow-Thomas / UAF42
        # den = [a0, a1, a2] → a0*s² + a1*s + a2
        # normalizado:
        # s² + (ω0/Q)s + ω0²
        # ─────────────────────────────────────────────────────────────
        if len(den) == 3:
            a0, a1, a2 = den

            if abs(a0) < 1e-12 or abs(a1) < 1e-12:
                print(f"debug stage {stage}: sección de segundo orden inválida, saltando")
                continue

            omega_0 = np.sqrt(abs(a2 / a0))
            Q = np.sqrt(abs(a0 * a2)) / abs(a1)

            # Ecuaciones correctas con RG = RQ = R:
            # ω0/Q = 3/(2 C RF1)
            # ω0²  = 1/(C² RF1 RF2)
            RF1 = (3.0 * Q) / (2.0 * C * omega_0)
            RF2 = 2.0 / (3.0 * Q * C * omega_0)

            RG = R_INTERNAL
            RQ = R_INTERNAL

            RG_r  = round_to_eseries(RG,  r_series)
            RQ_r  = round_to_eseries(RQ,  r_series)
            RF1_r = round_to_eseries(RF1, r_series)
            RF2_r = round_to_eseries(RF2, r_series)

            for name, val, val_r in (
                ("RG",  RG,  RG_r),
                ("RQ",  RQ,  RQ_r),
                ("RF1", RF1, RF1_r),
                ("RF2", RF2, RF2_r),
            ):
                components.append(ComponentValue(
                    stage          = stage,
                    name           = name,
                    component_type = ComponentType.RESISTOR,
                    ideal          = val,
                    rounded        = val_r,
                    error_pct      = eseries_error_pct(val, val_r),
                    section_type   = biquad.section_type,
                    filter_type    = biquad.filter_type,
                ))

            print(
                f"debug stage {stage}: Tow-Thomas "
                f"type={biquad.section_type.value}, "
                f"ω0={omega_0:.2f} rad/s, "
                f"f0={omega_0/(2*np.pi):.2f} Hz, "
                f"Q={Q:.4f}, "
                f"RG={RG:.2f}Ω, RQ={RQ:.2f}Ω, "
                f"RF1={RF1:.2f}Ω, RF2={RF2:.2f}Ω"
            )

            continue

    return components

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
    ── STUDENT CODE (partially implemented below) ──
    Inspect biquad.section_type:
      SectionType.BANDPASS   → classic 2-R 2-C Deliyannis-Friend BP topology
      SectionType.LOWPASS_2  → Friend LP variant (5 components: 3R 2C)
      Other types are not directly realisable with this topology — skip or raise.
    The Friend bandpass biquad (K=1):
        C₁ = C₂ = C
        R₁ = 1 / (ω₀ · C · (2Q - 1))
        R₂ = Q / (ω₀ · C)
    Refer to Deliyannis (1968) and Wai-Kai Chen "Active Network Analysis" Ch. 6.
    """
    components = []  # lista donde acumulamos todos los componentes

    for stage_idx, biquad in enumerate(biquads):
        stage = stage_idx + 1
        den = np.asarray(biquad.denominator, dtype=float)

        # ─────────────────────────────────────────────────────────────────────
        # CASO A: SECCIÓN DE PRIMER ORDEN (den tiene 2 coeficientes: [a0, a1])
        #
        # Ocurre cuando el filtro es de orden impar la sección sobrante
        # es de primer orden. Se realiza con un simple RC:
        #   H(s) = ωc / (s + ωc)   donde ωc = a1/a0
        #   C = c_base,  R = 1/(ωc·C)
        # ─────────────────────────────────────────────────────────────────────
        if len(den) == 2:
            a0, a1 = den

            if abs(a0) < 1e-12:
                print(f"debug stage {stage}: primer orden inválido, saltando")
                continue

            omega_c = abs(a1 / a0)   # frecuencia de corte de la sección

            C   = c_base
            C_r = round_to_eseries(C, c_series)
            R   = 1.0 / (omega_c * C)
            R_r = round_to_eseries(R, r_series)

            components.append(ComponentValue(
                stage          = stage,
                name           = "C1",
                component_type = ComponentType.CAPACITOR,
                ideal          = C,
                rounded        = C_r,
                error_pct      = eseries_error_pct(C, C_r),
                section_type   = biquad.section_type,
                filter_type    = biquad.filter_type,
            ))
            components.append(ComponentValue(
                stage          = stage,
                name           = "R1",
                component_type = ComponentType.RESISTOR,
                ideal          = R,
                rounded        = R_r,
                error_pct      = eseries_error_pct(R, R_r),
                section_type   = biquad.section_type,
                filter_type    = biquad.filter_type,
            ))

            print(f"debug stage {stage}: 1er orden ωc={omega_c:.2f} rad/s, "
                  f"R={R:.2f}Ω, C={C:.2e}F")
            continue   # pasar al siguiente biquad

        # ─────────────────────────────────────────────────────────────────────
        # CASO B: SECCIÓN DE SEGUNDO ORDEN (den tiene 3 coeficientes)
        # ─────────────────────────────────────────────────────────────────────
        if len(den) < 3:
            print(f"debug stage {stage}: sección no reconocida, saltando")
            continue

        a0, a1, a2 = den[0], den[1], den[2]

        # Caso especial: a0≈0 puede ser sección de primer orden disfrazada
        # den=[0, a1, a2] equivale a s + a2/a1
        if abs(a0) < 1e-12:
            if abs(a1) > 1e-12:
                omega_c = abs(a2 / a1)
                C   = c_base
                C_r = round_to_eseries(C, c_series)
                R   = 1.0 / (omega_c * C)
                R_r = round_to_eseries(R, r_series)
                components.append(ComponentValue(
                    stage          = stage,
                    name           = "C1",
                    component_type = ComponentType.CAPACITOR,
                    ideal          = C,
                    rounded        = C_r,
                    error_pct      = eseries_error_pct(C, C_r),
                    section_type   = biquad.section_type,
                    filter_type    = biquad.filter_type,
                ))
                components.append(ComponentValue(
                    stage          = stage,
                    name           = "R1",
                    component_type = ComponentType.RESISTOR,
                    ideal          = R,
                    rounded        = R_r,
                    error_pct      = eseries_error_pct(R, R_r),
                    section_type   = biquad.section_type,
                    filter_type    = biquad.filter_type,
                ))
                print(f"debug stage {stage}: 1er orden (disfrazado) ωc={omega_c:.2f} rad/s, "
                      f"R={R:.2f}Ω, C={C:.2e}F")
            else:
                print(f"debug stage {stage}: sección degenerada, saltando")
            continue

        # Extraer ω₀ y Q del denominador normalizado s² + (ω₀/Q)s + ω₀²
        # Comparando con a0·s² + a1·s + a2:
        #   ω₀ = sqrt(a2/a0)
        #   Q  = sqrt(a0·a2) / a1
        omega_0 = np.sqrt(abs(a2 / a0))
        Q       = np.sqrt(abs(a0 * a2)) / abs(a1)

        C   = c_base
        C_r = round_to_eseries(C, c_series)

        # ─────────────────────────────────────────────────────────────────────
        # CASO B.1: Q ≤ 0.5 → polos reales, descomponer en dos RC de 1er orden
        #
        # Cuando Q es bajo los polos del denominador son reales (no complejos).
        # np.roots() los encuentra directamente.
        # Cada polo real p_i , sección RC con ωc = |Re(p_i)|, R = 1/(ωc·C)
        # ─────────────────────────────────────────────────────────────────────
        if Q <= 0.5:
            poles = np.roots(den)
            print(f"debug stage {stage}: Q={Q:.3f} ≤ 0.5 → polos reales")

            for i, p in enumerate(poles, start=1):
                if np.real(p) >= 0:   # descartar polos inestables
                    continue

                omega_c = abs(np.real(p))
                R       = 1.0 / (omega_c * C)
                R_r     = round_to_eseries(R, r_series)

                components.append(ComponentValue(
                    stage          = stage,
                    name           = f"C{i}",
                    component_type = ComponentType.CAPACITOR,
                    ideal          = C,
                    rounded        = C_r,
                    error_pct      = eseries_error_pct(C, C_r),
                    section_type   = biquad.section_type,
                    filter_type    = biquad.filter_type,
                ))
                components.append(ComponentValue(
                    stage          = stage,
                    name           = f"R{i}",
                    component_type = ComponentType.RESISTOR,
                    ideal          = R,
                    rounded        = R_r,
                    error_pct      = eseries_error_pct(R, R_r),
                    section_type   = biquad.section_type,
                    filter_type    = biquad.filter_type,
                ))
            continue   # stage ya procesado, siguiente biquad

        # ─────────────────────────────────────────────────────────────────────
        # CASO B.2: BANDPASS  topología clásica Deliyannis-Friend BP
        #
        # Del documento de topologias y funciones de transferencia (MFB con Y2=∅, Y3=sC, Y4=sC, Y1=G1, Y5=G5):
        #   H(s) = -Y1·Y3 / ((Y1+Y3+Y4)·Y5 + Y3·Y4)
        #
        # Con C3=C4=C e igualando con forma estándar s²+(ω₀/Q)s+ω₀²:
        #   ω₀² = G1·G5/C² , GG5 = ω₀·C/(2Q) ,   R5 = 2Q/(ω₀·C)
        #   ω₀/Q = 2G5/C     , G1 = 2Q·ω₀·C   ,→  R1 = 1/(2Q·ω₀·C)
        #
        # C1=C2=C (los dos capacitores son iguales)
        # ─────────────────────────────────────────────────────────────────────
        if biquad.section_type == SectionType.BANDPASS:

            R1   = 1.0 / (2.0 * Q * omega_0 * C)   # resistor de entrada
            R2   = (2.0 * Q) / (omega_0 * C)        # resistor de realimentación
            R1_r = round_to_eseries(R1, r_series)
            R2_r = round_to_eseries(R2, r_series)

            for name, val, val_r, ctype in (
                ("C1", C,  C_r,  ComponentType.CAPACITOR),
                ("C2", C,  C_r,  ComponentType.CAPACITOR),
                ("R1", R1, R1_r, ComponentType.RESISTOR),
                ("R2", R2, R2_r, ComponentType.RESISTOR),
            ):
                components.append(ComponentValue(
                    stage          = stage,
                    name           = name,
                    component_type = ctype,
                    ideal          = val,
                    rounded        = val_r,
                    error_pct      = eseries_error_pct(val, val_r),
                    section_type   = biquad.section_type,
                    filter_type    = biquad.filter_type,
                ))

            print(f"debug stage {stage}: BP ω₀={omega_0:.2f} rad/s, Q={Q:.4f}, "
                  f"R1={R1:.2f}Ω, R2={R2:.2f}Ω, C={C:.2e}F")

        # ─────────────────────────────────────────────────────────────────────
        # CASO B.3: LOWPASS variante Friend LP (3R 2C)
        #
        # Del documento de topologias y funciones d etrasnferencia (MFB con Y1=G1, Y2=sC, Y3=G3, Y4=G4, Y5=sC):
        #   H(s) = -Y1·Y3 / ((Y1+Y2+Y3+Y4)·Y5 + Y3·Y4)
        #
        # Con C2=C5=C y R3=R4=R (resistores iguales):
        #   ω₀ = 1/(R·C)  →  R3=R4 = 1/(ω₀·C)
        #   Q = R1/(2R) + 0.5  →  R1 = (2Q-1)·R = (2Q-1)/(ω₀·C)
        #
        # Requiere Q > 0.5 para que R1 > 0.
        # 5 componentes totales: C1, C2, R1, R2, R3
        # ─────────────────────────────────────────────────────────────────────
        elif biquad.section_type == SectionType.LOWPASS_2:

            R1   = (2.0*Q - 1.0) / (omega_0 * C)   # resistor de entrada
            R2   = 1.0 / (omega_0 * C)              # R3=R4 iguales (resistores de la red)
            R3   = 1.0 / (omega_0 * C)              # mismo valor que R2
            R1_r = round_to_eseries(R1, r_series)
            R2_r = round_to_eseries(R2, r_series)
            R3_r = round_to_eseries(R3, r_series)

            for name, val, val_r, ctype in (
                ("C1", C,  C_r,  ComponentType.CAPACITOR),
                ("C2", C,  C_r,  ComponentType.CAPACITOR),
                ("R1", R1, R1_r, ComponentType.RESISTOR),
                ("R2", R2, R2_r, ComponentType.RESISTOR),
                ("R3", R3, R3_r, ComponentType.RESISTOR),
            ):
                components.append(ComponentValue(
                    stage          = stage,
                    name           = name,
                    component_type = ctype,
                    ideal          = val,
                    rounded        = val_r,
                    error_pct      = eseries_error_pct(val, val_r),
                    section_type   = biquad.section_type,
                    filter_type    = biquad.filter_type,
                ))

            print(f"debug stage {stage}: LP ω₀={omega_0:.2f} rad/s, Q={Q:.4f}, "
                  f"R1={R1:.2f}Ω, R2=R3={R2:.2f}Ω, C={C:.2e}F")

        else:
            print(f"debug stage {stage}: section_type={biquad.section_type} "
                  f"no implementado en Deliyannis, saltando")

    return components    

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
    Instructor-provided — do NOT modify.
    """
    # Group components by stage, keyed by component name
    stages: dict[int, dict[str, ComponentValue]] = {}
    for c in components:
        stages.setdefault(c.stage, {})[c.name] = c

    n_stages              = len(stages)
    opamp, lib, op_tmpl   = _opamp_subckt(ic_model)

    # For UAF42 topology, the summing amp uses the internal AMP_UAF subcircuit
    # (pinout: non_inv  inv  V+  V-  out — same as a regular op-amp)
    _aux_tmpl = op_tmpl or "X_{tag}  {n}  {i}  {p}  {m}  {o}  AMP_UAF"

    def opamp_line(tag, n, i, o):
        """Render an op-amp instance with the correct pin order for this model."""
        return _opamp_instance(_aux_tmpl, tag, n, i, o)

    lines = [
        f"* Analog Filter — {topology.name}  IC: {ic_model}",
        f".include {lib}",
        "",
        "* Supply rails",
        "Vcc  vcc  0  DC  15",
        "Vee  vee  0  DC -15",
        "",
        "* AC input source",
        "Vin  n_in  0  AC 1  DC 0",
        "",
    ]

    match topology:

        # ── Sallen-Key ────────────────────────────────────────────────────────
        case Topology.SALLEN_KEY:
            for s, comps in stages.items():
                stype = next(iter(comps.values())).section_type
                n_in  = "n_in" if s == 1 else f"n_s{s-1}_out"
                n_out = f"n_s{s}_out"
                n_mid = f"n_s{s}_mid"
                lines.append(f"* ── Stage {s}  [{stype.value}] ──────────────")

                if stype in (SectionType.LOWPASS_2, SectionType.BANDPASS):
                    r1, r2 = comps["R1"].rounded, comps["R2"].rounded
                    c1, c2 = comps["C1"].rounded, comps["C2"].rounded
                    lines += [
                        f"R1_{s}  {n_in}   {n_mid}  {r1:.6g}",
                        f"R2_{s}  {n_mid}  {n_out}  {r2:.6g}",
                        f"C1_{s}  {n_mid}  0        {c1:.6g}",
                        f"C2_{s}  {n_out}  {n_mid}  {c2:.6g}",
                        opamp_line(f"U{s}", n_out, n_out, n_out),
                    ]
                elif stype == SectionType.HIGHPASS_2:
                    r1, r2 = comps["R1"].rounded, comps["R2"].rounded
                    c1, c2 = comps["C1"].rounded, comps["C2"].rounded
                    lines += [
                        f"C1_{s}  {n_in}   {n_mid}  {c1:.6g}",
                        f"C2_{s}  {n_mid}  {n_out}  {c2:.6g}",
                        f"R1_{s}  {n_mid}  0        {r1:.6g}",
                        f"R2_{s}  {n_out}  {n_mid}  {r2:.6g}",
                        opamp_line(f"U{s}", n_out, n_out, n_out),
                    ]
                elif stype == SectionType.BANDSTOP:
                    r1, r2, r3 = comps["R1"].rounded, comps["R2"].rounded, comps["R3"].rounded
                    c1, c2, c3 = comps["C1"].rounded, comps["C2"].rounded, comps["C3"].rounded
                    n_tee = f"n_s{s}_tee"
                    lines += [
                        f"R1_{s}  {n_in}   {n_tee}  {r1:.6g}",
                        f"R2_{s}  {n_tee}  {n_out}  {r2:.6g}",
                        f"C1_{s}  {n_in}   {n_tee}  {c1:.6g}",
                        f"C2_{s}  {n_tee}  {n_out}  {c2:.6g}",
                        f"R3_{s}  {n_tee}  0        {r3:.6g}",
                        f"C3_{s}  {n_tee}  0        {c3:.6g}",
                        opamp_line(f"U{s}", n_out, n_out, n_out),
                    ]
                elif stype in (SectionType.LOWPASS_1, SectionType.HIGHPASS_1):
                    r1, c1 = comps["R1"].rounded, comps["C1"].rounded
                    if stype == SectionType.LOWPASS_1:
                        lines += [
                            f"R1_{s}  {n_in}   {n_mid}  {r1:.6g}",
                            f"C1_{s}  {n_mid}  0        {c1:.6g}",
                        ]
                    else:
                        lines += [
                            f"C1_{s}  {n_in}   {n_mid}  {c1:.6g}",
                            f"R1_{s}  {n_mid}  0        {r1:.6g}",
                        ]
                    lines.append(opamp_line(f"U{s}", n_mid, n_out, n_out))
                else:
                    lines.append(f"* Stage {s}: {stype.value} not supported for SK — skipped")
                lines.append("")

        # ── Tow-Thomas / UAF42 ────────────────────────────────────────────────
        case Topology.TOW_THOMAS:
            for s, comps in stages.items():
                stype = next(iter(comps.values())).section_type
                n_in  = "n_in" if s == 1 else f"n_s{s-1}_out"
                n_lp  = f"n_s{s}_lp"
                n_bp  = f"n_s{s}_bp"
                n_hp  = f"n_s{s}_hp"
                n_out = f"n_s{s}_out"
                # Aux amp nodes (pins 4, 5, 6 of UAF42)
                n_aux_ni  = f"n_s{s}_aux_ni"   # pin 4 non-inv input
                n_aux_inv = f"n_s{s}_aux_inv"  # pin 5 inv input
                n_aux_out = f"n_s{s}_aux_out"  # pin 6 output
                lines.append(f"* ── Stage {s}  [{stype.value}] ──────────────")

                if stype in (SectionType.LOWPASS_1, SectionType.HIGHPASS_1):
                    # Odd-order first-order section — use UAF42 aux amp as follower
                    # Wire RC to aux amp non-inv input; connect inv to output (follower)
                    rp = (comps.get("RP") or comps.get("R1")).rounded
                    cp = (comps.get("CP") or comps.get("C1")).rounded
                    n_rc = f"n_s{s}_rc"
                    if stype == SectionType.LOWPASS_1:
                        lines += [
                            f"R1_{s}  {n_in}  {n_rc}  {rp:.6g}",
                            f"C1_{s}  {n_rc}  0       {cp:.6g}",
                        ]
                    else:
                        lines += [
                            f"C1_{s}  {n_in}  {n_rc}  {cp:.6g}",
                            f"R1_{s}  {n_rc}  0       {rp:.6g}",
                        ]
                    lines += [
                        f"* UAF42 aux amp as voltage follower (pins 4,5,6)",
                        f"* pin1=LP pin4=aux_ni pin5=aux_inv pin6=aux_out",
                        f"* pin7=BP pin9=V- pin10=V+ pin13=HP",
                        f"X_U{s}  {n_lp}  0  0  {n_rc}  {n_aux_inv}  {n_aux_out}  {n_bp}  0  vee  vcc  0  0  {n_hp}  0  UAF42",
                        f"* aux amp follower: inv tied to output",
                        f"Rfb_{s}  {n_aux_out}  {n_aux_inv}  0",
                        f"Vwire_{s}  {n_aux_out}  {n_out}  DC 0",
                    ]

                else:
                    rg  = comps["RG"].rounded
                    rf1 = comps["RF1"].rounded
                    rf2 = comps["RF2"].rounded
                    rq  = comps["RQ"].rounded
                    tap = {"LP2": n_lp, "BP": n_bp, "HP2": n_hp}.get(stype.value, n_lp)

                    if stype == SectionType.BANDSTOP:
                        # BS: use aux amp to sum LP + HP outputs
                        # Aux amp non-inv = 0 (GND), inv = summing node, out = n_out
                        r_sum = 10e3
                        n_sum = f"n_s{s}_sum"
                        lines += [
                            f"* UAF42: pin1=LP pin4=aux_ni pin5=aux_inv pin6=aux_out",
                            f"* pin7=BP pin9=V- pin10=V+ pin13=HP",
                            f"X_U{s}  {n_lp}  0  0  0  {n_sum}  {n_aux_out}  {n_bp}  {rq:.6g}  vee  vcc  0  {n_in}  {n_hp}  {rf1:.6g}  UAF42",
                            f"* BS: sum LP + HP into aux amp inverting input",
                            f"Rsum1_{s}  {n_lp}  {n_sum}  {r_sum:.6g}",
                            f"Rsum2_{s}  {n_hp}  {n_sum}  {r_sum:.6g}",
                            f"Rfb_{s}    {n_aux_out}  {n_sum}  {r_sum:.6g}",
                            f"Vwire_{s}  {n_aux_out}  {n_out}  DC 0",
                        ]
                    else:
                        # Standard LP / BP / HP — aux amp pins left unconnected (to 0)
                        lines += [
                            f"* UAF42: pin1=LP pin4=aux_ni pin5=aux_inv pin6=aux_out",
                            f"* pin7=BP pin9=V- pin10=V+ pin13=HP",
                            f"X_U{s}  {n_lp}  0  0  0  0  0  {n_bp}  {rq:.6g}  vee  vcc  0  {n_in}  {n_hp}  {rf1:.6g}  UAF42",
                            f"Vwire_{s}  {tap}  {n_out}  DC 0",
                        ]
                lines.append("")

        # ── Deliyannis-Friend ─────────────────────────────────────────────────
        case Topology.DELIYANNIS:
            for s, comps in stages.items():
                stype = next(iter(comps.values())).section_type
                n_in  = "n_in" if s == 1 else f"n_s{s-1}_out"
                n_out = f"n_s{s}_out"
                n_mid = f"n_s{s}_mid"
                n_inv = f"n_s{s}_inv"
                lines.append(f"* ── Stage {s}  [{stype.value}] ──────────────")

                if len(comps) == 2:
                    # First-order RC
                    r = (comps.get("R") or comps.get("R1")).rounded
                    c = (comps.get("C") or comps.get("C1")).rounded
                    n_rc = f"n_s{s}_rc"
                    lines += [
                        f"R1_{s}  {n_in}  {n_rc}  {r:.6g}",
                        f"C1_{s}  {n_rc}  0       {c:.6g}",
                        opamp_line(f"U{s}", n_rc, n_out, n_out),
                    ]
                elif stype == SectionType.BANDPASS:
                    r1, r2 = comps["R1"].rounded, comps["R2"].rounded
                    c1, c2 = comps["C1"].rounded, comps["C2"].rounded
                    lines += [
                        f"R1_{s}  {n_in}   {n_mid}  {r1:.6g}",
                        f"C1_{s}  {n_mid}  {n_out}  {c1:.6g}",
                        f"C2_{s}  {n_mid}  0        {c2:.6g}",
                        f"R2_{s}  {n_out}  {n_inv}  {r2:.6g}",
                        opamp_line(f"U{s}", "0", n_inv, n_out),
                    ]
                elif stype == SectionType.LOWPASS_2:
                    r1, r2, r3 = comps["R1"].rounded, comps["R2"].rounded, comps["R3"].rounded
                    c1, c2     = comps["C1"].rounded, comps["C2"].rounded
                    lines += [
                        f"R1_{s}  {n_in}   {n_mid}  {r1:.6g}",
                        f"R2_{s}  {n_mid}  {n_inv}  {r2:.6g}",
                        f"R3_{s}  {n_mid}  {n_inv}  {r3:.6g}",
                        f"C1_{s}  {n_mid}  0        {c1:.6g}",
                        f"C2_{s}  {n_inv}  {n_out}  {c2:.6g}",
                        opamp_line(f"U{s}", "0", n_inv, n_out),
                    ]
                else:
                    lines.append(f"* Stage {s}: {stype.value} not supported for Deliyannis — skipped")
                lines.append("")

        case _:
            raise ValueError(f"Unknown topology: {topology}")

    lines += [
        "* AC sweep",
        ".ac  dec  100  1  10Meg",
        f".probe  V(n_s{n_stages}_out)",
        "",
        ".end",
    ]

    return "\n".join(lines)


def _opamp_subckt(ic_model: str) -> tuple[str, str, str]:
    """
    Map GUI model name → (SPICE subcircuit name, .mod filepath, pin_order).
    Instructor-provided — do NOT modify.

    pin_order is the ngspice instantiation template:
        '{n}' = non-inverting input node
        '{i}' = inverting input node
        '{o}' = output node
        '{p}' = positive supply node
        '{m}' = negative supply node

    LM741/NS pinout: non_inv  inv  V+   V-   out   → 1 2 99 50 28
    TL081    pinout: non_inv  inv  V+   V-   out   → 1 2 3  4  5
    UAF42    pinout: 14-pin IC — handled separately in generate_spice_netlist
    """
    _MODELS = {
        "LM741":              ("LM741/NS", "resources/spice_models/lm741.mod",
                               "X_{tag}  {n}  {i}  {p}  {m}  {o}  LM741/NS"),
        "TL081":              ("TL081",    "resources/spice_models/tl081.mod",
                               "X_{tag}  {n}  {i}  {p}  {m}  {o}  TL081"),
        "UAF42 (Burr-Brown)": ("UAF42",   "resources/spice_models/uaf42.mod",
                               None),   # UAF42 handled separately
    }
    return _MODELS.get(ic_model, _MODELS["LM741"])


def _opamp_instance(template: str, tag: str, n: str, i: str, o: str,
                    p: str = "vcc", m: str = "vee") -> str:
    """
    Render an op-amp instance line from the template in _opamp_subckt.
    tag  = unique instance tag e.g. 'U1', 'Usum2'
    n    = non-inverting input node
    i    = inverting input node
    o    = output node
    p, m = positive / negative supply nodes
    """
    return template.format(tag=tag, n=n, i=i, o=o, p=p, m=m)
    """
    Locate the ngspice executable, searching conda prefix and common system paths.
    Instructor-provided — do NOT modify.
    """
    import shutil, sys, os
    found = shutil.which("ngspice")
    if found:
        return found
    prefix = sys.prefix
    candidates = [
        os.path.join(prefix, "bin", "ngspice"),
        os.path.join(prefix, "Library", "bin", "ngspice.exe"),
        os.path.join(prefix, "Scripts", "ngspice.exe"),
        "/usr/bin/ngspice",
        "/usr/local/bin/ngspice",
        "/opt/homebrew/bin/ngspice",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return "ngspice"   # last resort — let SpiceServer raise a clear error


def _find_ngspice() -> str:
    """
    Locate the ngspice executable, searching conda prefix and common system paths.
    Instructor-provided — do NOT modify.
    """
    import shutil, sys, os
    found = shutil.which("ngspice")
    if found:
        return found
    prefix = sys.prefix
    candidates = [
        os.path.join(prefix, "bin", "ngspice"),
        os.path.join(prefix, "Library", "bin", "ngspice.exe"),
        os.path.join(prefix, "Scripts", "ngspice.exe"),
        "/usr/bin/ngspice",
        "/usr/local/bin/ngspice",
        "/opt/homebrew/bin/ngspice",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return "ngspice"   # last resort


def run_spice_simulation(netlist: str) -> SimulationResult:
    """
    Execute an AC simulation via ngspice and return the results.
    Instructor-provided — do NOT modify.

    Runs ngspice in server mode (-s), strips any preamble warnings from
    stdout, then parses the binary raw data with PySpice's NgSpice.RawFile.

    Requires ngspice to be installed and findable by _find_ngspice().
    """
    import subprocess, re
    from PySpice.Spice.NgSpice.RawFile import RawFile as NgRawFile

    # ── Extract output node from last .probe V(...) line ─────────────────────
    probe_node = None
    for line in netlist.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith(".probe") and "v(" in stripped:
            start      = stripped.index("v(") + 2
            end        = stripped.index(")", start)
            probe_node = stripped[start:end]

    if probe_node is None:
        raise ValueError("No .probe V(...) line found in netlist.")

    # ── Run ngspice -s (server / batch stdin mode) ────────────────────────────
    ngspice = _find_ngspice()
    process = subprocess.Popen(
        [ngspice, "-s"],
        stdin  = subprocess.PIPE,
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = process.communicate(
        input=netlist.encode("utf-8"), timeout=60
    )
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")

    # ── Extract number_of_points from stderr ──────────────────────────────────
    # ngspice server mode outputs  "@@@ <something> <number_of_points>"
    # e.g.  "@@@ 149 701"
    number_of_points = None
    for line in stderr_text.splitlines():
        line = line.strip()
        if line.startswith("@@@"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    number_of_points = int(parts[-1])
                    break
                except ValueError:
                    pass

    # Fallback: also accept "N points" style (older ngspice versions)
    if number_of_points is None:
        m = re.search(r"(\d+)\s+point", stderr_text, re.IGNORECASE)
        if m:
            number_of_points = int(m.group(1))

    if number_of_points is None:
        raise NameError(
            "ngspice did not report the number of points.\n"
            f"ngspice stderr:\n{stderr_text}"
        )

    # ── Strip preamble and filter unexpected header lines ────────────────────
    # ngspice may emit extra lines (warnings, gmin notes, trtol messages)
    # before and inside the raw header. PySpice's NgRawFile parser is strict
    # and sequential, so we must keep only the lines it expects.
    circuit_marker = b"Circuit:"
    binary_marker  = b"Binary:"
    idx = stdout_bytes.find(circuit_marker)
    if idx < 0:
        raise RuntimeError(
            "Could not find 'Circuit:' header in ngspice output.\n"
            f"ngspice stderr:\n{stderr_text}\n"
            f"stdout (first 500 bytes): {stdout_bytes[:500]}"
        )

    # Split into header text and binary data
    binary_idx   = stdout_bytes.find(binary_marker, idx)
    header_bytes = stdout_bytes[idx:binary_idx]
    binary_bytes = stdout_bytes[binary_idx:]

    # Keep only lines that NgRawFile expects — filter everything else out
    _EXPECTED = (
        b"Circuit:", b"Doing analysis at TEMP", b"Warning",
        b"Title:", b"Date:", b"Plotname:", b"Flags:",
        b"No. Variables:", b"No. Points:", b"Variables:",
        b"No. of Data Columns",
    )
    filtered_lines = []
    in_variables_section = False
    for line in header_bytes.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith(b"No. of Data Columns") or \
           stripped.startswith(b"Variables:"):
            in_variables_section = True
        if in_variables_section or any(stripped.startswith(e) for e in _EXPECTED):
            filtered_lines.append(line)
        # Variable table rows start with whitespace + index number
        elif in_variables_section and (stripped[:1].isdigit() or line[:1] == b'\t'):
            filtered_lines.append(line)

    clean_stdout = b"".join(filtered_lines) + binary_bytes

    # ── Monkey-patch PySpice for NumPy 2.x compatibility ─────────────────────
    # PySpice 1.5 uses np.fromstring (removed in NumPy 2.x); patch it once.
    from PySpice.Spice.RawFile import RawFileAbc
    if not getattr(RawFileAbc, '_numpy2_patched', False):
        def _read_variable_data_patched(self, raw_data):
            if self.flags == 'real':
                number_of_columns = self.number_of_variables
            elif self.flags == 'complex':
                number_of_columns = 2 * self.number_of_variables
            else:
                raise NotImplementedError
            input_data = np.frombuffer(raw_data,
                                       count=number_of_columns * self.number_of_points,
                                       dtype='f8')
            input_data = input_data.reshape((self.number_of_points, number_of_columns))
            input_data = input_data.transpose()
            if self.flags == 'complex':
                raw_d = input_data
                input_data = np.array(raw_d[0::2], dtype='complex128')
                input_data.imag = raw_d[1::2]
            for variable in self.variables.values():
                variable.data = input_data[variable.index]

        RawFileAbc._read_variable_data = _read_variable_data_patched
        RawFileAbc._numpy2_patched = True

    # ── Parse the raw output ──────────────────────────────────────────────────
    raw = NgRawFile(clean_stdout, number_of_points)

    # ── Extract results directly from raw.variables ───────────────────────────
    # to_analysis() requires a Circuit object we don't have, so we read
    # the parsed variable data directly instead.

    # Frequency axis — always stored as variable named 'frequency'
    freq_var = raw.variables.get('frequency')
    if freq_var is None:
        available = list(raw.variables.keys())
        raise RuntimeError(
            f"'frequency' variable not found in raw output.\n"
            f"Available variables: {available}"
        )
    frequencies = np.real(np.array(freq_var.data)).astype(float)

    # Output voltage — node names are lower-case in the raw file
    v_out = None
    for name, var in raw.variables.items():
        if name.lower() in (probe_node.lower(), f"v({probe_node.lower()})"):
            v_out = np.array(var.data)
            break

    if v_out is None:
        available = list(raw.variables.keys())
        raise KeyError(
            f"Node '{probe_node}' not found in simulation results.\n"
            f"Available nodes: {available}"
        )

    magnitude_db = 20.0 * np.log10(np.abs(v_out) + 1e-300)
    phase_deg    = np.degrees(np.unwrap(np.angle(v_out)))

    return SimulationResult(
        frequencies  = frequencies,
        magnitude_db = magnitude_db,
        phase_deg    = phase_deg,
    )


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
