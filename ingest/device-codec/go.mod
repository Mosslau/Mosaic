module github.com/Mosslau/OceanVerse/ingest/device-codec

go 1.25

replace github.com/Mosslau/OceanVerse/contracts => ../../contracts

require (
	github.com/Mosslau/OceanVerse/contracts v0.0.0-00010101000000-000000000000
	github.com/segmentio/kafka-go v0.4.49
)

require (
	github.com/klauspost/compress v1.18.0 // indirect
	github.com/pierrec/lz4/v4 v4.1.15 // indirect
)
