# Application examples

The [slider](simple_slider/README.md) and [synthetic robot](urdf_robot/README.md) examples combine a Vue UI with Python or C++ backends. Use the local 0.5.0 SDK wheel/install prefix and an explicitly started matching Host. They do not require an installed global FrameViz App.

Both require a separate `FRAMEVIZ_BUSINESS_TOKEN` of at least 32 characters. Put the Host token and business token in the UI fragment as described in each example. Use loopback, disposable state, and synthetic assets for acceptance. Complete native packaging and desktop credential injection are separate validation gates.

See [installation](../../docs/INSTALLATION.md) and [validation](../../docs/VALIDATION.md) before running. No public package registry or private service is assumed.
