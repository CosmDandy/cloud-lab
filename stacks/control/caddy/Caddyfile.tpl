{
    email ${ACME_EMAIL}
}

${PANEL_DOMAIN} {
    reverse_proxy panel:3000
}

${SUB_DOMAIN} {
    reverse_proxy subscription-page:3010 {
        header_up X-Forwarded-Proto https
    }
}

${MON_DOMAIN} {
    reverse_proxy grafana:3000
}

${MESH_DOMAIN} {
    handle /admin/* {
        reverse_proxy headplane:3000
    }

    handle {
        reverse_proxy headscale:8080 {
            flush_interval -1
        }
    }
}
