# Frontend applications

`attendx/` is one Flutter package that targets Android, iOS, and the web. Shared
screens stay in `attendx/lib/`; native and browser implementations are separated
under `attendx/lib/core/platform/` and selected through conditional imports.

Keeping one package prevents the mobile and web experiences from drifting while
the standard `android/`, `ios/`, and `web/` folders retain their platform-owned
configuration.
