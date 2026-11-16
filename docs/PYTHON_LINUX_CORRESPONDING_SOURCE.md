# Corresponding source for the FrameViz Linux wheel

The Linux wheel is delivered with a separate source archive. Its `BUILD-RECORD.txt` identifies the wheel hash, SDK revision, native revision and exact build inputs. Keep the source archive available from the same download page as the wheel. Retain copies for each binary revision that is distributed.

The archive contains these directories and records.

- `ubuntu/pool/` has the original source package descriptors, upstream archives, Ubuntu patches and signature files for the exact Ubuntu source versions used by the AppDir.
- `ubuntu/apt/` retains the signed Ubuntu snapshot indexes used to select and verify the source files. `ubuntu/source-manifest.json` maps the package versions to the signed indexes and file hashes.
- `frameviz/` has the source revisions for the native application and the wheel assembler, including build scripts and lockfiles. Resolve Rust and JavaScript dependencies from the checked-in Cargo and pnpm locks when rebuilding FrameViz.
- `build/` records the AppDir inputs, the WebKitGTK relocation and the original notices carried in the wheel. The relocation record includes the file, the replacement bytes and count, and the SHA-256 before and after modification.

After extracting the archive, run the following from its root to check the delivered source files.

```sh
sha256sum -c SHA256SUMS
(cd ubuntu && sha256sum -c SHA256SUMS)
```

To work on Ubuntu's WebKitGTK source, install your standard packaging tools and unpack the included descriptor and archives together. Use the previously supplied Ubuntu archive keyring to authenticate the index files. The manifest provides the exact source package paths. For this candidate, use:

```sh
dpkg-source -x ubuntu/pool/main/w/webkit2gtk/webkit2gtk_2.50.4-0ubuntu0.22.04.1.dsc
```

This yields Ubuntu's source and patch series. The additional FrameViz relocation occurs when `scripts/release/build_linux_appdir.py` assembles the runtime. Its modifying function is in the wheel assembly source revision. The included `runtime-build.json` records its effect. The [Linux build instructions](PYTHON_LINUX_RELEASE.md) give the SDK and AppDir reconstruction commands. The collection can be restored from the signed snapshot with `scripts/release/collect_ubuntu_sources.py` and the included `ubuntu-runtime-sources.json` index.
