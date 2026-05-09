run:
	docker compose up

stop:
	docker compose down

migrate:
	docker compose exec web python manage.py migrate

seed:
	docker compose exec web python manage.py seed_data

shell:
	docker compose exec web python manage.py shell

test:
	docker compose exec web pytest