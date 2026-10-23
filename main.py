"""
mk50240-rp2350
Drop-in replacement for the Mostek MK50240 top-octave frequency generator.
Target: Waveshare RP2350-Zero (RP2350 only), sits in MK50240 DIP-16 socket.

Uses the existing clock signal from the instrument (MK50240 pin 2) rather
than generating frequencies internally. Pitch tracks the instrument's own
clock, including the tuning adjustment (in the Omni 2, the L1 coil slug).

STATUS: untested on hardware. Divider logic checked on a cycle-level PIO
simulator only. NOT VERIFIED, confirm before ordering parts: every part and
value below comes from datasheets and the Omni 2 service manual, not a bench
(the Omni 2 clock frequency, swing and load, pin 3 being the -15V rail, the
shifters at these voltages, the 10k/2.7k divider into 5V-tolerant GPIO 13,
78L05 temperature). See the README's "Not verified" list.

Power (read this first):
  In the ARP Omni 2, MK50240 pin 1 (VSS) is chassis ground and pin 3 (VDD)
  is the -15V rail. The adapter's GND is socket pin 3, so the whole board
  sits at -15V relative to the instrument's ground, and pin 1 is +15V
  relative to the board.
  NEVER wire pin 1 to VBUS. Power the board from its own regulator:
    pin 1 -> ~100Ω 0.5W -> 78L05 IN (0.33µF), 78L05 GND -> pin 3,
    78L05 OUT (0.1µF) -> Schottky (BAT54 / 1N5817) -> RP2350-Zero VBUS
  Only connect USB with the instrument off and unplugged, or through a USB
  isolator. Unplug USB before you plug the instrument in or switch it on.
  To use the REPL with the instrument running, go through a USB isolator.
  Never clip a mains scope's ground to the adapter.

Clock input (pin 2, 0 to +15V square, ~500 kHz from a CD4007 in the Omni 2;
datasheet range 100 kHz - 2.5 MHz):
  Pin 2 -> 10kΩ -> node -> GPIO 13      node -> 2.7kΩ -> GND (pin 3)
  ≈3.2V at 15V (3.4V at 16V), ~2.1kΩ source. GPIO 13 is 5V-tolerant and is
  also PWM6 B, which makes the ÷478 output. No pull-up on GPIO 13.
  (Belt and braces: 10k/3.9k divider into a 74LVC1G17 at 3V3, out to GPIO 13.)

Outputs: a 3.3V GPIO cannot drive the instrument's 15V CMOS inputs
(CD4520 needs VIH ≥ 11V). Use a real low-to-high shifter, VDD = pin 1,
VSS = pin 3, with ~1kΩ in series from each shifter output to its socket pin:
  CD4504B (3x, TTL mode: SELECT pin 13 and VCC tied to the 78L05's 5V), or
  CD40109B (4x, VCC = 3V3 from the RP2350-Zero, all ENABLE pins to VCC).
  Both are non-inverting, so a PIO high is a high on the socket pin.
  Do not use CD4049UB / CD4050B here (they only shift DOWN), or 10kΩ
  open-collector NPNs (too slow into the Omni 2's 5-20nF tone loads).

GPIO map (MK50240 pin -> RP2350-Zero GPIO), note names for the Omni 2's
~500 kHz clock (two octaves higher at the datasheet's 2.00024 MHz):
  MK50240 pin 2  (CLOCK in)       -> GPIO 13 (via 10k/2.7k divider; PWM6 B)
  MK50240 pin 4  (÷451, C#6)      -> GPIO 0   SM 0   PIO0
  MK50240 pin 5  (÷426, D6)       -> GPIO 1   SM 1   PIO0
  MK50240 pin 6  (÷402, D#6)      -> GPIO 2   SM 2   PIO0
  MK50240 pin 7  (÷379, E6)       -> GPIO 3   SM 3   PIO0
  MK50240 pin 8  (÷358, F6)       -> GPIO 4   SM 4   PIO1
  MK50240 pin 9  (÷338, F#6)      -> GPIO 5   SM 5   PIO1
  MK50240 pin 10 (÷319, G6)       -> GPIO 6   SM 6   PIO1
  MK50240 pin 11 (÷301, G#6)      -> GPIO 7   SM 7   PIO1
  MK50240 pin 12 (÷284, A6)       -> GPIO 8   SM 8   PIO2
  MK50240 pin 13 (÷268, A#6)      -> GPIO 9   SM 9   PIO2
  MK50240 pin 14 (÷253, B6)       -> GPIO 10  SM 10  PIO2
  MK50240 pin 15 (÷239, C7)       -> GPIO 11  SM 11  PIO2
  MK50240 pin 16 (÷239÷2, C6)     -> GPIO 12  PWM6 A (no state machine)

  The RP2350 has 12 state machines (3 PIO blocks x 4), one short of 13, so
  ÷478 comes from PWM slice 6 counting rising edges of the clock on its
  B pin (GPIO 13). Do not use GPIO 28/29 for anything PWM: they are
  slice 6 too.
"""

import rp2
from machine import Pin, mem32
import os
import utime


# =============================================================================
# PIO: Clock divider
# Counts rising edges of the incoming clock only: H rising edges with the
# output high, then L rising edges with it low, so output = clock / (H+L)
# exactly, whatever the input duty cycle. H = D//2 and L = D - D//2, so odd
# divisors are exact too (duty H/D, e.g. 119/239 = 49.8%).
#
# The two pull(block)s take H-1 then L-1 at start-up. Then the SM waits for
# a rising edge of the ÷478 output (GPIO 12, from the PWM), so every output
# starts on the same clock edge and the ÷239 output's rising edges land on
# the ÷478 output's edges, as in the MK50240 (÷478 = ÷239 then ÷2 there).
# After that the SM runs forever without CPU involvement.
#
# 15 instructions. MicroPython loads one copy into each PIO block the first
# time a state machine in that block uses it: 15 of 32 words in PIO0/1/2.
# The SMs run at the full system clock (no freq= argument, clkdiv 1).
# =============================================================================

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def divide():
    pull(block)
    mov(y, osr)             # Y   = H - 1
    pull(block)             # OSR = L - 1 (stays in OSR)

    wait(0, gpio, 12)       # sync: wait for a rising edge on GPIO 12
    wait(1, gpio, 12)       # (= DIV478_GPIO; asm_pio can't see constants)

    wrap_target()

    # High half: count H rising edges of clock
    set(pins, 1)
    mov(x, y)
    label("hi")
    wait(0, pin, 0)
    wait(1, pin, 0)         # rising edge
    jmp(x_dec, "hi")

    # Low half: count L rising edges of clock
    set(pins, 0)
    mov(x, osr)
    label("lo")
    wait(0, pin, 0)
    wait(1, pin, 0)         # rising edge
    jmp(x_dec, "lo")

    wrap()


# =============================================================================
# MK50240 divider values
# From datasheet. Pin 16 = ÷239 then ÷2 internally = effective ÷478.
# Each SM is loaded with H-1 and L-1 (H = D//2, L = D - D//2).
# =============================================================================

CLOCK_GPIO  = 13    # PWM6 B, 5V-tolerant
DIV478_GPIO = 12    # PWM6 A, the ÷478 output (must match wait(.., gpio, 12))

# (gpio, sm_id, divider, mk50240_pin, note)
OUTPUTS = [
    (0,  0,  451, 4,  'C#6'),
    (1,  1,  426, 5,  'D6'),
    (2,  2,  402, 6,  'D#6'),
    (3,  3,  379, 7,  'E6'),
    (4,  4,  358, 8,  'F6'),
    (5,  5,  338, 9,  'F#6'),
    (6,  6,  319, 10, 'G6'),
    (7,  7,  301, 11, 'G#6'),
    (8,  8,  284, 12, 'A6'),
    (9,  9,  268, 13, 'A#6'),
    (10, 10, 253, 14, 'B6'),
    (11, 11, 239, 15, 'C7'),
]
DIV478, DIV478_MK_PIN = 478, 16    # ÷239÷2 (C6 in the Omni 2), PWM6 A

# PWM slice 6 registers (RP2350 datasheet 12.5.3; not the RP2040 address)
PWM_BASE = 0x400A8000
PWM6     = PWM_BASE + 6 * 0x14
PWM6_CSR, PWM6_DIV, PWM6_CTR, PWM6_CC, PWM6_TOP = (
    PWM6 + 0x00, PWM6 + 0x04, PWM6 + 0x08, PWM6 + 0x0C, PWM6 + 0x10)
PWM_INTR = PWM_BASE + 0xF4               # raw wrap flags, bit 6 = slice 6


# =============================================================================
# Init
# =============================================================================

if "RP2350" not in os.uname().machine:
    raise RuntimeError("needs an RP2350: 12 state machines, PWM at 0x400A8000")

print("mk50240-rp2350 — ARP Omni 2 TOG replacement")
print("Clock source: external (MK50240 pin 2 -> GPIO {} via 10k/2.7k divider)".format(CLOCK_GPIO))
print("")
print("{:<8} {:<10} {:<10} {:<6}".format("GPIO", "Engine", "Divider", "Note"))
print("-" * 40)

# Take every slice 6 pin off the PWM first. A previous run (then Ctrl-D) or
# other PWM code can leave them on it. While the slice runs free below, B on
# GPIO 13 would drive against the clock divider, and GPIO 28/29 (slice 6
# too) would be driven. A GPIO 29 left on PWM would also be ORed with
# GPIO 13 into the B input once the slice counts clock edges.
Pin(CLOCK_GPIO, Pin.IN)
Pin(DIV478_GPIO, Pin.OUT, value=0)
for gpio in (28, 29):
    Pin(gpio, Pin.IN, Pin.PULL_DOWN)     # unused: input, reset pull-down

# TOP and CC are double-buffered: the slice only takes new values when its
# counter wraps (RP2350 datasheet 12.5.2.3). Values left latched by earlier
# code (e.g. a machine.PWM test on GPIO 12/13 before a soft reset) would give
# an early first ÷478 edge, and the ÷239 output would stay out of step with
# ÷478 for good. So run the slice free until it wraps and latches TOP/CC.
# A wrap also sets the slice's INTR flag (12.5.2.7), so wait for that flag
# rather than a fixed time.
mem32[PWM6_CSR] = 0                      # stopped
mem32[PWM6_DIV] = 1 << 4                 # INT=1, FRAC=0: one count per edge
mem32[PWM6_TOP] = DIV478 - 1             # 478 counts per period
mem32[PWM6_CC]  = DIV478 // 2            # A high while CTR < 239: 239/239
mem32[PWM6_CTR] = DIV478 - 1
mem32[PWM_INTR] = 1 << 6                 # clear slice 6's wrap flag (write 1)
mem32[PWM6_CSR] = 1                      # EN=1, free-running: one count per system clock
t0 = utime.ticks_ms()
while not (mem32[PWM_INTR] & (1 << 6)):  # wraps within 65536 counts (0.44 ms at 150 MHz)
    if utime.ticks_diff(utime.ticks_ms(), t0) > 100:
        raise RuntimeError("PWM slice 6 did not wrap")

# Stop it again with B as an input (DIVMODE=2) before GPIO 13 is handed to
# the PWM, and park the counter at TOP so the first clock edge after EN
# wraps it. Output A should then be low (if it is still high from the free
# run, the SMs simply sync on the next ÷478 rise).
mem32[PWM6_CSR] = 2 << 4                 # DIVMODE=2: count rising edges of B, EN=0
mem32[PWM6_CTR] = DIV478 - 1

# Clock pin: PWM function (slice 6 B input), no pull. The PIO reads it too:
# PIO can always see every pin's input, whatever its function.
CLOCK_PIN  = Pin(CLOCK_GPIO, Pin.ALT, alt=Pin.ALT_PWM)
DIV478_PIN = Pin(DIV478_GPIO, Pin.ALT, alt=Pin.ALT_PWM)

state_machines = []

for gpio, sm_id, divider, mk_pin, note in OUTPUTS:
    print("{:<8} {:<10} {:<10} {:<6}  (pin {})".format(
        gpio, "SM {}".format(sm_id), divider, note, mk_pin))

    high = divider // 2
    low  = divider - high
    sm = rp2.StateMachine(
        sm_id,
        divide,
        set_base=Pin(gpio, Pin.OUT),
        in_base=CLOCK_PIN
    )
    sm.put(high - 1)
    sm.put(low - 1)
    sm.active(1)                         # waits for the first ÷478 edge
    state_machines.append(sm)

print("{:<8} {:<10} {:<10} {:<6}  (pin {})".format(
    DIV478_GPIO, "PWM6 A", DIV478, 'C6', DIV478_MK_PIN))

# Start the ÷478 counter: DIVMODE=2 (count rising edges of B), EN=1.
# All 12 state machines wait for the first rising edge of output A, so they
# start on the same clock edge.
mem32[PWM6_CSR] = (2 << 4) | 1

print("")
print("PIO0/PIO1/PIO2: divide(), {} of 32 instruction words each".format(len(divide[0])))

# Bench check: the ÷478 output only toggles if the clock is reaching GPIO 13
# (both levels show within ~5 ms, even at the slowest 100 kHz clock).
seen = set()
t0 = utime.ticks_ms()
while len(seen) < 2 and utime.ticks_diff(utime.ticks_ms(), t0) < 1000:
    seen.add(DIV478_PIN.value())
if len(seen) == 2:
    print("All 13 dividers running.")
    print("Pitch tracks the Omni 2's own clock on pin 2.")
else:
    print("No clock on GPIO {}: outputs wait for it (check pin 2 wiring).".format(CLOCK_GPIO))

# SMs and PWM run independently in hardware — nothing left for CPU to do
while True:
    utime.sleep(10)
