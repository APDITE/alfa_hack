COMPOSE ?= docker compose
DEV  = $(COMPOSE) -f docker-compose.dev.yml
TEST = $(COMPOSE) -f docker-compose.test.yml
PROD = $(COMPOSE) -f docker-compose.prod.yml

.DEFAULT_GOAL := help
.PHONY: help env dev dev-down test prod prod-down prod-cert-init prod-cert-renew

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-18s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

dev: env ## Start the development stack (HTTP, reload, API docs)
	$(DEV) up --build

dev-down: ## Stop the development stack
	$(DEV) down --remove-orphans

test: ## Run backend tests and frontend checks in isolation
	$(TEST) run --rm --build backend-tests
	$(TEST) run --rm --build frontend-checks
	$(TEST) down --remove-orphans

prod: env ## Start the production stack (HTTPS, needs a domain)
	$(PROD) up -d --build

prod-down: ## Stop the production stack
	$(PROD) down --remove-orphans

prod-cert-init: env ## Obtain the first Let's Encrypt certificate
	NGINX_CONF=prod-http.conf.template $(PROD) up -d --build nginx
	$(PROD) run --rm --entrypoint sh certbot -c 'certbot certonly --webroot -w /var/www/certbot -d "$$CERTBOT_DOMAIN" --email "$$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email --non-interactive'
	$(PROD) up -d --force-recreate nginx

prod-cert-renew: ## Renew certificates and reload Nginx (run daily via cron)
	$(PROD) run --rm --entrypoint certbot certbot renew --webroot -w /var/www/certbot
	$(PROD) exec nginx nginx -s reload
