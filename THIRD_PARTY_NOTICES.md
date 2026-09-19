# Third-party notices

The application and synthetic fixtures were authored for this project. Review of the source and local development history found no copied third-party application source or third-party visual assets in the public selection. Private benchmark source excerpts are excluded from the public export and its Git history.

TypeScript 5.9.3 by Microsoft is the only npm dependency (development/parser toolchain), licensed Apache-2.0. We use its API without modifying the package. Its LICENSE.txt and ThirdPartyNoticeText.txt remain in the parser sidecar when building a ZIP. The source repository does not vendor node_modules.

See [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0), [TypeScript source](https://github.com/microsoft/TypeScript) and the preserved texts in docs/licenses/. Python and Node runtimes are prerequisites and are not bundled. Python packaging uses setuptools as a build requirement; the standard-library ZIP build does not bundle it.

The MIT license applies to our own files, not to TypeScript or its notices. No external fonts, images, or generated branding assets are bundled.
