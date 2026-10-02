# RegFire

Source export of the RegFire Nexus registration application and the RegFire corporate website.

- [`app/`](app/): Python/PostgreSQL local application, browser UI, database migrations, tests, documentation and synthetic sample data.
- [`corporate-site/`](corporate-site/): static corporate website, branded assets, teaser video versions and media-rendering scripts.

## Run RegFire Nexus

Install PostgreSQL and Python 3.13, then create a virtual environment in `app/` and install `app/requirements.txt`. Follow [`app/README.md`](app/README.md) for private database setup and [`app/docs/ACCESS_ADMIN.md`](app/docs/ACCESS_ADMIN.md) for owner setup. Existing documentation may refer to the original local workspace; substitute your own checkout path. Private configuration and live event/member data are deliberately absent.

## Preview the corporate website

```sh
cd corporate-site/dist
python3 -m http.server 8080
```

Open http://localhost:8080. No build is required for the checked-in website. Its current teaser is `dist/regfire-teaser-music-louder.mp4`, with the flame poster alongside it. All locally tracked video versions and media source assets are included; no Git LFS or external download is required.

## Reproduce the teaser

The media scripts require Python, Pillow, NumPy and FFmpeg. Set `FFMPEG` to the FFmpeg executable and create `corporate-site/work/` before running them. The approved rendered media is included, so regenerating it is optional. See `corporate-site/scripts/` for the render and mixing stages.

## Export boundaries

This export contains source and reusable media, not operational backups. Credentials, private `.local/` settings, event/member databases, uploads, backups, temporary files, virtual environments and the deployment-specific `.openai/hosting.json` binding are excluded. No hosting deployment is performed by this repository export.

`EXPORT-MANIFEST.json` records SHA-256 checksums of copied source files. Local source workspaces remain in place. Subsequent exports should update these same folders, review the diff and push a normal fast-forward commit; never force-push over remote changes.
