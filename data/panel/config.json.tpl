{
  "configProfiles": [
    {
      "name": "VLESS-Reality",
      "config": {
        "log": { "loglevel": "warning" },
        "inbounds": [
          {
            "tag": "VLESS-Reality-Vision",
            "port": 443,
            "protocol": "vless",
            "settings": {
              "clients": [],
              "decryption": "none"
            },
            "streamSettings": {
              "network": "raw",
              "security": "reality",
              "realitySettings": {
                "show": false,
                "dest": "www.microsoft.com:443",
                "xver": 0,
                "serverNames": ["www.microsoft.com"],
                "privateKey": "${REALITY_PRIVATE_KEY}",
                "shortIds": ["${REALITY_SHORT_ID}"]
              }
            },
            "sniffing": {
              "enabled": true,
              "destOverride": ["http", "tls", "quic"]
            }
          },
          {
            "tag": "VLESS-Reality-gRPC",
            "port": 443,
            "protocol": "vless",
            "settings": {
              "clients": [],
              "decryption": "none"
            },
            "streamSettings": {
              "network": "grpc",
              "grpcSettings": { "serviceName": "grpc" },
              "security": "reality",
              "realitySettings": {
                "show": false,
                "dest": "dl.google.com:443",
                "xver": 0,
                "serverNames": ["dl.google.com"],
                "privateKey": "${REALITY_PRIVATE_KEY}",
                "shortIds": ["${REALITY_SHORT_ID}"]
              }
            },
            "sniffing": {
              "enabled": true,
              "destOverride": ["http", "tls", "quic"]
            }
          },
          {
            "tag": "VLESS-Reality-XHTTP",
            "port": 443,
            "protocol": "vless",
            "settings": {
              "clients": [],
              "decryption": "none"
            },
            "streamSettings": {
              "network": "xhttp",
              "xhttpSettings": { "mode": "auto", "path": "/xhttp" },
              "security": "reality",
              "realitySettings": {
                "show": false,
                "dest": "www.google.com:443",
                "xver": 0,
                "serverNames": ["www.google.com"],
                "privateKey": "${REALITY_PRIVATE_KEY}",
                "shortIds": ["${REALITY_SHORT_ID}"]
              }
            },
            "sniffing": {
              "enabled": true,
              "destOverride": ["http", "tls", "quic"]
            }
          }
        ],
        "outbounds": [
          { "tag": "DIRECT", "protocol": "freedom" },
          { "tag": "BLOCK", "protocol": "blackhole" }
        ],
        "routing": {
          "rules": [
            { "type": "field", "outboundTag": "BLOCK", "protocol": ["bittorrent"] }
          ]
        }
      }
    }
  ],
  "nodes": [
    {
      "name": "htz-hel-02",
      "address": "htz-hel-02.cosmdandy.dev",
      "port": 2222,
      "countryCode": "FI",
      "configProfile": "VLESS-Reality"
    }
  ],
  "hosts": [
    {
      "remark": "HEL-02 Vision",
      "address": "htz-hel-02.cosmdandy.dev",
      "port": 443,
      "sni": "www.microsoft.com",
      "fingerprint": "chrome",
      "inboundTag": "VLESS-Reality-Vision",
      "configProfile": "VLESS-Reality",
      "nodes": ["htz-hel-02"]
    },
    {
      "remark": "HEL-02 gRPC",
      "address": "htz-hel-02.cosmdandy.dev",
      "port": 443,
      "sni": "dl.google.com",
      "fingerprint": "chrome",
      "inboundTag": "VLESS-Reality-gRPC",
      "configProfile": "VLESS-Reality",
      "nodes": ["htz-hel-02"]
    },
    {
      "remark": "HEL-02 XHTTP",
      "address": "htz-hel-02.cosmdandy.dev",
      "port": 443,
      "sni": "www.google.com",
      "fingerprint": "chrome",
      "path": "/xhttp",
      "inboundTag": "VLESS-Reality-XHTTP",
      "configProfile": "VLESS-Reality",
      "nodes": ["htz-hel-02"]
    }
  ]
}
