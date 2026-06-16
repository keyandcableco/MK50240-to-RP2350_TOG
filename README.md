# mk50240-rp2350

Drop-in replacement for the Mostek MK50240 top-octave frequency generator,
built around the Waveshare RP2350-Zero.

Tested target: ARP Omni 2. May work in other instruments that use the
MK50240 or MK50241 — check the pinout and clock voltage before installing.

**Status: untested on hardware.**

---

## What it does

The MK50240 takes an external clock (pin 2, nominally 2.00024 MHz in the
Omni 2) and divides it by 13 fixed values to produce one full octave of
top-octave square waves plus a C7 one octave below. These feed the Omni 2's
downstream VCO/divider chain.

This firmware uses the same external clock signal from the instrument's PCB,
divided by the same values using RP2350 PIO state machines. Pitch tracks the
instrument's own clock, including any tuning adjustments the instrument makes.
This is the correct approach for a true drop-in replacement.

The RP2350 was chosen over the RP2040 specifically because the MK50240 has
13 outputs — one more than the RP2040's 8 PIO state machines can handle.
The RP2350 has 12 state machines across two PIO blocks, covering all 13
outputs exactly.

---

## Hardware

### What you need

- Waveshare RP2350-Zero
- 2× 68kΩ resistors, 2× 33kΩ resistors (clock + one spare — see below)
- 13× MMBT3904 NPN transistors (SOT-23) + 13× 1kΩ + 13× 10kΩ resistors
- 5V supply for VBUS (steal from a nearby regulator in the instrument)
- Machined DIP-16 pin header to sit in the MK50240 socket

### Pin mapping

| MK50240 pin | Function | RP2350-Zero |
|---|---|---|
| 1 | VSS (+supply, ~15V) | VBUS via regulator (5V) |
| 2 | CLOCK in | GPIO 26 (via 68k+33k voltage divider) |
| 3 | VDD (GND) | GND |
| 4 | ÷451 C#8 | GPIO 0 |
| 5 | ÷426 D8 | GPIO 1 |
| 6 | ÷402 D#8 | GPIO 2 |
| 7 | ÷379 E8 | GPIO 3 |
| 8 | ÷358 F8 | GPIO 4 |
| 9 | ÷338 F#8 | GPIO 5 |
| 10 | ÷319 G8 | GPIO 6 |
| 11 | ÷301 G#8 | GPIO 7 |
| 12 | ÷284 A8 | GPIO 8 |
| 13 | ÷268 A#8 | GPIO 9 |
| 14 | ÷253 B8 | GPIO 10 |
| 15 | ÷239 C8 | GPIO 11 |
| 16 | ÷239÷2 C7 | GPIO 12 |

### Clock input (pin 2)

The clock signal on pin 2 swings to VSS (~15V). The RP2350 GPIO maximum
is 3.3V. **You must level-shift the clock down before connecting to GPIO 26.**

Voltage divider:
```
MK50240 pin 2 → 68kΩ → node → GPIO 26
                node → 33kΩ → GND
```
Output at node ≈ 15V × 33/(68+33) = 4.9V... actually that's still too high.
Use 18kΩ + 33kΩ instead:
```
MK50240 pin 2 → 68kΩ → node → GPIO 26
                node → 22kΩ → GND
```
15V × 22/(68+22) = 3.67V — marginal. Better: use a Schottky diode clamp
(BAT48 between GPIO 26 and 3.3V rail with a 10kΩ series resistor) which
clamps anything above ~3.6V cleanly regardless of supply voltage.

### Output levels

The MK50240 datasheet specifies VOH = VSS-1.0V (~14V) and VOL = 0-1.5V.
The downstream circuitry expects logic swings near the supply voltage.
**Level shifting is required on all 13 outputs.**

Use MMBT3904 NPN transistors in open-collector configuration:

```
GPIO → 1kΩ → MMBT3904 base
              MMBT3904 emitter → GND
              MMBT3904 collector → output pin → downstream circuit
                                       │
                                    10kΩ pullup to VSS (+15V)
```

- GPIO HIGH → transistor ON  → output pulled to GND (0V) = logic LOW
- GPIO LOW  → transistor OFF → output pulled to ~15V via 10kΩ = logic HIGH

This inverts the output polarity. The original MK50240 outputs HIGH when
active; our transistor outputs LOW when the GPIO is high. If the downstream
circuit behaves incorrectly, swap `set(pins,0)` and `set(pins,1)` in the
`divide()` PIO program in main.py.

### Pin 16 — C7

Pin 16 is not a direct divider output. The MK50240 internally takes the
÷239 output (C8, pin 15) and divides it by 2 to produce C7 on pin 16.
The firmware represents this as an effective divider of 478 (= 239 × 2),
which gives the correct output frequency. Per the datasheet (Note 1),
pin 16 always has 50% duty cycle — our ÷2 implementation naturally
produces this.

---

## MK50240 vs MK50241 vs MK50242

| Variant | Duty cycle | Pin 16 |
|---|---|---|
| MK50240 | 50% | C7 (÷239÷2), 50% duty |
| MK50241 | 30% | C7 (÷239÷2), 50% duty |
| MK50242 | 50% | **different pinout** — check datasheet before using |

If your instrument uses a MK50242, the GPIO-to-pin assignments need
reordering. Edit the `OUTPUTS` list in main.py.

