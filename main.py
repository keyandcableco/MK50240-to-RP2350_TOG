"""
mk50240-rp2350
Drop-in replacement for the Mostek MK50240 top-octave frequency generator.
Target: Waveshare RP2350-Zero, sits in MK50240 DIP-16 socket.

Uses the existing clock signal from the instrument (MK50240 pin 2) rather
than generating frequencies internally. This is the correct approach for
a true drop-in replacement — pitch tracks the instrument's own clock,
including any tuning adjustments the instrument makes.

The clock input on pin 2 swings to VSS (~15V in the ARP Omni 2).
You MUST add a voltage divider before GPIO 26:
  Pin 2 → 68kΩ → node → GPIO 26
  node → 33kΩ → GND
  Output ≈ 3.0V — safe for RP2350 input.

GPIO map (MK50240 pin → RP2350-Zero GPIO):
  MK50240 pin 2  (CLOCK in)     → GPIO 26 (via 68k+33k voltage divider)
  MK50240 pin 4  (÷451, C#8)   → GPIO 0   SM 0
  MK50240 pin 5  (÷426, D8)    → GPIO 1   SM 1
  MK50240 pin 6  (÷402, D#8)   → GPIO 2   SM 2
  MK50240 pin 7  (÷379, E8)    → GPIO 3   SM 3
  MK50240 pin 8  (÷358, F8)    → GPIO 4   SM 4
  MK50240 pin 9  (÷338, F#8)   → GPIO 5   SM 5
  MK50240 pin 10 (÷319, G8)    → GPIO 6   SM 6
  MK50240 pin 11 (÷301, G#8)   → GPIO 7   SM 7
  MK50240 pin 12 (÷284, A8)    → GPIO 8   SM 8
  MK50240 pin 13 (÷268, A#8)   → GPIO 9   SM 9
  MK50240 pin 14 (÷253, B8)    → GPIO 10  SM 10
  MK50240 pin 15 (÷239, C8)    → GPIO 11  SM 11
  MK50240 pin 16 (÷239÷2, C7)  → GPIO 12  SM 12

  MK50240 pin 1  (VSS, +supply) → RP2350 VBUS (5V from regulator)
  MK50240 pin 3  (VDD, ground)  → RP2350 GND

Output levels:
  MK50240 VOH = VSS-1.0V (~14V in Omni 2). RP2350 GPIOs = 3.3V.
  Level shifting required on all 13 outputs. See README for circuit.

  MK50240 outputs are buffered push-pull, not open-drain. Use MMBT3904
  NPN transistors, open-collector with 10kΩ pullup to VSS:
    GPIO HIGH → transistor ON  → output LOW  (0V)
    GPIO LOW  → transistor OFF → output HIGH (~15V via pullup)

  This inverts the output polarity relative to the PIO logic.
  If the downstream circuit is edge-sensitive and behaves incorrectly,
  swap set(pins,0) and set(pins,1) in the divide() PIO program below.
"""

import rp2
from machine import Pin
import utime


# =============================================================================
# PIO: Clock divider
# Counts rising and falling edges of the incoming clock signal.
# Each state machine divides the clock by its loaded counter value,
# producing a square wave at clock_freq / (2 * (N+1)).
#
# pull(block) on first load ensures the SM waits for a valid divider
# before starting. The divider is pushed once during init and then
# the SM runs indefinitely without CPU involvement.
# =============================================================================

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def divide():
    pull(block)
    mov(y, osr)

    wrap_target()
    label("start")

    # Low half: count N rising edges of clock
    mov(x, y)
    set(pins, 0)
    label("loop1")
    wait(0, pin, 0)         # wait for falling edge
    jmp(x_dec, "d1")
    jmp("part2")
    label("d1")
    wait(1, pin, 0)         # wait for rising edge
    jmp(x_dec, "loop1")

    # High half: count N rising edges of clock
    label("part2")
    set(pins, 1)
    mov(x, y)
    label("loop2")
    wait(0, pin, 0)
    jmp(x_dec, "d2")
    jmp("start")
    label("d2")
    wait(1, pin, 0)
    jmp(x_dec, "loop2")

    wrap()


# =============================================================================
# MK50240 divider values
# From datasheet. Pin 16 = ÷239 then ÷2 internally = effective ÷478.
# Divider value loaded into SM = N where output = clock / (2*(N+1)).
# So we load (divider - 1) to get the correct division ratio.
# =============================================================================

CLOCK_PIN = Pin(26, Pin.IN, Pin.PULL_UP)

# (gpio, sm_id, divider, mk50240_pin, note)
OUTPUTS = [
    (0,  0,  451, 4,  'C#8'),
    (1,  1,  426, 5,  'D8'),
    (2,  2,  402, 6,  'D#8'),
    (3,  3,  379, 7,  'E8'),
    (4,  4,  358, 8,  'F8'),
    (5,  5,  338, 9,  'F#8'),
    (6,  6,  319, 10, 'G8'),
    (7,  7,  301, 11, 'G#8'),
    (8,  8,  284, 12, 'A8'),
    (9,  9,  268, 13, 'A#8'),
    (10, 10, 253, 14, 'B8'),
    (11, 11, 239, 15, 'C8'),
    (12, 12, 478, 16, 'C7'),   # ÷239÷2 — extra ÷2 stage internal to MK50240
]


# =============================================================================
# Init
# =============================================================================

print("mk50240-rp2350 — ARP Omni 2 TOG replacement")
print("Clock source: external (MK50240 pin 2 → GPIO 26 via 68k+33k divider)")
print("")
print("{:<8} {:<6} {:<10} {:<6}".format("GPIO", "SM", "Divider", "Note"))
print("-" * 34)

state_machines = []

for gpio, sm_id, divider, mk_pin, note in OUTPUTS:
    print("{:<8} {:<6} {:<10} {:<6}  (pin {})".format(
        gpio, sm_id, divider, note, mk_pin))

    sm = rp2.StateMachine(
        sm_id,
        divide,
        freq=125_000_000,
        set_base=Pin(gpio, Pin.OUT),
        in_base=CLOCK_PIN
    )
    sm.put(divider - 1)
    sm.active(1)
    state_machines.append(sm)

print("")
print("All 13 dividers running.")
print("Pitch tracks the Omni 2's own clock on pin 2.")

# SMs run independently in hardware — nothing left for CPU to do
while True:
    utime.sleep(10)
