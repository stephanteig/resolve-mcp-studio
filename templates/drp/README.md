# Template .drp files

Place exported DaVinci Resolve project files (`.drp`) here, e.g. `_TEMPLATE_.drp`.

A template config in `templates/configs/` can reference a `.drp` file with an
optional `"drp"` key (filename relative to this directory):

```json
{ "name": "My template", "drp": "_TEMPLATE_.drp", ... }
```

When a config references an existing `.drp`, `create_project_from_template`
imports it (renamed to the new project name) instead of building the project
from the config fields. Without a `"drp"` reference, the project is created
from scratch using the config (resolution, fps, timelines, bins).

`.drp` files are not checked into git — copy your own template file in here.
