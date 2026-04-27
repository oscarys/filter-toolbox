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
    stage        : int
    name         : str              # e.g. "R1", "C2"
    component_type: ComponentType   # RESISTOR or CAPACITOR
    ideal        : float            # Ohms or Farads
    rounded      : float            # nearest E-series value
    error_pct    : float

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

    # TRANSFORMACION DE FRECUENCIA LP a {LP,HP,BP,BS}, AQUI SE OBTIENEN FRECUENCIAS DE CORTE 
    # Usamos z,p,k en lugar de polinomios para hacerlo mas estable con ordenes altos
    # lp2lp_zpk: escala la frecuencia de 1 rad/s a omega_p real
    # lp2hp_zpk: invierte el eje de frecuencias y escala a omega_p
    # lp2bp_zpk: abre la banda alrededor de omega_0 con ancho BW
    # lp2bs_zpk: inverso del BP ,  rechazo en el centro

    match spec.filter_type : 
    	case FilterType.LOWPASS: 
    # Frecuencia de corte: omega_p del usuario
    		z, p, k = sps.lp2lp_zpk(z, p, k, wo=spec.omega_p)

    	case FilterType.HIGHPASS:
    # Frecuencia de giro: omega_p. scipy hace s a omega_p/s internamente,
    # que es la inversión del eje de frecuencias que ya vimos en el orden.
    		z, p, k = sps.lp2hp_zpk(z, p, k, wo=spec.omega_p)

    	case FilterType.BANDPASS:
    # Necesitamos la frecuencia central geométrica "(f0) es el punto central de una banda de paso 
    # calculado mediante la media geométrica de las frecuencias límite inferior (f1) y superior (f2)
    # A diferencia de una media aritmética simple, la media geométrica proporciona un valor intermedio proporcional en escalas logarítmicas
    # lo que la hace fundamental para el diseño de filtros y el análisis de espectro y el ancho de banda."
    # Se usa geométrica porque el filtro es simétrico en escala logarítmica.
    		omega_0 = np.sqrt(spec.omega_p * spec.omega_p2)  # frec. central
    		BW = spec.omega_p2 - spec.omega_p            # ancho de banda
    		z, p, k = sps.lp2bp_zpk(z, p, k, wo=omega_0, bw=BW)

    	case FilterType.BANDSTOP:
    # Mismo cálculo de omega_0 y BW que BP,
    # pero la transformación pone el rechazo en el centro.
    		omega_0 = np.sqrt(spec.omega_p * spec.omega_p2)
    		BW = spec.omega_p2 - spec.omega_p
    		z, p, k = sps.lp2bs_zpk(z, p, k, wo=omega_0, bw=BW)

    


    # Calcula los polinomios normalizados de la función de transferencia
    # Convertir ZPK a coeficientes de polinomio 
    # zpk2tf convierte zeros,polos,ganancia a coeficientes num/den en orden
    # descendente de potencias: [b_n, b_{n-1}, b_0] / [a_n, a_0]
    # np.real() elimina la parte imaginaria residual de punto flotante (~1e-16).
    # Los coeficientes deben ser reales porque los polos complejos siempre son pares conjugados.
    num, den = sps.zpk2tf(z, p, k)

    # Transformación del filtro pasabajas a su tipo final:
    # match spec.filter_type:
    #    case FilterType.LOWPASS:  b, a = sps.lp2lp(nb, na)
    #    case FilterType.HIGHPASS: b, a = sps.lp2hp(nb, na)
    #    case FilterType.BANDPASS: b, a = sps.lp2bp(nb, na)
    #    case FilterType.BANDSTOP: b, a = sps.lp2bs(nb, na)

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

    print(f'debug: orden={n}, polos={p}')

    # Crea el objeto para la fucnión de transferencia
    # tf = TransferFunction(nb, na)
           
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
     
    # Factoriza en secciones analógicas de primer y segundo orden 
    sos = sps.tf2sos(tf.numerator, tf.denominator, analog=True)

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
        print(f"debug biquad {i+1}: section_type={s.section_type.value}  "
              f"filter_type={s.filter_type.name}  "
              f"num={np.round(s.numerator,4)}  den={np.round(s.denominator,4)}")

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
    Inspect biquad.section_type for each stage:
      SectionType.LOWPASS_2  → tap LP output of UAF42
      SectionType.BANDPASS   → tap BP output of UAF42
      SectionType.HIGHPASS_2 → tap HP output of UAF42
      SectionType.BANDSTOP   → sum LP and HP outputs externally
    For each biquad:
        C₁ = C₂ = C  (user base value)
        R₁ = R₂ = 1 / (ω₀ · C)
        R_q = Q / (ω₀ · C)   (Q-setting resistor)
    Refer to the Burr-Brown UAF42 datasheet for full design equations.
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
        den = biquad.denominator  # coeficientes [a0, a1, a2] del denominador

        # Verificar que es una sección de segundo orden 
        # Deliyannis-Friend solo aplica a biquads de 2do orden (bandpass).
        # Secciones de primer orden las saltamos.
        if len(den) < 3:
            continue

        # Extraer ω₀ y Q del denominador
        # El denominador normalizado de un biquad analógico es:
        #   s² + (ω₀/Q)·s + ω₀²
        # Si den = [a0, a1, a2], dividimos todo entre a0 para normalizar:
        #   s² + (a1/a0)·s + (a2/a0)
        # Por lo tanto:
        #   ω₀ = sqrt(a2/a0)
        #   Q  = sqrt(a0·a2) / a1

        a0 = den[0]
        a1 = den[1]
        a2 = den[2]

        # Guardia: si a0 es cero o muy pequeño, es una sección de primer orden
        # disfrazada de segundo orden. Deliyannis-Friend no aplica aquí.
        if abs(a0) < 1e-10:
            print(f"debug: stage {stage_idx+1} es sección de primer orden, "
                  f"Deliyannis no aplica — saltando")
            continue

        omega_0 = np.sqrt(abs(a2 / a0))
        Q = np.sqrt(abs(a0 * a2)) / abs(a1)

        # Guardia: Q debe ser > 0.5 para que Deliyannis sea realizable.
        # 2Q - 1/K debe ser positivo para que R1 sea positivo.
        if Q <= 0.5:
            print(f"debug: stage {stage_idx+1} Q={Q:.4f} ≤ 0.5, "
                  f"Deliyannis no realizable — saltando")
            continue

        # Ganancia K en la frecuencia central 
        # K=1 simplifica el diseño y es el caso más común.
        # Con K=1: R₁ = 1/(ω₀·C·(2Q-1)), R₂ = Q/(ω₀·C)
        # 2Q-1 debe ser > 0, lo que se cumple siempre que Q > 0.5
        # (para filtros bandpass bien diseñados Q >> 0.5).
        K = 1.0

        # Cálculo de capacitore
        # Ambos capacitores son iguales y usan el valor base del usuario.
        # El usuario puede elegir E series para redondear al valor estándar.
        C_ideal   = c_base
        C_rounded = round_to_eseries(C_ideal, c_series)

        # Cálculo de resistores
        # R1: resistor de entrada, controla la ganancia y el ancho de banda
        # R2: resistor de realimentación, controla el Q y la ganancia
        R1_ideal = 1.0 / (omega_0 * C_ideal * (2*Q - 1.0/K))
        R2_ideal = Q   / (omega_0 * C_ideal * K)

        R1_rounded = round_to_eseries(R1_ideal, r_series)
        R2_rounded = round_to_eseries(R2_ideal, r_series)

        # Empaquetar en objetos ComponentVae
        # stage_idx+1 porque los stages se numeran desde 1, no desde 0.
        components.append(ComponentValue(
            stage          = stage_idx + 1,
            name           = "C1",
            component_type = ComponentType.CAPACITOR,
            ideal          = C_ideal,
            rounded        = C_rounded,
            error_pct      = eseries_error_pct(C_ideal, C_rounded),
        ))
        components.append(ComponentValue(
            stage          = stage_idx + 1,
            name           = "C2",
            component_type = ComponentType.CAPACITOR,
            ideal          = C_ideal,        # C1 = C2 por diseño
            rounded        = C_rounded,
            error_pct      = eseries_error_pct(C_ideal, C_rounded),
        ))
        components.append(ComponentValue(
            stage          = stage_idx + 1,
            name           = "R1",
            component_type = ComponentType.RESISTOR,
            ideal          = R1_ideal,
            rounded        = R1_rounded,
            error_pct      = eseries_error_pct(R1_ideal, R1_rounded),
        ))
        components.append(ComponentValue(
            stage          = stage_idx + 1,
            name           = "R2",
            component_type = ComponentType.RESISTOR,
            ideal          = R2_ideal,
            rounded        = R2_rounded,
            error_pct      = eseries_error_pct(R2_ideal, R2_rounded),
        ))

        print(f'debug deliyannis stage {stage_idx+1}: ω₀={omega_0:.2f} rad/s, Q={Q:.4f}, R1={R1_ideal:.2f}Ω, R2={R2_ideal:.2f}Ω, C={C_ideal:.2e}F')

    return components
    #raise NotImplementedError("STUDENT: implement synthesise_deliyannis()")


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
    Each ComponentValue carries:
      .name            — "R1", "C2", etc.
      .component_type  — ComponentType.RESISTOR or ComponentType.CAPACITOR
      .stage           — which biquad stage (1-indexed)
      .rounded         — the E-series value to use in the netlist

    Use the topology argument to select the correct subcircuit template.
    Use ic_model to pick the op-amp .lib file from resources/spice_models/.
    Include:
      * .ac dec 100 {f_start} {f_stop}
      * Voltage source Vin ac 1
      * One subcircuit instance per stage, wired in cascade
      * .probe V(out)
    """
    match topology:
        case Topology.DELIYANNIS:              
            for component in components:
                print(f'debug (oscar) Components: {component.name}{component.stage} = {component.rounded}')
            print(f'debug (oscar) IC: {ic_model}')
        case _:
            print(f'debug (oscar): Topología {topology} aún no implementada')
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
