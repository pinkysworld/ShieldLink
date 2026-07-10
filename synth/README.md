# Yosys synthesis workflow

This directory contains an open-flow synthesis helper for comparing the ShieldLink control-plane RTL variants:

- baseline CRC+ARQ receiver control
- ShieldLink Mode A per-frame ACK gating
- ShieldLink Mode B flush-all epoch authentication
- ShieldLink Mode B-SR selective-retry epoch authentication

Run from the repository root:

```bash
bash synth/run_yosys_synthesis.sh
```

The script writes logs and compact summaries to `synth/out/`. It uses generic Yosys synthesis passes and reports structural cell/memory statistics. These results are useful for relative control-plane comparison, but they are not a replacement for vendor FPGA place-and-route, ASIC timing closure, power analysis, or a complete PHY/cipher integration.

If Yosys is not installed locally, the GitHub Actions workflow `.github/workflows/yosys-synthesis.yml` can run the same script and upload the synthesis output as an artifact.
