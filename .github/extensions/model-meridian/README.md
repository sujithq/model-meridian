# Model Meridian canvas

This project-scoped GitHub Copilot app canvas opens the published Model
Meridian explorer at <https://model-meridian.quintelier.dev/>.

The Copilot app discovers the required `extension.mjs` entry point under
`.github/extensions/model-meridian/`. The entry point joins the active session
with `@github/copilot-sdk/extension`, registers the `model-meridian` canvas,
and returns the hosted explorer URL when Copilot opens it.

Do not install `@github/copilot-sdk` in this directory. The Copilot extension
host supplies its compatible SDK through an automatic module resolver, as
required by the [official extension runtime contract][extension-runtime].
The `package.json` file provides extension metadata and a local contract test;
the canvas has no separately installed runtime dependencies.

## Use in the GitHub Copilot app

1. Open this repository in the GitHub Copilot app.
2. Start a new session so the app discovers project customizations under
   `.github/extensions/`.
3. Ask Copilot to open the **Model Meridian** canvas.

The app opens the URL returned by the extension in its canvas panel. The hosted
page must remain available over HTTPS and allow iframe embedding. In
particular, keep the response free of a restrictive `X-Frame-Options` header or
`Content-Security-Policy: frame-ancestors` directive.

## Verify

Run the deterministic host-contract test from this directory:

```powershell
npm test
```

The test loads the declared `main` entry point against a temporary SDK test
double and verifies that the extension registers one canvas whose `open`
callback returns
`https://model-meridian.quintelier.dev/`.

[extension-runtime]: https://github.com/github/copilot-sdk/blob/main/nodejs/docs/extensions.md
