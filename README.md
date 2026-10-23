# mk50240-rp2350

Drop-in replacement for the Mostek MK50240 top-octave frequency generator,
built around the Waveshare RP2350-Zero.

Primary target: ARP Omni 2. May work in other instruments using the MK50240
or MK50241 — verify the pinout, supply and clock before installing.

**Status: untested on hardware. The divider firmware has only been checked on
a cycle-level PIO simulator. Treat all component values and wiring details as
starting points, not verified specifications.**

### Not verified: confirm before ordering

These come from datasheets, the Omni 2 service manual and simulation, not
from a bench:

- The Omni 2 socket supply: pin 1 = chassis ground, pin 3 = -15 V (service
  manual schematic). Measure pin 1 to pin 3 (expect about +15 V) before
  fitting the adapter.
- The Omni 2 clock: about 500 kHz, 0 to +15 V (relative to pin 3), from a
  CD4007. Taken from the service manual, not measured.
- GPIO 13 is 5 V-tolerant (3.63 V max while the board is unpowered; the
  divider gives 3.2-3.4 V), and GPIO 0-13 are on the RP2350-Zero header
  (RP2350 datasheet, Waveshare schematic).
- The 10k/2.7k clock divider: about 3.2 V at the GPIO from 15 V, and the
  CD4007 driving its 12.7 kΩ load (1.2 mA). Same for the 10k/3.9k +
  74LVC1G17 option.
- CD4504B in TTL mode (SELECT pin 13 to VCC = 5 V, VDD = 15 V) reading a
  3.3 V GPIO as high. CD40109B at VCC = 3.3 V (TI only tables 5 V and up).
- The ~1 kΩ series resistors matching the MK50240's own output drive into
  the Omni 2's 5-20 nF tone networks (simulated only).
- The 78L05 with ~100 Ω 0.5 W in front: its temperature inside the
  instrument at 25-45 mA (estimated draw), and its input headroom in
  instruments where the MK50240 supply is only 11-12 V.
- The Schottky drop into VBUS, and the RP2350-Zero's VBUS limits (5 V TVS,
  6.5 V LDO input; from third-party part listings).
- The optional PTC value (50-100 mA).
- The silicon stepping on your RP2350-Zero (see Erratum E9 below).
- Every other datasheet figure in this README is also unchecked on a bench:
  the MK50240/1/2 pinouts, supply range (11-16 V), duty cycles and
  100 kHz-2.5 MHz clock range; the CD4049UB/CD4050B and CD4520 input
  thresholds and the CD4520's 5 µs rise limit; the RP2350 pin limits and the
  E9 figures.

---

## What it does

The MK50240 takes an external clock (pin 2) and divides it by 12 fixed
values to produce one octave of top-octave square waves, plus a 13th output
(pin 16) one octave below the highest one: ÷239 then ÷2, so ÷478.

The RP2350 has 12 PIO state machines (3 PIO blocks of 4; the RP2040 has 8).
This firmware uses all 12 for the top-octave outputs, and makes the ÷478
output on pin 16 with PWM slice 6 counting rising edges of the same clock.
Pitch tracks the instrument's own clock, including its tuning adjustment.

Each state machine counts rising edges of the clock only (H edges high, then
L edges low, with H + L = D, the divider), so every output is exact, odd
dividers included, whatever the clock's duty cycle. Odd dividers give a duty
of H/D (49.8-49.9%) instead of exactly 50%.

All 12 state machines wait for the first rising edge of the ÷478 output, so
they start on the same clock edge and the ÷239 output stays in step with
÷478, as inside the MK50240. If no clock reaches GPIO 13, pins 4-15 stay
low and the console says so.

---

## Hardware

### What you need

- Waveshare RP2350-Zero
- Machined DIP-16 pin header to sit in the MK50240 socket
- Output level shifting (non-inverting, 3.3 V in, 15 V out), one of:
  - 3× CD4504B hex level shifter, in TTL mode (recommended), or
  - 4× CD40109B quad level shifter
- 100 nF decoupling capacitor on each shifter's VDD and on its VCC
- 13× ~1 kΩ series resistors, one per output (not verified)
- Power: 78L05, ~100 Ω 0.5 W resistor, 0.33 µF and 0.1 µF capacitors,
  BAT54 or 1N5817 Schottky diode (not verified)
- Clock input: 10 kΩ and 2.7 kΩ 1% resistors (not verified). Optional
  belt-and-braces version: 74LVC1G17 with a 10k/3.9k divider instead.
- Optional: 50-100 mA PTC fuse in series with pin 1 (not verified)

### Pin mapping

In the Omni 2 the clock is about 500 kHz (service manual, not verified), a
quarter of the datasheet's 2.00024 MHz, so every output is two octaves
lower. Note names below are scientific pitch. The datasheet's own labels
agree for C#8-B8 but call ÷239 C8 and ÷478 C7.

| MK50240 pin | Function | Omni 2 note | At 2.00024 MHz | Adapter |
|---|---|---|---|---|
| 1 | VSS | | | 78L05 input (through the PTC and ~100 Ω). **Never to VBUS** |
| 2 | CLOCK in | | | 10k/2.7k divider → GPIO 13 (no pull-up) |
| 3 | VDD | | | Adapter GND. **In the Omni 2 this is the -15 V rail, not chassis ground** |
| 4 | ÷451 | C#6 | C#8 | GPIO 0 |
| 5 | ÷426 | D6 | D8 | GPIO 1 |
| 6 | ÷402 | D#6 | D#8 | GPIO 2 |
| 7 | ÷379 | E6 | E8 | GPIO 3 |
| 8 | ÷358 | F6 | F8 | GPIO 4 |
| 9 | ÷338 | F#6 | F#8 | GPIO 5 |
| 10 | ÷319 | G6 | G8 | GPIO 6 |
| 11 | ÷301 | G#6 | G#8 | GPIO 7 |
| 12 | ÷284 | A6 | A8 | GPIO 8 |
| 13 | ÷268 | A#6 | A#8 | GPIO 9 |
| 14 | ÷253 | B6 | B8 | GPIO 10 |
| 15 | ÷239 | C7 | C9 | GPIO 11 |
| 16 | ÷478 (÷239 then ÷2) | C6 | C8 | GPIO 12 (PWM6 A) |

Pins 4-16 each go GPIO → level shifter → ~1 kΩ → socket pin.

### Power (read this first)

The MK50240 is a P-MOS part: pin 1 (VSS) is its most positive supply and
pin 3 (VDD) sits 11-16 V below it. In the Omni 2, pin 1 is chassis ground and
pin 3 is the -15 V rail (service manual schematic, not verified: measure it).
The adapter's GND is pin 3, so the whole board sits at -15 V relative to the
instrument, and pin 1 is +15 V relative to the board.

Never wire pin 1 to VBUS: 15 V there would likely destroy the RP2350-Zero's
TVS diode and regulator, and can reach a connected USB host. Give the adapter
its own 5 V:

```
pin 1 → (PTC) → ~100 Ω 0.5 W → 78L05 IN   (0.33 µF to pin 3)
                               78L05 GND  → pin 3
                               78L05 OUT  (0.1 µF to pin 3) → Schottky → VBUS
```

The Schottky stops USB power back-feeding the 78L05. A CD4504B's VCC
comes from the 78L05 output, before the diode. The 100 Ω resistor takes some
of the heat off the 78L05; check its temperature in the instrument. The
estimated draw (25-45 mA) is close to the MK50240's own (24 mA typical,
37 mA max, datasheet). All of this is not verified.

### Clock input (pin 2)

The Omni 2's clock is a 0 to +15 V square wave (relative to pin 3) at about
500 kHz (service manual, not verified), from a CD4007 buffering the L1/Q1
oscillator. The MK50240 datasheet allows 100 kHz to 2.5 MHz (not verified).

```
pin 2 → 10 kΩ → node → GPIO 13
                node → 2.7 kΩ → GND (pin 3)
```

That gives about 3.2 V at 15 V (3.4 V at 16 V) from a ~2.1 kΩ source (not
verified). GPIO 13 is 5 V-tolerant (RP2350 datasheet, not verified), and it
is also the PWM6 B input that makes the ÷478 output. No pull-up or pull-down
on GPIO 13. Do not use GPIO 26-29 (ADC pins, not 5 V-tolerant), and do not
use a clamp diode to 3.3 V (it back-powers the board when it is off). Keep
the divider values low: a higher-impedance divider misses edges at 2 MHz,
and fails on A2-stepping chips (see Erratum E9).

Belt-and-braces option: pin 2 → 10k/3.9k divider → 74LVC1G17 (VCC = 3V3,
100 nF) → GPIO 13 (not verified).

### Outputs (pins 4-16)

The MK50240's outputs swing nearly the full supply: within 1.0 V of pin 1
when high and within 1.5 V of pin 3 when low (datasheet, not verified). In
the Omni 2 they clock CD4520 dividers, which need at least 11 V for a high
(datasheet, not verified), and drive 5-20 nF tone networks. A 3.3 V GPIO
cannot drive them directly.

Use a real low-to-high shifter, VDD = pin 1, VSS = pin 3 (from datasheets,
not verified):

- **CD4504B** (3×), TTL mode: SELECT (pin 13) and VCC tied to the 78L05's
  5 V. Reads a 3.3 V GPIO as high. 5 channels spare.
- **CD40109B** (4×): VCC = 3V3 from the RP2350-Zero, all ENABLE pins tied to
  VCC (or the outputs float). VCC must be 3.3 V, not 5 V.

Both are non-inverting, so a high from the PIO is a high on the socket pin.
Put ~1 kΩ in series with each shifter output: it brings the drive close to
the MK50240's and slows the edges, as the original does.

Do not use a CD4049UB or CD4050B here: they only shift down (at 15 V they
need 11-12.5 V to see a high). Do not use 10 kΩ open-collector NPN stages
either: into the Omni 2's tone networks their rise time is far beyond the
CD4520's 5 µs limit.

### Pin 16 — ÷478

The MK50240 divides its ÷239 output by 2 to make pin 16, at 50% duty on
the MK50240 and MK50241 (the MK50242 has no ÷478 output). The firmware
makes it with PWM slice 6 (output A on GPIO 12, counting the clock on input
B, GPIO 13): exactly 478 clock edges per period, 239 high. GPIO 28 and 29
belong to slice 6 too: leave them unused and never give them a PWM function
(`main.py` sets both to plain inputs at start-up).

---

## USB and scopes

The adapter's GND is the instrument's -15 V rail. A USB cable from a
mains-earthed computer, or a mains scope's ground clip, connects that rail to
earth and shorts it through the instrument's grounding.

- Connect USB only with the instrument off and unplugged, or through a USB
  isolator. Unplug USB before you plug the instrument in or switch it on.
  To use the REPL with the instrument running, go through a USB isolator.
- Never clip a mains scope's ground to the adapter. Put the scope ground on
  the instrument's chassis ground (readings are then offset by -15 V), or
  use a differential probe.

Bench check without the instrument: do it on the bare RP2350-Zero, before
the level shifters are fitted (or with them removed). On an assembled
adapter the shifters' VCC comes from the 78L05, which is dead without the
instrument, and 3.3 V outputs driving an unpowered CD4504B exceed its input
rating. Power the Zero from USB, feed a 3.3 V square wave (100 kHz-2.5 MHz)
into GPIO 13, and check GPIO 11 reads f/239 and GPIO 12 reads f/478 on a
frequency counter. A two-channel scope on GPIO 11 and 12 should show their
edges together.

---

## Erratum E9 (RP2350 A2 stepping)

On A2-stepping chips, a GPIO input fed from a source above about 8.2 kΩ can
stick near 2.2 V (RP2350 datasheet, erratum RP2350-E9; fixed in A3/A4). The
10k/2.7k clock divider is about 2.1 kΩ, so it should work on A2 as well (not
verified); do not raise its values or add a pull resistor. To check your
board in the MicroPython REPL:

```python
import machine
print(machine.mem32[0x40000000] >> 28 & 0xF)  # 2 = A2 (has E9), 3 = A3 or A4
print(machine.mem8[0x13])                      # bootrom version: 3 = A3, 4 = A4
```

---

## Firmware notes

- MicroPython for the RP2350 (`main.py` refuses to run on an RP2040). The
  state machines run at the full system clock (no `freq=`).
- GPIO 12 is written into the PIO program (`wait(.., gpio, 12)`), because
  `asm_pio` cannot see module constants. Moving the ÷478 output means editing
  both `DIV478_GPIO` and those two lines.
- PWM slice 6 is set up through `machine.mem32` (MicroPython's PWM class has
  no edge-counting mode), at the RP2350 address (0x400A8000), not the
  RP2040's. Its TOP/CC registers are double-buffered, so the setup runs the
  slice free until it wraps (its INTR flag sets) to latch them, before
  switching it to counting clock edges. That keeps the ÷239/÷478 lock even
  after a soft reset that follows other PWM code.
- Not checked on hardware: the PWM counting the clock on GPIO 13 while the
  PIO reads the same pin, and the MicroPython calls (checked against current
  MicroPython source only).

---

## Variants

| Variant | Duty cycle | Notes |
|---|---|---|
| MK50240 | 50% | Supported |
| MK50241 | 30% (pin 16 50%) | Same pinout, but this firmware gives 50% on every output, which changes the direct top-octave tone slightly |
| MK50242 | 50% | Not supported: power on pins 1 and 10, no ÷478 output, different pin order. Needs a different PCB |
