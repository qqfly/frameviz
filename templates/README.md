# Application template

The [external application template](frameviz-template-external-app/README.md) contains a Vue front end, Tauri shell, and Python/C++ backend examples for protocol 0.4.0.

Use the source-tree generator or the packaged devkit to create an application. The devkit includes local JavaScript SDK tarballs; Python and C++ use the explicit local wheel/install prefix. See the [installation guide](../docs/INSTALLATION.md) and the template README for business authentication and runtime configuration.

The generator preserves LICENSE, NOTICE, and third-party notices. The source template and devkit are starting points for application development. Native packaging, credential injection, and target-platform installation require separate acceptance.

For a smaller example, use [simple_slider](../examples/apps/simple_slider/README.md).
