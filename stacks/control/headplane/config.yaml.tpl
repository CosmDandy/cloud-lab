server:
  host: "0.0.0.0"
  port: 3000
  cookie_secret: "${COOKIE_SECRET}"
  cookie_secure: false

headscale:
  url: "http://headscale:8080"
  config_path: "/etc/headscale/config.yaml"
  config_strict: true

integration:
  docker:
    enabled: false
    container_name: "headscale"
    socket: "unix:///var/run/docker.sock"
  kubernetes:
    enabled: false
    validate_manifest: true
    pod_name: "headscale"
  proc:
    enabled: false
