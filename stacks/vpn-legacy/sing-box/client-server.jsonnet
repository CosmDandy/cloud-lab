local outbounds = import 'lib/outbounds.libsonnet';
local route = import 'lib/route.libsonnet';

{
  log: { level: 'info', timestamp: true },
  dns: {
    servers: [
      { type: 'https', tag: 'remote', server: '1.1.1.1', domain_resolver: 'local' },
      { type: 'local', tag: 'local' },
    ],
    rules: route.dnsRules,
    strategy: 'ipv4_only',
  },
  inbounds: [
    {
      type: 'mixed',
      tag: 'mixed-in',
      listen: '::',
      listen_port: 7890,
    },
    {
      type: 'redirect',
      tag: 'redirect-in',
      listen: '::',
      listen_port: 7891,
    },
  ],
  outbounds:
    [outbounds.selector(outbounds.allTags)]
    + [outbounds.urltest(outbounds.allTags)]
    + outbounds.allProtocols
    + [outbounds.warpSelector()]
    + [outbounds.direct()],
  endpoints: [outbounds.warpEndpoint()],
  route: route.base({ default_domain_resolver: 'local' }),
  experimental: {
    cache_file: { enabled: true, path: 'cache.db' },
  },
}
