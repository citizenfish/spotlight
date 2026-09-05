# Tools

Asset and data converters that sit between `assets/` and the two targets.

The prototype and the port must not drift, so anything both need — level maps,
sprite bitmaps, attribute data — is authored once in `assets/` and converted
here: into whatever the Python side loads, and into Spectrum-ready bytes for
`spectrum/src/`.

Nothing here yet.
