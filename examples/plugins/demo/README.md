# `openflowsheet-demo-plugin`

A minimal OpenFlowsheet plugin (extension distribution). It declares the entry point `demo` in the
group `openflowsheet.extensions` and registers one descriptor, the message catalogue
`demo.messages` with the code `demo.feed_too_wet`. It adds no unit model, property method or
numerics.

The plugin guide (`docs-site/guide/plugins.md`, "Plugins (extensions)" on the documentation site)
explains every part of it: the entry point, the package document, the descriptor fields, message
entries, namespaces, quarantine and the evidence flags. `tests/test_x01_example_plugin.py`
discovers it through the registry's entry-point discovery.

To try it next to an installed OpenFlowsheet (illustrative):

<!-- snippet: illustrative -->
```console
$ pip install ./examples/plugins/demo
$ openflowsheet capabilities --prefix demo.
$ openflowsheet explain demo.feed_too_wet
```
