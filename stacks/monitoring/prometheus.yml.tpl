global:
  scrape_interval: 15s

scrape_configs:
  - job_name: victoriametrics
    static_configs:
      - targets: ["victoriametrics:8428"]

  - job_name: node-exporter
    static_configs:
      - targets: ["host.docker.internal:9100"]
        labels:
          instance: htz-hel-01

  - job_name: cadvisor
    static_configs:
      - targets: ["cadvisor:8080"]

  - job_name: vmalert
    static_configs:
      - targets: ["vmalert:8880"]

  - job_name: remote-nodes
    static_configs:
      - targets: ["${NODE_HEL_02_ADDRESS}:9100"]
        labels:
          instance: htz-hel-02
