module github.com/Mosslau/Mosaic/ingest/device-gateway

go 1.25

replace github.com/Mosslau/Mosaic/ingest/device-contracts => ../device-contracts

require (
	github.com/Mosslau/Mosaic/ingest/device-contracts v0.0.0-00010101000000-000000000000
	github.com/eclipse/paho.mqtt.golang v1.5.0
	github.com/prometheus/client_golang v1.23.2
	// client_model 由 internal/kafka/producer_test.go 直接 import(读取 CounterVec 快照),
	// 因此是**直接**依赖 —— 此前误标 indirect, go mod tidy 会把它挪到这里。
	github.com/prometheus/client_model v0.6.2
	github.com/segmentio/kafka-go v0.4.49
	golang.org/x/time v0.14.0
)

require (
	github.com/beorn7/perks v1.0.1 // indirect
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/gorilla/websocket v1.5.3 // indirect
	github.com/klauspost/compress v1.18.0 // indirect
	github.com/kr/text v0.2.0 // indirect
	github.com/munnerz/goautoneg v0.0.0-20191010083416-a7dc8b61c822 // indirect
	github.com/pierrec/lz4/v4 v4.1.15 // indirect
	github.com/prometheus/common v0.66.1 // indirect
	github.com/prometheus/procfs v0.16.1 // indirect
	go.yaml.in/yaml/v2 v2.4.2 // indirect
	golang.org/x/net v0.43.0 // indirect
	golang.org/x/sync v0.13.0 // indirect
	golang.org/x/sys v0.35.0 // indirect
	google.golang.org/protobuf v1.36.8 // indirect
)
