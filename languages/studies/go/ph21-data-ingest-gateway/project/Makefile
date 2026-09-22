# 来源：ph21-data-ingest-gateway project/Makefile
# 用法：make test / make vet / make race / make build / make run-platform / make run-gateway
GO ?= go

.PHONY: build test vet race fmt run-platform run-gateway clean

build:
	$(GO) build ./...

test:
	$(GO) test ./...

vet:
	$(GO) vet ./...

race:
	$(GO) test -race ./...

fmt:
	gofmt -w ./cmd ./internal
	gofmt -l ./cmd ./internal

# 本地演练第一步：起云端（终端 A）
run-platform:
	PLATFORM_ADDR=127.0.0.1:8080 GATEWAY_SECRETS=edge-001=dev-secret-1 \
		$(GO) run ./cmd/platform

# 本地演练第二步：起网关跑一轮确定性演示（终端 B）
run-gateway:
	$(GO) run ./cmd/gateway -once -cloud http://127.0.0.1:8080 \
		-gateway-id edge-001 -secret dev-secret-1 -vehicles 3 -samples 6

clean:
	rm -f edge-platform edge-gateway
