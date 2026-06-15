run:
	docker compose up

stop:
	docker compose down

migrate:
	docker compose exec web python manage.py migrate

seed:
	docker compose exec web python manage.py seed_data password123

reset-seed:
	docker compose exec web python manage.py seed_data password123 --flush

shell:
	docker compose exec web python manage.py shell

test:
	docker compose exec web pytest