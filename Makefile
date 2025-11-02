# Makefile
.PHONY: setup up down tests lint type lab verify clean

setup:
    @pixi install

up:
    @docker compose up -d

down:
    @docker compose down -v

tests:
    @pixi run tests

lint:
    @pixi run lint

type:
    @pixi run type

lab:
    @pixi run lab

verify: lint type tests

clean:
    @find . -name "__pycache__" -type d -prune -exec rm -rf {} +; \
    rm -rf .pytest_cache .mypy_cache
