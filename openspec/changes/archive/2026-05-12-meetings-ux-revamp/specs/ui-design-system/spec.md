## ADDED Requirements

### Requirement: --color-secondary SHALL be a distinct teal hue, not a surface-2 alias

The web app SHALL define `--color-secondary` and
`--color-secondary-foreground` as standalone oklch values keyed to
hue 195 (teal/cyan) in BOTH the `[data-theme="light"]` and
`[data-theme="dark"]` token blocks of `packages/web/src/index.css`.
The pre-change binding (`var(--color-surface-2)`) SHALL be removed.
Any UI that previously consumed `--color-secondary` as a neutral
surface MUST migrate to `--color-muted` or `--color-surface-2`
directly.

Concrete values:

- Light theme: `--color-secondary: oklch(0.62 0.12 195);`
  `--color-secondary-foreground: oklch(1 0 0);`
- Dark theme: `--color-secondary: oklch(0.7 0.13 195);`
  `--color-secondary-foreground: oklch(0.14 0.012 var(--primary-hue-dark));`

Hue 195 was chosen because it is roughly opposite both light-theme
primary (purple, hue 280) and dark-theme primary (orange, hue 50)
on the oklch wheel, so the secondary action stays visually distinct
from primary in either theme. It is also far enough from
`--color-success` (green, hue 155) to avoid confusion.

`Button variant="secondary"` SHALL render with the new token,
producing a teal pill in both themes. Other Button variants
(primary / outline / ghost / destructive) SHALL NOT change.

#### Scenario: Light-theme secondary button renders teal

- **GIVEN** the user has the light theme active and views any
  page that renders a `<Button variant="secondary">`
- **WHEN** the button is in its default (non-hover) state
- **THEN** its background SHALL resolve to `oklch(0.62 0.12 195)`
  and its foreground SHALL resolve to white

#### Scenario: Dark-theme secondary button renders teal

- **GIVEN** the user has the dark theme active and views the same
  page
- **WHEN** the button is in its default (non-hover) state
- **THEN** its background SHALL resolve to `oklch(0.7 0.13 195)`
  and its foreground SHALL resolve to the dark-theme background
  colour

#### Scenario: Other button variants are unaffected

- **GIVEN** the codebase after this change ships
- **WHEN** the source is scanned for Button `variant="primary"`,
  `variant="outline"`, `variant="ghost"`, and `variant="destructive"`
  call sites
- **THEN** each variant SHALL render the same colour as before this
  change in both themes
