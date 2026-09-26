# Static dataset via GitHub Actions

GitHub Trending API is delivered as generated JSON and RSS committed by a scheduled GitHub Actions
job and served through repository files and GitHub Raw, rather than through an application server
and database. This keeps operation minimal and makes every published change visible in Git history,
at the cost of update latency, repository write access for Actions, and no dynamic query interface.
