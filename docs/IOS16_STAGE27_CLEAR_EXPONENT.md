# Stage27: match color-clear brightness to guest rendering

The build27 phone capture of the aerial GPS map (frame1285) shows a sharply
bounded bright area before the final bloom/composition. The early lighting
target contains exactly0.498046875 outside the local geometry and8.0 inside it.
Its color-info0x430400 requests exponent+4: the neutral geometry output0.5 is
scaled by16, while the previous color clear kept raw127/255. This leaves the
background and the geometry in different brightness ranges.

The game's original clear path also applies the target exponent: clear helper
824188E0 passes the target color-info exponent to packer824206A8, whose prefix
adjusts the exponent of each supplied float before format conversion. The
Metal clear previously omitted that step.

Clear now applies the existing native color-output conversion separately for
each active color attachment. Full load-action clears and rectangular shader
clears use the same scale and format limits as draws. Resolve-requested clears
already share this method. Rectangle bounds, depth/stencil clear behavior,
shaders, controls, saved settings and minimum iOS16 are retained.

`tools/test_mcla_metal_clear_exponent.py` extracts and compiles the actual Clear
method with synthetic render targets. GPU readback checks full and rectangular
clears, different simultaneous target exponents (including negative), alpha,
normalized limits, disabled target flags and surrounding pixels. Run the same
test against the previous method to establish a failing regression, then the
fixed method. Existing color/depth/stencil clear regressions remain relevant.

This is a source-level correction supported by the captured buffer values and
the guest clear implementation. A native build and phone comparison must be
reported separately; disappearance of the map seam is not claimed until the
phone retest. A small difference between127/255 and0.5 is title quantization,
not a reason to force the whole scene to a fixed brightness.
