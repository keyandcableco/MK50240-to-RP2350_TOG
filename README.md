# mk50240-rp2350

Drop-in replacement for the Mostek MK50240 top-octave frequency generator,
built around the Waveshare RP2350-Zero.

Primary target: ARP Omni 2. May work in other instruments using the MK50240
or MK50241 — verify the pinout and clock voltage before installing.

**Status: untested on hardware. Treat all component values and wiring details
as starting points, not verified specifications.**

---

## What it does

The MK50240 takes an external clock (pin 2) and divides it by 13 fixed values
to produce one full octave of top-octave square waves plus a C7 one octave
below. This firmware replicates that using 13 PIO state machines on the
RP2350-Zero, reading the same clock signal from the instrument's PCB and
dividing it by the same values. Pitch tracks the instrument's own clock.

The RP2350 was chosen over the RP2040 because the MK50240 has 13 outputs —
one more than the RP2040's 8 PIO state machines can handle.

---

## Hardware

### What you need

- Waveshare RP2350-Zero
- 2× CD4049UB hex inverting buffer (DIP-16) for output level shifting (12 channels)
- 1× MMBT3904 NPN transistor + 1× 1kΩ + 1× 10kΩ resistor for the 13th output
- 1× BAT48 Schottky diode + 1× 10kΩ resistor for clock input clamping
- 5V supply for VBUS (a nearby regulator in the instrument may work)
- Machined DIP-16 pin header to sit in the MK50240 socket

### Pin mapping

| MK50240 pin | Function | RP2350-Zero |
|---|---|---|
| 1 | VSS (+supply) | VBUS (5V from regulator) |
| 2 | CLOCK in | GPIO 26 (needs level shifting — see below) |
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

The MK50240 clock swings to VSS (~15V in the Omni 2). The RP2350 GPIO
maximum input is 3.3V. The clock signal must be level-shifted before
connecting to GPIO 26.

A Schottky diode clamp is a reliable approach regardless of exact supply
voltage: place a BAT48 (or similar) between GPIO 26 and the 3.3V rail,
with a series resistor (10kΩ) between the clock source and GPIO 26.
Anything above ~3.6V is clamped. Verify the clamped signal looks clean
on a scope before powering the RP2350.

A resistor voltage divider also works if you know the supply voltage —
choose values that bring the clock signal below 3.3V at the GPIO.

### Output levels

The MK50240 datasheet specifies VOH = VSS-1.0V minimum (~14V in the Omni 2)
and VOL = 0-1.5V. The downstream circuitry expects logic swings near the
supply voltage. The RP2350 GPIOs output 3.3V, which is unlikely to be
recognised as a valid HIGH by the downstream circuitry without level shifting.

Direct GPIO connection is worth trying first on the bench — it may work
depending on what the downstream inputs actually need.

**Recommended level shifter: CD4049UB (hex inverting buffer)**

The CD4049UB is designed exactly for this use case. Its VDD can be tied to
the instrument's 15V supply rail while accepting 3.3V GPIO inputs directly
(the input protection diodes handle the voltage mismatch). Outputs swing
rail-to-rail at VDD (~15V). It is non-destructive to the RP2350 inputs and
still widely available in DIP-16.

Two CD4049UB chips cover 12 channels. The 13th output (pin 16, C7) uses a
single MMBT3904 NPN transistor in open-collector configuration — same
inverting behaviour as the CD4049UB, so polarity is consistent across all
13 outputs.

```
RP2350 GPIO → CD4049UB input (VDD = +15V from instrument)
              CD4049UB output → MK50240 socket pin
```

The CD4049UB is inverting — output is HIGH when input is LOW and vice versa.
This inverts the output polarity relative to the GPIO state. If the
downstream circuit behaves incorrectly, swap `set(pins,0)` and `set(pins,1)`
in the `divide()` PIO program in `main.py` to compensate.

A CD4050B (non-inverting hex buffer, same package) is also an option if
polarity inversion is a problem, though verify its input voltage tolerance
at 3.3V with a 15V supply before using — the CD4049UB is the more
established choice for cross-voltage-domain buffering.

### Pin 16 — C7

The MK50240 internally divides the ÷239 output (C8, pin 15) by 2 to
produce C7 on pin 16, one octave below. The firmware uses an effective
divider of 478 (= 239 × 2) to replicate this. Per the datasheet, pin 16
has 50% duty cycle regardless of variant.

---

## Variants

| Variant | Duty cycle | Notes |
|---|---|---|
| MK50240 | 50% | Supported |
| MK50241 | 30% | Same pinout as MK50240, should work |
| MK50242 | 50% | Different pin order — edit `OUTPUTS` in main.py |
