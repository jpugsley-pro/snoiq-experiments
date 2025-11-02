# Makefile
.PHONY: up down lab test lint type logs verify

up:
	docker compose up -d

down:
	docker compose down

lab:
	pixi run lab

test:
	pixi run tests

lint:
	pixi run lint

type:
	pixi run typecheck

logs:
	docker compose logs -f db

verify:
	pixi run lint && pixi run typecheck && pixi run tests