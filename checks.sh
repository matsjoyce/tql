set -e
mypy tql tests
pylint tql tests
isort tql tests
black tql tests
