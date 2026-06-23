{
	email ${ACME_EMAIL}
}

${SERVER_ADDRESS}:8443 {
	basic_auth {
		${CADDY_USER} ${CADDY_HASH}
	}
	root * /srv/configs
	file_server
}
