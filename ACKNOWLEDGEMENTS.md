# Acknowledgements

Smart Remote Control was developed with reference to the Home Assistant IR-control ecosystem, including SmartIR concepts and community implementations used to understand IR profile formats and transmitter behavior.

Notable references used during development include:

- SmartIR by litinoveweedle — https://github.com/litinoveweedle/SmartIR
- climate-remote-control by avzhuiko — https://github.com/avzhuiko/climate-remote-control
- Home Assistant documentation and APIs
- HACS validation tooling

Where code or algorithms are derived from third-party projects, their original copyright and license continue to apply. This project's GPL-3.0-only license does not relicense third-party material.

The notices and license texts below are reproduced because parts of this integration are derived from those projects.

---

## SmartIR

The Pronto/LIRC/Broadlink conversion in `remote_control.py` (`_pronto_to_lirc`, `_lirc_to_broadlink`) follows SmartIR's algorithm.

MIT License

Copyright (c) 2019 Vassilis Panos, 2024 Li Tin O've Weedle

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## climate-remote-control

The HA Remote learned-command naming and grouping semantics in `climate.py` follow climate-remote-control.

MIT License

Copyright (c) 2024 - 2026 Aleksei Zhuiko @avzhuiko

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
