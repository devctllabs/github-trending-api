# GitHub Trending API

Static JSON and RSS snapshots of GitHub Trending, refreshed four times per day by GitHub Actions.
The dataset covers `daily`, `weekly`, and `monthly` periods for `all`, `python`, `rust`, `go`,
`javascript`, and `typescript`.

## Data

`current` contains the latest published snapshot. `archive` contains one accumulated UTC daily
rollup per feed.

```text
https://raw.githubusercontent.com/<owner>/<repo>/main/data/current/{period}/{language}.{json|xml}
https://raw.githubusercontent.com/<owner>/<repo>/main/data/archive/{YYYY}/{MM}/{DD}/{period}/{language}.{json|xml}
```

## Documentation

- [Dataset behavior](docs/product/dataset.md)
- [JSON and RSS data contract](docs/product/data-contract.md)
- [Documentation index](docs/README.md)
