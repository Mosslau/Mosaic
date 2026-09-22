module github.com/Mosslau/OceanVerse/ingest/device-simulator

go 1.25

replace github.com/Mosslau/OceanVerse/ingest/device-contracts => ../device-contracts

require (
	github.com/Mosslau/OceanVerse/ingest/device-contracts v0.0.0-00010101000000-000000000000
	github.com/eclipse/paho.mqtt.golang v1.5.0
)

require (
	github.com/gorilla/websocket v1.5.3 // indirect
	golang.org/x/net v0.43.0 // indirect
	golang.org/x/sync v0.13.0 // indirect
)
