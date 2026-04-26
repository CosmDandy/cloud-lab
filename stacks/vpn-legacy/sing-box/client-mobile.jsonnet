local outbounds = import 'lib/outbounds.libsonnet';
local route = import 'lib/route.libsonnet';

{
  log: { level: 'warn', timestamp: true },
  dns: {
    servers: [
      { address: 'https://1.1.1.1/dns-query', tag: 'remote', address_resolver: 'local' },
      { address: 'local', tag: 'local' },
      { address: 'rcode://success', tag: 'block' },
    ],
    rules: route.dnsRulesLegacy,
    strategy: 'ipv4_only',
  },
  inbounds: [
    {
      type: 'tun',
      tag: 'tun-in',
      address: ['172.19.0.1/30', 'fdfe:dcba:9876::1/126'],
      mtu: 1400,
      auto_route: true,
      strict_route: true,
      stack: 'mixed',
      route_exclude_address: route.excludeAddresses,
    },
  ],
  outbounds:
    [outbounds.selector(outbounds.allTags)]
    + [outbounds.urltest(outbounds.allTags, '10m')]
    + outbounds.allProtocols
    + [outbounds.warpSelector()]
    + [outbounds.direct()],
  endpoints: [outbounds.warpEndpoint()],
  route: route.base(),
  experimental: {
    cache_file: { enabled: true, path: 'cache.db' },
    clash_api: {
      external_controller: '127.0.0.1:9090',
      external_ui: 'ui',
      external_ui_download_detour: 'direct',
      external_ui_download_url: 'https://github.com/MetaCubeX/metacubexd/archive/gh-pages.zip',
    },
  },
}
