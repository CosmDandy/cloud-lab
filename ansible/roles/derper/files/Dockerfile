# Managed by ansible (roles/derper). Правки на хосте будут перезаписаны.
ARG GO_IMAGE=golang:1.26-alpine

FROM ${GO_IMAGE} AS build
ARG DERPER_VERSION
RUN go install tailscale.com/cmd/derper@${DERPER_VERSION}

FROM alpine:3
RUN apk add --no-cache ca-certificates
COPY --from=build /go/bin/derper /usr/local/bin/derper
ENTRYPOINT ["/usr/local/bin/derper"]
