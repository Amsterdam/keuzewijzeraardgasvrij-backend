# keuzewijzeraardgasvrij

## Prerequisites

Make sure you have Docker installed locally:

- [Docker](https://docs.docker.com/docker-for-mac/install/)

## Getting up and running (Local development only)

These steps are necessary to make sure all configurations are set up correctly so that you can get the project running correctly.

### Creating networks & build container

First, create a network and build the project:

```bash
docker network create keuzewijzeraardgasvrij_network
docker-compose -f docker-compose.local.yml build
```

### Starting the backend

Run the following to start the backend:

```bash
docker-compose -f docker-compose.local.yml up
```

### Creating a superuser

For accessing the Django admin during local development you'll have to become a `superuser`. This user should have the same `email` and `username` as the one that will be auto-created by the SSO login.

Run the following command to either create the user, or make the existing one a superuser:

```bash
sh bin/setup_superuser.sh <email>
```

### Django admin

Visit the Admin at http://localhost:8082/admin/

## Swagger

http://localhost:8082/api/schema/swagger/

## Django DB migrations

For changes to the model you have to migrate the DB.

```bash
python manage.py makemigrations --name <name_of_your_migration> <name_of_apps>

python manage.py migrate
```

name_of_apps is the model you would like to change like: cases, events, workflow or schedules.
You can use the `---empty` flag to create a custom migration.

## Dependency management & upgrading
This project uses [Poetry](https://python-poetry.org/docs/cli/) for dependency management. You can either manage this locally on your CLI, or do it inside the backend container.

To check for outdated dependencies, run:

```sh
poetry show --outdated
```

To upgrade all packages to their latests version constraints and and create a new lockfile, run:


```sh
poetry update
```

> Note: this means that when `~=1.10` is specified, the package will upgrade to `1.x.x`, but will not upgrade to `2.x.x`.

To upgrade individual packages to major versions, run:

```sh
poetry add <package>@latest
```

> Note: always read changelogs for breaking changes.

## Adding pre-commit hooks

You can add pre-commit hooks for checking and cleaning up your changes:

```bash
bash bin/install_pre_commit.sh
```


## Running tests

Containers should be running to run tests via docker.
```bash
docker compose -f docker-compose.local.yml up -d
docker compose exec -T keuzewijzeraardgasvrij-backend python manage.py test /app/apps
```

## Importing gas usage CSV

Source of the data: https://www.liander.nl/over-ons/open-data#verbruiksdata-kleinverbruikaansluitingen

Copy the CSV into the backend container:

```bash
docker cp LOCATION/verbruikgegevens.csv keuzewijzeraardgasvrij-backend-keuzewijzeraardgasvrij-backend-1:/app
```

Run a dry run first to validate and see how many rows would be created or updated:

```bash
docker compose exec keuzewijzeraardgasvrij-backend python manage.py import_gasverbruikgegevens /app/verbruikgegevens.csv
```

Run the actual import:

```bash
docker compose exec keuzewijzeraardgasvrij-backend python manage.py import_gasverbruikgegevens /app/verbruikgegevens.csv --no-dry-run
```

## Importing buurtcode warmteprogramma CSV

The CSV must contain the columns `buurt_code` and `toelichting`.
`toelichting` is matched against `Warmteprogramma.categorie`. Rows with an unknown category are skipped.

Copy the CSV into the backend container:

```bash
docker cp LOCATION/buurtcodewarmteprogramma.csv keuzewijzeraardgasvrij-backend-keuzewijzeraardgasvrij-backend-1:/app
```

Run the import:

```bash
docker compose exec keuzewijzeraardgasvrij-backend python manage.py import_buurtcodewarmteprogramma /app/buurtcodewarmteprogramma.csv
```

This command deletes all existing `BuurtcodeWarmteprogramma` records and imports the new file in a single transaction.
