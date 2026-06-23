{
  vlessRealityVision():: {
    type: 'vless',
    tag: 'vless-reality-vision',
    server: '${SERVER_IPV4}',
    server_port: 443,
    uuid: '${VLESS_UUID}',
    flow: 'xtls-rprx-vision',
    tls: {
      enabled: true,
      server_name: 'www.microsoft.com',
      utls: { enabled: true, fingerprint: 'chrome' },
      reality: {
        enabled: true,
        public_key: '${REALITY_PUBLIC_KEY}',
        short_id: '${REALITY_SHORT_ID}',
      },
    },
  },

  vlessRealityGrpc():: {
    type: 'vless',
    tag: 'vless-reality-grpc',
    server: '${SERVER_IPV4}',
    server_port: 8446,
    uuid: '${VLESS_UUID}',
    flow: '',
    tls: {
      enabled: true,
      server_name: 'dl.google.com',
      utls: { enabled: true, fingerprint: 'chrome' },
      reality: {
        enabled: true,
        public_key: '${REALITY_PUBLIC_KEY}',
        short_id: '${REALITY_SHORT_ID}',
      },
    },
    transport: { type: 'grpc', service_name: 'grpc' },
  },

  hysteria2Salamander():: {
    type: 'hysteria2',
    tag: 'hysteria2-salamander',
    server: '${SERVER_IPV4}',
    server_port: 443,
    password: '${HY2_PASSWORD}',
    tls: { enabled: true, server_name: 'bing.com', insecure: true },
    obfs: { type: 'salamander', password: '${SALAMANDER_PASSWORD}' },
  },

  warpEndpoint():: {
    type: 'wireguard',
    tag: 'warp',
    detour: 'proxy',
    private_key: '${WARP_PRIVATE_KEY}',
    address: ['${WARP_ADDRESS_V4}/32', '${WARP_ADDRESS_V6}/128'],
    mtu: 1280,
    peers: [
      {
        public_key: 'bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=',
        address: 'engage.cloudflareclient.com',
        port: 2408,
        allowed_ips: ['0.0.0.0/0', '::/0'],
      },
    ],
  },

  direct():: { type: 'direct', tag: 'direct' },

  allProtocols:: [
    self.vlessRealityVision(),
    self.vlessRealityGrpc(),
    self.hysteria2Salamander(),
  ],

  allTags:: [o.tag for o in self.allProtocols],

  selector(tags):: {
    type: 'selector',
    tag: 'proxy',
    outbounds: ['auto'] + tags,
    default: 'vless-reality-vision',
  },

  warpSelector():: {
    type: 'selector',
    tag: 'warp-out',
    outbounds: ['warp', 'proxy', 'direct'],
    default: 'warp',
  },

  urltest(tags, interval='1m', tag='auto'):: {
    type: 'urltest',
    tag: tag,
    outbounds: tags,
    url: 'https://www.gstatic.com/generate_204',
    interval: interval,
    tolerance: 150,
    interrupt_exist_connections: true,
  },
}
