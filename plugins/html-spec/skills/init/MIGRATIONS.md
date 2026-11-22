# Spec format migrations

The spec format is the contract between spec files and `style.css` / `global-components.js`. The current format is the number in the header of both assets and in `<meta name="html-spec">` in `templates/html-spec/template.html`.

Every spec declares its format with `<meta name="html-spec" content="N">`, copied from the template.

`/html-spec:init` migrates every spec whose format is lower than the current one, applying the steps below in order (1 → 2, then 2 → 3, ...). Migrations change structure only: never change the content, the language, the decisions or the status of a spec.

The current format is 1. There are no migrations yet.

## Adding a migration (plugin maintainers)

Bump the format when a change to `style.css` or `global-components.js` needs existing specs to change (renamed element or attribute, changed required structure, new required tag). Changes that keep old specs rendering correctly do not bump the format.

1. Increase the number in the header of `assets/style.css` and `assets/global-components.js` and in `templates/html-spec/template.html`.
2. Add a `## N → N+1` section here with exact, mechanical steps.
3. Update the `html-spec` skill if the markup it writes changed.
