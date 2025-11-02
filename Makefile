# Makefile
.PHONY: setup up down tests lint type lab verify clean health bucket

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
	@pixi run typecheck

lab:
	@pixi run lab

verify: lint type tests

clean:
	@find . -name "__pycache__" -type d -prune -exec rm -rf {} +; \
	rm -rf .pytest_cache .mypy_cache

health:
	@docker compose ps
	@curl -sf http://127.0.0.1:9000/minio/health/ready && echo "MinIO up" || echo "MinIO not ready"
	@dvc remote list -v
	@dvc status -c

bucket:
	@AWS_ACCESS_KEY_ID=minio AWS_SECRET_ACCESS_KEY=minio12345 AWS_DEFAULT_REGION=us-east-1 AWS_EC2_METADATA_DISABLED=true \
	aws s3 mb s3://snoiq-experiments --endpoint-url http://127.0.0.1:9000 || true
