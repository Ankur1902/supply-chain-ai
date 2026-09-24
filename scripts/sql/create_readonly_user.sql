-- Manual setup for a non-Docker local MySQL install (the docker-compose path
-- creates this automatically via docker/mysql/init/01_readonly_user.sh).
--
-- Run as an admin user against your ai_supply_chain database:
--   mysql -u root -p ai_supply_chain < scripts/sql/create_readonly_user.sql
--
-- Edit the password below (and MYSQL_READONLY_PASSWORD in your .env) first.

CREATE USER IF NOT EXISTS 'supply_chain_ai_ro'@'%' IDENTIFIED BY 'change-me-ro';
GRANT SELECT ON ai_supply_chain.* TO 'supply_chain_ai_ro'@'%';
FLUSH PRIVILEGES;
