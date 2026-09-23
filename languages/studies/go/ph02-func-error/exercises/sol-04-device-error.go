// exercises/sol-04-device-error.go —— 练习 4 参考实现：自定义业务错误
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-04-device-error.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"errors"
	"fmt"
)

// DeviceError 是自定义业务错误类型，携带错误码与设备 DEVICE_ID。
type DeviceError struct {
	Code    int
	DeviceID     string
	Message string
}

func (e *DeviceError) Error() string {
	return fmt.Sprintf("device error (code=%d, device_id=%s): %s", e.Code, e.DeviceID, e.Message)
}

// checkDevice 校验设备状态：DEVICE_ID 必填，电量过低不可上路。
func checkDevice(device_id string, soc float64) error {
	if device_id == "" {
		return &DeviceError{Code: 1001, DeviceID: device_id, Message: "device_id is required"}
	}
	if soc < 20 {
		return &DeviceError{Code: 2001, DeviceID: device_id, Message: fmt.Sprintf("soc %.0f%% below 20%%", soc)}
	}
	return nil
}

func main() {
	if err := checkDevice("", 80); err != nil {
		var ve *DeviceError
		if errors.As(err, &ve) {
			fmt.Println("参数错误:", ve)
		}
	}

	if err := checkDevice("LFV3A28K1A5000001", 15); err != nil {
		var ve *DeviceError
		if errors.As(err, &ve) {
			switch ve.Code {
			case 2001:
				fmt.Printf("设备 %s 电量过低（code=%d），请充电\n", ve.DeviceID, ve.Code)
			default:
				fmt.Println("设备校验失败:", ve)
			}
		}
	}

	if err := checkDevice("LFV3A28K1A5000001", 80); err == nil {
		fmt.Println("设备状态正常，可以上路")
	}
}
