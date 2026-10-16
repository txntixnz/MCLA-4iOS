# Stage 8: Native PPC-to-C++ code generator

This workflow builds the **headless ReXGlue code generator** from precisely pinned dependencies (LARecomp and Theft4) using Apple's macOS runner. No Xbox game content is uploaded.

The existing MCLA source tree omits the real ARM64 AOT code and its full shader corpus. Compiling the code generator is the first reproducible step toward filling the missing AOT directory. Passing this workflow is **not** a playable port.

## Private game inputs

The verified ISO in the iOS app is **not** automatically accessible to GitHub Actions. Code generation requires a **local extracted** `default.xex` on a build machine. Do not commit the ISO, XEX, game archives, or generated content derived from them to any public GitHub repository.

The pinned LARecomp manifest and configs are in the `larecomp` submodule. The developer guide explains how to adjust a **local** manifest for the selected XEX, and write generated code to `MCLAApp/generated`. Workflows should stop when the required private inputs are absent, rather than manufacturing placeholder game code.

After AOT codegen succeeds, the large collection of game shader source/metadata and iOS 16 compatible offline `.metallib` outputs remain another blocker. See `docs/DEVELOPMENT.md` and `docs/IOS16_BACKPORT.md`.
