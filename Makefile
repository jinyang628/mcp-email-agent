.PHONY: lint publish

lint:
	poetry run black .
	poetry run isort .
	poetry run autoflake --in-place --remove-all-unused-imports --recursive .
	poetry run pylint **/*.py

publish:
	poetry build
	poetry publish
