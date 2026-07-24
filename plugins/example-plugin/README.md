# Example Plugin

A minimal reference plugin for the OGI plugin system.

## What it does

Emits a single `Document` entity describing the input it was given. Nothing is
fetched over the network and no API key is required.

## Layout

```
example-plugin/
  plugin.yaml          # manifest, including the long-form documentation fields
  README.md            # this file, shown in the transform info dialog
  transforms/
    __init__.py
    hello_world.py     # the BaseTransform subclass
```

## Using it as a template

Copy the directory, rename the slug in `plugin.yaml`, and replace the body of
`run()`. Declare any external services under `api_keys_required` rather than
`transform_settings`, and fill in `when_to_use` and `limitations` so analysts
can tell from the info dialog whether your transform fits their investigation.
