# Makefile
.PHONY: up down logs psql

up:
	docker compose up -d

down:
	docker compose down -v

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

psql:
	docker compose exec db psql -U snoiq -d snoiq_experiments