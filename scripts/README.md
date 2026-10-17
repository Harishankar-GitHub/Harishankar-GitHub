# Profile images

The header, link buttons, career timeline and tech stack on the profile are SVG
images built from **[`profile.toml`](profile.toml)**. The README blocks that
show them (between the `<!-- profile:… -->` markers) are generated too, so their
alt text always matches the images.

## Updating the profile

1. Edit `scripts/profile.toml`: add a job, change a title, add or remove a skill.
2. Commit and push. The **Build profile images** GitHub Action rebuilds
   `assets/` and the README blocks and commits the result to the same branch.

You can edit the file straight in the GitHub web editor. Text outside the
markers in the main `README.md` (the About section, the footer) is ordinary
Markdown, so edit it as usual.

## Building locally

```bash
pip install -r scripts/requirements.txt
python scripts/build_assets.py          # rebuild everything
python scripts/build_assets.py --check  # exit 1 if anything is out of date
```

Needs Python 3.11 or newer.

## Adding a tech logo

Find the tool on [simpleicons.org](https://simpleicons.org), download its SVG
into `scripts/icons/` (for example `scripts/icons/terraform.svg`), and add it to
`profile.toml` with its brand colour:

```toml
{ name = "Terraform", icon = "terraform", color = "844FBA" }
```

For things with no logo, use one of the built-in symbols: `sparkle`, `db`,
`braces`, `nodes` or `check`.

## How it works

- Every image is built in two sizes. GitHub shows the narrow version on phones
  and small windows (below 1012px wide) and the wide version on desktop.
- The career and tech stack images have light and dark variants that follow the
  viewer's GitHub theme.
- Text is converted to vector outlines with the fonts in `scripts/fonts/`, so
  the images look the same on every device and need no web fonts or
  third-party image services.

## Credits

- Fonts: [Inter](https://github.com/rsms/inter) (SIL Open Font License 1.1) and
  [DejaVu Sans Mono](https://dejavu-fonts.github.io/) (Bitstream Vera licence),
  trimmed to Latin characters. Licences are in `scripts/fonts/`.
- Brand icons: [Simple Icons](https://simpleicons.org) (CC0). The logos are
  trademarks of their respective owners.
